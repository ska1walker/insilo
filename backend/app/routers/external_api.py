"""External, token-authenticated read-only API.

Lives under `/api/external/v1/*`. Authenticates via `Authorization: Bearer
inskey_…`. Org-scope is implicit in the key — every endpoint scopes
queries to `caller.org_id`.

Scope `read:meetings` is the only one defined in this iteration; we
gate every endpoint behind it via `require_scope`.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.auth_api import ApiCaller, require_scope
from app.db import acquire
from app.exports.markdown import render_meeting_markdown

router = APIRouter(prefix="/api/external/v1", tags=["external-api"])


READ_MEETINGS = require_scope("read:meetings")


def _meeting_row_to_external(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "status": row["status"],
        "recorded_at": row["recorded_at"].isoformat() if row["recorded_at"] else None,
        "duration_sec": row["duration_sec"],
        "language": row["language"],
        "template_id": str(row["template_id"]) if row["template_id"] else None,
        "template_name": row.get("template_name"),
        "tags": row.get("tags") or [],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


@router.get("/meetings")
async def list_meetings(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None, max_length=32),
    caller: ApiCaller = Depends(READ_MEETINGS),
) -> dict[str, Any]:
    async with acquire() as conn:
        if status:
            rows = await conn.fetch(
                """
                select m.id, m.title, m.status, m.recorded_at, m.duration_sec,
                       m.language, m.template_id, m.created_at,
                       t.name as template_name
                from public.meetings m
                left join public.templates t on t.id = m.template_id
                where m.org_id = $1 and m.deleted_at is null and m.status = $2
                order by m.recorded_at desc
                limit $3 offset $4
                """,
                caller.org_id,
                status,
                limit,
                offset,
            )
        else:
            rows = await conn.fetch(
                """
                select m.id, m.title, m.status, m.recorded_at, m.duration_sec,
                       m.language, m.template_id, m.created_at,
                       t.name as template_name
                from public.meetings m
                left join public.templates t on t.id = m.template_id
                where m.org_id = $1 and m.deleted_at is null
                order by m.recorded_at desc
                limit $2 offset $3
                """,
                caller.org_id,
                limit,
                offset,
            )

        if not rows:
            return {"items": [], "limit": limit, "offset": offset}

        meeting_ids = [r["id"] for r in rows]
        tag_rows = await conn.fetch(
            """
            select mt.meeting_id, t.name
            from public.meeting_tags mt
            join public.tags t on t.id = mt.tag_id
            where mt.meeting_id = any($1::uuid[])
            order by t.name asc
            """,
            meeting_ids,
        )
        tags_by_meeting: dict[str, list[str]] = {}
        for tr in tag_rows:
            tags_by_meeting.setdefault(str(tr["meeting_id"]), []).append(tr["name"])

    items = []
    for r in rows:
        d = _meeting_row_to_external(dict(r))
        d["tags"] = tags_by_meeting.get(d["id"], [])
        items.append(d)
    return {"items": items, "limit": limit, "offset": offset}


async def _fetch_meeting_for_export(conn, meeting_id: UUID, org_id: UUID) -> tuple[
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
    list[dict[str, Any]],
    str | None,
]:
    meeting = await conn.fetchrow(
        """
        select m.id, m.title, m.status, m.recorded_at, m.duration_sec,
               m.language, m.template_id, m.audio_size_bytes,
               m.error_message, m.created_at,
               t.name as template_name
        from public.meetings m
        left join public.templates t on t.id = m.template_id
        where m.id = $1 and m.org_id = $2 and m.deleted_at is null
        """,
        meeting_id,
        org_id,
    )
    if meeting is None:
        return None, None, None, [], None

    transcript_row = await conn.fetchrow(
        """
        select segments, speakers, full_text, language, whisper_model, word_count
        from public.transcripts where meeting_id = $1
        """,
        meeting_id,
    )
    transcript = None
    if transcript_row is not None:
        segs = transcript_row["segments"]
        if isinstance(segs, str):
            segs = json.loads(segs)
        speakers = transcript_row["speakers"]
        if isinstance(speakers, str):
            speakers = json.loads(speakers)
        transcript = {
            "segments": segs or [],
            "speakers": speakers or [],
            "full_text": transcript_row["full_text"],
            "language": transcript_row["language"],
        }

    summary_row = await conn.fetchrow(
        """
        select s.content, s.llm_model, s.created_at, t.name as template_name
        from public.summaries s
        join public.templates t on t.id = s.template_id
        where s.meeting_id = $1 and s.is_current = true
        order by s.created_at desc
        limit 1
        """,
        meeting_id,
    )
    summary = None
    template_name = meeting["template_name"]
    if summary_row is not None:
        content = summary_row["content"]
        if isinstance(content, str):
            content = json.loads(content)
        summary = {"content": content, "llm_model": summary_row["llm_model"]}
        template_name = summary_row["template_name"] or template_name

    tag_rows = await conn.fetch(
        """
        select t.name, t.color
        from public.meeting_tags mt
        join public.tags t on t.id = mt.tag_id
        where mt.meeting_id = $1
        order by t.name asc
        """,
        meeting_id,
    )
    tags = [{"name": r["name"], "color": r["color"]} for r in tag_rows]

    return dict(meeting), transcript, summary, tags, template_name


@router.get("/meetings/{meeting_id}")
async def get_meeting(
    meeting_id: UUID,
    caller: ApiCaller = Depends(READ_MEETINGS),
) -> dict[str, Any]:
    async with acquire() as conn:
        meeting, transcript, summary, tags, template_name = await _fetch_meeting_for_export(
            conn, meeting_id, caller.org_id
        )
    if meeting is None:
        raise HTTPException(404, "meeting not found")

    dto = _meeting_row_to_external(meeting)
    dto["template_name"] = template_name
    dto["tags"] = [t["name"] for t in tags]
    if transcript:
        dto["transcript"] = transcript
    if summary:
        dto["summary"] = summary
    return dto


@router.get("/meetings/{meeting_id}/markdown")
async def get_meeting_markdown(
    meeting_id: UUID,
    caller: ApiCaller = Depends(READ_MEETINGS),
) -> Response:
    async with acquire() as conn:
        meeting, transcript, summary, tags, template_name = await _fetch_meeting_for_export(
            conn, meeting_id, caller.org_id
        )
    if meeting is None:
        raise HTTPException(404, "meeting not found")

    body = render_meeting_markdown(
        meeting=meeting,
        transcript=transcript,
        summary=summary,
        tags=tags,
        template_name=template_name,
        include_transcript=True,
    )
    return Response(content=body, media_type="text/markdown; charset=utf-8")
