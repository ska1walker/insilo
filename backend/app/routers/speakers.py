"""Org-Speaker-Katalog: CRUD + per-Meeting cluster assignment + re-diarize.

Endpoints:
    GET    /api/v1/speakers                       — list org speakers
    POST   /api/v1/speakers                       — create (name only, no voiceprint yet)
    PUT    /api/v1/speakers/{id}                  — rename / set is_self / clear voiceprint
    DELETE /api/v1/speakers/{id}                  — hard delete (cascades to voiceprints)

    GET    /api/v1/meetings/{mid}/clusters        — list clusters for a meeting
    POST   /api/v1/meetings/{mid}/clusters/{cid}/assign
           Body: { org_speaker_id: uuid | null, new_name?: str }
           Either assigns to an existing speaker (and appends a voiceprint sample),
           creates a new speaker with that name (also append sample),
           or clears the assignment (org_speaker_id=null).

    POST   /api/v1/meetings/{mid}/re-diarize      — re-run diarization on archived audio
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.auth import CurrentUser, get_current_user
from app.config import settings as env_settings
from app.db import acquire
from app.speaker_matcher import append_voiceprint_sample
from app.tasks.notify import enqueue as enqueue_webhook

router = APIRouter(prefix="/api/v1", tags=["speakers"])


# ─── Pydantic DTOs ─────────────────────────────────────────────────────


class SpeakerCreate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    is_self: bool = False


class SpeakerUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    is_self: bool | None = None
    # If true, wipe the voiceprint + sample history. Speaker stays in the
    # catalog but Insilo will no longer auto-match anyone to them.
    clear_voiceprint: bool = False


class SpeakerRead(BaseModel):
    id: str
    display_name: str
    description: str
    is_self: bool
    has_voiceprint: bool
    sample_count: int
    last_heard_at: str | None
    created_at: str


class ClusterAssign(BaseModel):
    """Assign a meeting-cluster to an org-speaker.

    - `org_speaker_id` is the existing speaker to bind to. Set to null
      to clear the assignment.
    - `new_name` shortcuts speaker-creation: if set (and org_speaker_id
      is null), Insilo creates a new org-speaker with that name and
      binds the cluster to it. Mutually exclusive with org_speaker_id.
    """

    org_speaker_id: UUID | None = None
    new_name: str | None = Field(default=None, min_length=1, max_length=120)


class ClusterRead(BaseModel):
    cluster_idx: int
    org_speaker_id: str | None
    display_name: str | None
    match_score: float | None
    assignment: str
    is_self: bool


# ─── Helpers ───────────────────────────────────────────────────────────


def _speaker_row_to_read(row: dict[str, Any]) -> SpeakerRead:
    return SpeakerRead(
        id=str(row["id"]),
        display_name=row["display_name"],
        description=row["description"] or "",
        is_self=bool(row["is_self"]),
        has_voiceprint=row["voiceprint"] is not None,
        sample_count=int(row["sample_count"] or 0),
        last_heard_at=row["last_heard_at"].isoformat() if row["last_heard_at"] else None,
        created_at=row["created_at"].isoformat() if row["created_at"] else "",
    )


# ─── Speaker CRUD ──────────────────────────────────────────────────────


@router.get("/speakers", response_model=list[SpeakerRead])
async def list_speakers(
    user: CurrentUser = Depends(get_current_user),
) -> list[SpeakerRead]:
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            select id, display_name, description, is_self,
                   voiceprint, sample_count, last_heard_at, created_at
            from public.org_speakers
            where org_id = $1
            order by is_self desc, display_name asc
            """,
            user.org_id,
        )
    return [_speaker_row_to_read(dict(r)) for r in rows]


@router.post("/speakers", status_code=201, response_model=SpeakerRead)
async def create_speaker(
    payload: SpeakerCreate,
    user: CurrentUser = Depends(get_current_user),
) -> SpeakerRead:
    name = payload.display_name.strip()
    if not name:
        raise HTTPException(400, "name must not be empty")

    async with acquire() as conn:
        async with conn.transaction():
            # If is_self=true, clear is_self on any existing speaker in the org —
            # there can be at most one "self" per org (unique partial index).
            if payload.is_self:
                await conn.execute(
                    "update public.org_speakers set is_self = false where org_id = $1",
                    user.org_id,
                )
            try:
                row = await conn.fetchrow(
                    """
                    insert into public.org_speakers (
                        org_id, display_name, description, is_self, created_by
                    )
                    values ($1, $2, $3, $4, $5)
                    returning id, display_name, description, is_self,
                              voiceprint, sample_count, last_heard_at, created_at
                    """,
                    user.org_id,
                    name,
                    payload.description.strip(),
                    payload.is_self,
                    user.user_id,
                )
            except Exception as exc:  # noqa: BLE001 — convert unique-violation to 409
                if "org_speakers" in str(exc) and "unique" in str(exc).lower():
                    raise HTTPException(409, f"speaker '{name}' already exists") from None
                raise
    return _speaker_row_to_read(dict(row))


