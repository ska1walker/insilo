"""Meeting CRUD + audio upload."""

import json
import re
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.auth import CurrentUser, get_current_user
from app.db import acquire
from app.storage import delete_object, get_presigned_url, upload_bytes
from app.tasks.transcribe import transcribe_meeting

_SPEAKER_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")

router = APIRouter(prefix="/api/v1", tags=["meetings"])


def _audio_key(org_id: UUID, meeting_id: UUID, mime_type: str) -> str:
    ext = "webm"
    if "mp4" in mime_type:
        ext = "m4a"
    elif "ogg" in mime_type:
        ext = "ogg"
    elif "wav" in mime_type:
        ext = "wav"
    return f"{org_id}/{meeting_id}.{ext}"


def _meeting_row_to_dto(row, audio_url: str | None = None) -> dict:
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "created_at": row["recorded_at"].isoformat() if isinstance(row["recorded_at"], datetime) else row["recorded_at"],
        "duration_ms": (row["duration_sec"] or 0) * 1000,
        "mime_type": row["audio_mime"] or "audio/webm",
        "byte_size": row["audio_size_bytes"] or 0,
        "status": row["status"],
        "audio_url": audio_url,
    }


@router.get("/meetings")
async def list_meetings(user: CurrentUser = Depends(get_current_user)) -> list[dict]:
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            select id, title, recorded_at, duration_sec, audio_size_bytes,
                   audio_path, status, metadata->>'mime_type' as audio_mime
            from public.meetings
            where org_id = $1 and deleted_at is null
            order by recorded_at desc
            """,
            user.org_id,
        )
    return [_meeting_row_to_dto(r) for r in rows]


@router.get("/meetings/{meeting_id}")
async def get_meeting(meeting_id: UUID, user: CurrentUser = Depends(get_current_user)) -> dict:
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            select m.id, m.title, m.recorded_at, m.duration_sec, m.audio_size_bytes,
                   m.audio_path, m.status, m.error_message, m.template_id,
                   m.metadata->>'mime_type' as audio_mime,
                   t.name as template_name
            from public.meetings m
            left join public.templates t on t.id = m.template_id
            where m.id = $1 and m.org_id = $2 and m.deleted_at is null
            """,
            meeting_id,
            user.org_id,
        )
        if row is None:
            raise HTTPException(404, "meeting not found")

        transcript_row = await conn.fetchrow(
            """
            select segments, speakers, full_text, language, whisper_model, word_count
            from public.transcripts
            where meeting_id = $1
            """,
            meeting_id,
        )

        summary_row = await conn.fetchrow(
            """
            select s.content, s.llm_model, s.generation_time_ms,
                   s.created_at, s.template_id, s.template_version,
                   t.name as template_name
            from public.summaries s
            join public.templates t on t.id = s.template_id
            where s.meeting_id = $1 and s.is_current = true
            order by s.created_at desc
            limit 1
            """,
            meeting_id,
        )

    audio_url = get_presigned_url(row["audio_path"]) if row["audio_path"] else None
    dto = _meeting_row_to_dto(row, audio_url=audio_url)
    dto["error_message"] = row["error_message"]
    dto["template_id"] = str(row["template_id"]) if row["template_id"] else None
    dto["template_name"] = row["template_name"]

    if transcript_row is not None:
        segs = transcript_row["segments"]
        if isinstance(segs, str):
            segs = json.loads(segs)
        speakers_field = transcript_row["speakers"]
        if isinstance(speakers_field, str):
            speakers_field = json.loads(speakers_field)
        dto["transcript"] = {
            "segments": segs,
            "speakers": speakers_field or [],
            "full_text": transcript_row["full_text"],
            "language": transcript_row["language"],
            "whisper_model": transcript_row["whisper_model"],
            "word_count": transcript_row["word_count"],
        }

    if summary_row is not None:
        content = summary_row["content"]
        if isinstance(content, str):
            content = json.loads(content)
        dto["summary"] = {
            "content": content,
            "llm_model": summary_row["llm_model"],
            "generation_time_ms": summary_row["generation_time_ms"],
            "created_at": summary_row["created_at"].isoformat() if summary_row["created_at"] else None,
            "template_id": str(summary_row["template_id"]),
            "template_name": summary_row["template_name"],
            "template_version": summary_row["template_version"],
        }

    return dto