@router.put("/speakers/{speaker_id}", response_model=SpeakerRead)
async def update_speaker(
    speaker_id: UUID,
    payload: SpeakerUpdate,
    user: CurrentUser = Depends(get_current_user),
) -> SpeakerRead:
    async with acquire() as conn:
        async with conn.transaction():
            existing = await conn.fetchrow(
                "select id from public.org_speakers where id = $1 and org_id = $2",
                speaker_id,
                user.org_id,
            )
            if existing is None:
                raise HTTPException(404, "speaker not found")

            if payload.is_self is True:
                # Demote any current self-speaker first.
                await conn.execute(
                    """
                    update public.org_speakers
                    set is_self = false
                    where org_id = $1 and id <> $2
                    """,
                    user.org_id,
                    speaker_id,
                )

            if payload.clear_voiceprint:
                await conn.execute(
                    "delete from public.speaker_voiceprints where org_speaker_id = $1",
                    speaker_id,
                )

            row = await conn.fetchrow(
                """
                update public.org_speakers set
                    display_name = coalesce($2, display_name),
                    description  = coalesce($3, description),
                    is_self      = coalesce($4, is_self),
                    voiceprint   = case when $5 then null else voiceprint end,
                    sample_count = case when $5 then 0 else sample_count end,
                    last_heard_at = case when $5 then null else last_heard_at end
                where id = $1
                returning id, display_name, description, is_self,
                          voiceprint, sample_count, last_heard_at, created_at
                """,
                speaker_id,
                payload.display_name.strip() if payload.display_name is not None else None,
                payload.description.strip() if payload.description is not None else None,
                payload.is_self,
                payload.clear_voiceprint,
            )
    return _speaker_row_to_read(dict(row))