@router.post("/recordings", status_code=201)
async def create_recording(
    audio: UploadFile = File(...),
    title: str = Form(...),
    duration_ms: int = Form(...),
    mime_type: str = Form(...),
    template_id: str | None = Form(default=None),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    blob = await audio.read()
    meeting_id = uuid4()
    key = _audio_key(user.org_id, meeting_id, mime_type)

    # Upload to MinIO first; only commit DB row on success.
    upload_bytes(key, blob, mime_type)

    duration_sec = max(1, duration_ms // 1000)

    tpl_uuid: UUID | None = UUID(template_id) if template_id else None

    async with acquire() as conn:
        # Validate template visibility if one was passed (otherwise the
        # summarize task falls back to the system default).
        if tpl_uuid is not None:
            allowed = await conn.fetchval(
                """
                select 1 from public.templates
                where id = $1
                  and is_active = true
                  and (is_system = true or org_id = $2)
                """,
                tpl_uuid,
                user.org_id,
            )
            if not allowed:
                raise HTTPException(400, "template not available")

        row = await conn.fetchrow(
            """
            insert into public.meetings (
                id, org_id, created_by, title, status,
                duration_sec, audio_path, audio_size_bytes,
                language, template_id, metadata
            )
            values (
                $1, $2, $3, $4, 'queued',
                $5, $6, $7,
                'de', $8, jsonb_build_object('mime_type', $9::text)
            )
            returning id, title, recorded_at, duration_sec, audio_size_bytes,
                     audio_path, status, template_id,
                     metadata->>'mime_type' as audio_mime
            """,
            meeting_id,
            user.org_id,
            user.user_id,
            title,
            duration_sec,
            key,
            len(blob),
            tpl_uuid,
            mime_type,
        )

    # Hand off transcription to the Celery worker. The HTTP response returns
    # immediately; the frontend polls status until it flips to "ready".
    transcribe_meeting.delay(str(meeting_id))

    return _meeting_row_to_dto(row, audio_url=get_presigned_url(key))


class SpeakerEntry(BaseModel):
    id: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=120)


class SpeakerAssignment(BaseModel):
    """Replace the speakers roster + per-segment speaker assignments.

    `speakers` is the canonical list (id + display name). `segments` maps
    segment index → speaker id (or null to clear). Unknown segment indices
    are ignored; ids that aren't in `speakers` are rejected.
    """

    speakers: list[SpeakerEntry] = Field(default_factory=list)
    segments: dict[str, str | None] = Field(default_factory=dict)


@router.put("/meetings/{meeting_id}/transcript/speakers")
async def update_transcript_speakers(
    meeting_id: UUID,
    payload: SpeakerAssignment,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    # Sanity: ids must be url-safe and unique.
    seen: set[str] = set()
    for s in payload.speakers:
        if not _SPEAKER_ID_RE.match(s.id):
            raise HTTPException(400, f"invalid speaker id: {s.id!r}")
        if s.id in seen:
            raise HTTPException(400, f"duplicate speaker id: {s.id!r}")
        seen.add(s.id)

    valid_ids = {s.id for s in payload.speakers}
    for idx, sid in payload.segments.items():
        if sid is not None and sid not in valid_ids:
            raise HTTPException(400, f"segment {idx} references unknown speaker {sid!r}")

    async with acquire() as conn:
        # Make sure the user owns the meeting.
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

        row = await conn.fetchrow(
            "select segments from public.transcripts where meeting_id = $1",
            meeting_id,
        )
        if row is None:
            raise HTTPException(409, "no transcript yet")

        segs = row["segments"]
        if isinstance(segs, str):
            segs = json.loads(segs)
        if not isinstance(segs, list):
            raise HTTPException(500, "transcript.segments has unexpected shape")

        # Apply per-segment assignments. Keys come as strings from JSON.
        for k, sid in payload.segments.items():
            try:
                i = int(k)
            except ValueError:
                continue
            if 0 <= i < len(segs):
                segs[i]["speaker"] = sid

        speakers_payload = [s.model_dump() for s in payload.speakers]

        await conn.execute(
            """
            update public.transcripts
            set segments = $2::jsonb, speakers = $3::jsonb
            where meeting_id = $1
            """,
            meeting_id,
            json.dumps(segs),
            json.dumps(speakers_payload),
        )

    return {"status": "ok", "speakers": speakers_payload, "segments": segs}


@router.post("/meetings/{meeting_id}/retry-summary", status_code=202)
async def retry_summary(
    meeting_id: UUID, user: CurrentUser = Depends(get_current_user)
) -> dict:
    """Re-queue summarization for a meeting whose summary failed or is stale.

    Useful after the user has configured a reachable LLM endpoint in
    Einstellungen — they don't want to re-record the meeting, just retry
    the summary step against the freshly-configured endpoint.
    """
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            select m.id, m.status, t.full_text
            from public.meetings m
            left join public.transcripts t on t.meeting_id = m.id
            where m.id = $1 and m.org_id = $2 and m.deleted_at is null
            """,
            meeting_id,
            user.org_id,
        )
        if row is None:
            raise HTTPException(404, "meeting not found")
        if not row["full_text"]:
            raise HTTPException(
                409, "no transcript yet — cannot summarize"
            )
        await conn.execute(
            """
            update public.meetings
            set status = 'summarizing', error_message = null, updated_at = now()
            where id = $1
            """,
            meeting_id,
        )

    # Send the task directly to Celery — `transcribe_meeting` would re-do
    # transcription, which is wasteful when only the summary needs retrying.
    from app.worker import celery_app
    celery_app.send_task("summarize_meeting", args=[str(meeting_id)])
    return {"status": "queued", "meeting_id": str(meeting_id)}


@router.delete("/meetings/{meeting_id}", status_code=204)
async def delete_meeting(
    meeting_id: UUID, user: CurrentUser = Depends(get_current_user)
) -> None:
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            update public.meetings
            set deleted_at = now()
            where id = $1 and org_id = $2 and deleted_at is null
            returning audio_path
            """,
            meeting_id,
            user.org_id,
        )
    if row is None:
        raise HTTPException(404, "meeting not found")
    # Soft-delete in DB; also remove from object storage to reclaim space.
    if row["audio_path"]:
        try:
            delete_object(row["audio_path"])
        except Exception:
            # If object is already gone, don't fail the request.
            pass