@router.delete("/speakers/{speaker_id}", status_code=204)
async def delete_speaker(
    speaker_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> None:
    async with acquire() as conn:
        result = await conn.execute(
            "delete from public.org_speakers where id = $1 and org_id = $2",
            speaker_id,
            user.org_id,
        )
    if result == "DELETE 0":
        raise HTTPException(404, "speaker not found")


# ─── Cluster listing + assignment ──────────────────────────────────────


@router.get("/meetings/{meeting_id}/clusters", response_model=list[ClusterRead])
async def list_clusters(
    meeting_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> list[ClusterRead]:
    async with acquire() as conn:
        owned = await conn.fetchval(
            """
            select 1 from public.meetings
            where id = $1 and org_id = $2 and deleted_at is null
            """,
            meeting_id,
            user.org_id,
        )
        if not owned:
            raise HTTPException(404, "meeting not found")
        rows = await conn.fetch(
            """
            select c.cluster_idx, c.org_speaker_id, c.match_score, c.assignment,
                   s.display_name, s.is_self
            from public.meeting_speaker_clusters c
            left join public.org_speakers s on s.id = c.org_speaker_id
            where c.meeting_id = $1
            order by c.cluster_idx asc
            """,
            meeting_id,
        )
    return [
        ClusterRead(
            cluster_idx=r["cluster_idx"],
            org_speaker_id=str(r["org_speaker_id"]) if r["org_speaker_id"] else None,
            display_name=r["display_name"],
            match_score=float(r["match_score"]) if r["match_score"] is not None else None,
            assignment=r["assignment"],
            is_self=bool(r["is_self"]) if r["is_self"] is not None else False,
        )
        for r in rows
    ]


@router.post("/meetings/{meeting_id}/clusters/{cluster_idx}/assign")
async def assign_cluster(
    meeting_id: UUID,
    cluster_idx: int,
    payload: ClusterAssign,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    if payload.org_speaker_id is not None and payload.new_name is not None:
        raise HTTPException(400, "provide either org_speaker_id or new_name, not both")

    async with acquire() as conn:
        async with conn.transaction():
            cluster = await conn.fetchrow(
                """
                select c.id, c.meeting_id, c.centroid::text as centroid_txt
                from public.meeting_speaker_clusters c
                join public.meetings m on m.id = c.meeting_id
                where c.meeting_id = $1
                  and c.cluster_idx = $2
                  and m.org_id = $3
                  and m.deleted_at is null
                """,
                meeting_id,
                cluster_idx,
                user.org_id,
            )
            if cluster is None:
                raise HTTPException(404, "cluster not found")

            # Resolve target speaker.
            target_id: UUID | None = None
            target_name: str | None = None
            if payload.new_name is not None:
                # Create the speaker on the fly.
                name = payload.new_name.strip()
                if not name:
                    raise HTTPException(400, "new_name must not be empty")
                try:
                    new_row = await conn.fetchrow(
                        """
                        insert into public.org_speakers (
                            org_id, display_name, created_by
                        ) values ($1, $2, $3)
                        returning id, display_name
                        """,
                        user.org_id,
                        name,
                        user.user_id,
                    )
                except Exception as exc:  # noqa: BLE001
                    if "unique" in str(exc).lower():
                        raise HTTPException(
                            409, f"speaker '{name}' already exists"
                        ) from None
                    raise
                target_id = new_row["id"]
                target_name = new_row["display_name"]
            elif payload.org_speaker_id is not None:
                sp = await conn.fetchrow(
                    """
                    select id, display_name from public.org_speakers
                    where id = $1 and org_id = $2
                    """,
                    payload.org_speaker_id,
                    user.org_id,
                )
                if sp is None:
                    raise HTTPException(404, "org_speaker not found")
                target_id = sp["id"]
                target_name = sp["display_name"]

            # Update the cluster row.
            await conn.execute(
                """
                update public.meeting_speaker_clusters
                set org_speaker_id = $2,
                    assignment = $3
                where meeting_id = $1 and cluster_idx = $4
                """,
                meeting_id,
                target_id,
                "manual" if target_id else "pending",
                cluster_idx,
            )

            # Patch transcripts.speakers entry for this cluster.
            tr = await conn.fetchrow(
                "select speakers from public.transcripts where meeting_id = $1",
                meeting_id,
            )
            if tr is not None:
                speakers_field = tr["speakers"]
                if isinstance(speakers_field, str):
                    speakers_field = json.loads(speakers_field)
                if isinstance(speakers_field, list) and 0 <= cluster_idx < len(speakers_field):
                    entry = dict(speakers_field[cluster_idx])
                    if target_id:
                        entry["id"] = f"org_{target_id}"
                        entry["name"] = target_name
                        entry["org_speaker_id"] = str(target_id)
                        entry["assignment"] = "manual"
                    else:
                        entry["id"] = f"cluster_{cluster_idx}"
                        entry["name"] = f"SPEAKER_{cluster_idx:02d}"
                        entry.pop("org_speaker_id", None)
                        entry["assignment"] = "pending"
                    speakers_field[cluster_idx] = entry
                    await conn.execute(
                        """
                        update public.transcripts
                        set speakers = $2::jsonb
                        where meeting_id = $1
                        """,
                        meeting_id,
                        json.dumps(speakers_field),
                    )

        # Outside transaction: append voiceprint sample (refines the
        # speaker's primary voiceprint).
        if target_id is not None:
            try:
                centroid_text = cluster["centroid_txt"]
                # pgvector serialises as '[v1,v2,…]'
                centroid = [float(x) for x in centroid_text.strip("[]").split(",")]
                await append_voiceprint_sample(
                    conn,
                    org_speaker_id=target_id,
                    meeting_id=meeting_id,
                    cluster_idx=cluster_idx,
                    embedding=centroid,
                    source="manual",
                    created_by=user.user_id,
                )
            except Exception:
                # Voiceprint refinement failure must not break the assignment.
                pass

    enqueue_webhook(meeting_id, "meeting.updated")
    return {
        "status": "ok",
        "cluster_idx": cluster_idx,
        "org_speaker_id": str(target_id) if target_id else None,
        "display_name": target_name,
    }


# ─── Voice enrollment ──────────────────────────────────────────────────


class EnrollResult(BaseModel):
    status: str
    voiced_seconds: float
    total_seconds: float
    sample_count: int
    speaker_id: str
    display_name: str


@router.post("/speakers/{speaker_id}/enroll", response_model=EnrollResult)
async def enroll_speaker(
    speaker_id: UUID,
    audio: UploadFile = File(...),
    min_voiced_seconds: float = Form(default=5.0),
    user: CurrentUser = Depends(get_current_user),
) -> EnrollResult:
    """Attach a dedicated voice sample (e.g. read aloud "Der Nordwind und
    die Sonne") to a speaker. Goes through the whisper /embed-only
    endpoint, runs VAD-trim + ECAPA-TDNN, and stores the result as a
    `source='enrollment'` voiceprint sample.

    Validation:
    - `min_voiced_seconds` (default 5.0) — at least this much active
      speech must remain after VAD trimming. Stops short uploads from
      polluting the voiceprint mean.
    - whisper returns 422 if its own VAD finds insufficient signal — we
      forward that as 422 with a German user-facing message.
    """
    # 1. Verify the speaker belongs to this org.
    async with acquire() as conn:
        speaker = await conn.fetchrow(
            """
            select id, display_name
            from public.org_speakers
            where id = $1 and org_id = $2
            """,
            speaker_id,
            user.org_id,
        )
    if speaker is None:
        raise HTTPException(404, "speaker not found")

    # 2. Read upload + forward to whisper /embed-only.
    payload = await audio.read()
    if not payload:
        raise HTTPException(400, "empty audio upload")

    mime = audio.content_type or "audio/webm"
    embed_url = f"{env_settings.whisper_url}/embed-only"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            resp = await client.post(
                embed_url,
                files={"audio": ("enrollment.bin", payload, mime)},
                data={"min_voiced_seconds": str(min_voiced_seconds)},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            503, f"Whisper-Service nicht erreichbar: {exc.__class__.__name__}"
        ) from None

    if resp.status_code == 422:
        # Forward whisper's "not enough speech" verdict in German.
        raise HTTPException(
            422,
            "Die Aufnahme enthält zu wenig erkennbare Sprache. Bitte "
            "sprechen Sie mindestens 5 Sekunden klar und nahe am Mikrofon.",
        )
    if resp.status_code != 200:
        raise HTTPException(
            502,
            f"Whisper-Service antwortete mit HTTP {resp.status_code}",
        )

    embed_data = resp.json()
    embedding: list[float] = embed_data["embedding"]
    voiced_sec: float = float(embed_data["voiced_seconds"])
    total_sec: float = float(embed_data["total_seconds"])

    # 3. Persist as voiceprint sample. Enrollment samples have no
    # meeting/cluster — migration 0007 made those columns nullable.
    async with acquire() as conn:
        await append_voiceprint_sample(
            conn,
            org_speaker_id=speaker_id,
            meeting_id=None,
            cluster_idx=None,
            embedding=embedding,
            source="enrollment",
            created_by=user.user_id,
        )
        sample_count = await conn.fetchval(
            "select sample_count from public.org_speakers where id = $1",
            speaker_id,
        )

    return EnrollResult(
        status="ok",
        voiced_seconds=voiced_sec,
        total_seconds=total_sec,
        sample_count=int(sample_count or 0),
        speaker_id=str(speaker_id),
        display_name=speaker["display_name"],
    )


# ─── Re-Diarize ────────────────────────────────────────────────────────


@router.post("/meetings/{meeting_id}/re-diarize", status_code=202)
async def re_diarize(
    meeting_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Re-run whisper diarization on the archived audio.

    Useful for meetings recorded before v0.1.37 (no cluster centroids
    persisted) — running this once gives them a fresh diarization +
    auto-match against the current org-speaker catalog. Heavy: full
    Whisper transcription + ECAPA embedding pass.
    """
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            select m.id, m.audio_path
            from public.meetings m
            where m.id = $1 and m.org_id = $2 and m.deleted_at is null
            """,
            meeting_id,
            user.org_id,
        )
    if row is None:
        raise HTTPException(404, "meeting not found")
    if not row["audio_path"]:
        raise HTTPException(409, "no audio retained for this meeting")

    # Hand off to the existing transcribe pipeline — it now persists
    # cluster centroids + does auto-matching as part of its normal path.
    from app.worker import celery_app as _app
    _app.send_task("transcribe_meeting", args=[str(meeting_id)])
    return {"status": "queued", "meeting_id": str(meeting_id)}
