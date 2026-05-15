"""Org-scoped Tags + Meeting-Tag-Verknüpfung.

Schema (in 0001_initial_schema.sql vorhanden):
    public.tags(id, org_id, name, color, created_at)
    public.meeting_tags(meeting_id, tag_id, added_at)

RLS (in 0002_rls_policies.sql vorhanden) erlaubt CRUD nur für Tags der
eigenen Org — wir validieren hier zusätzlich für klare Fehlermeldungen
und 4xx-Statuscodes statt nackter RLS-DENY.
"""

from __future__ import annotations

import re
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import CurrentUser, get_current_user
from app.db import acquire
from app.errors import http_error
from app.tasks.notify import enqueue as enqueue_webhook

router = APIRouter(prefix="/api/v1", tags=["tags"])

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_DEFAULT_COLOR = "#737065"


class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    color: str | None = None


class TagUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    color: str | None = None


class TagDto(BaseModel):
    id: str
    name: str
    color: str


class MeetingTagAttach(BaseModel):
    tag_id: UUID


def _normalize_name(name: str) -> str:
    return name.strip()


def _validate_color(color: str | None) -> str:
    if color is None:
        return _DEFAULT_COLOR
    if not _HEX_COLOR_RE.match(color):
        raise http_error(400, "tags.invalid_color", color=repr(color))
    return color.lower()


def _row_to_dto(row) -> TagDto:
    return TagDto(
        id=str(row["id"]),
        name=row["name"],
        color=row["color"] or _DEFAULT_COLOR,
    )


@router.get("/tags")
async def list_tags(user: CurrentUser = Depends(get_current_user)) -> list[TagDto]:
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            select id, name, color
            from public.tags
            where org_id = $1
            order by name asc
            """,
            user.org_id,
        )
    return [_row_to_dto(r) for r in rows]


@router.post("/tags", status_code=201)
async def create_tag(
    payload: TagCreate,
    user: CurrentUser = Depends(get_current_user),
) -> TagDto:
    name = _normalize_name(payload.name)
    if not name:
        raise http_error(400, "tags.name_empty")
    color = _validate_color(payload.color)

    async with acquire() as conn:
        try:
            row = await conn.fetchrow(
                """
                insert into public.tags (org_id, name, color)
                values ($1, $2, $3)
                returning id, name, color
                """,
                user.org_id,
                name,
                color,
            )
        except asyncpg.UniqueViolationError:
            raise http_error(409, "tags.duplicate", name=name) from None
    return _row_to_dto(row)


@router.put("/tags/{tag_id}")
async def update_tag(
    tag_id: UUID,
    payload: TagUpdate,
    user: CurrentUser = Depends(get_current_user),
) -> TagDto:
    name = _normalize_name(payload.name)
    if not name:
        raise http_error(400, "tags.name_empty")
    color = _validate_color(payload.color)

    async with acquire() as conn:
        try:
            row = await conn.fetchrow(
                """
                update public.tags
                set name = $2, color = $3
                where id = $1 and org_id = $4
                returning id, name, color
                """,
                tag_id,
                name,
                color,
                user.org_id,
            )
        except asyncpg.UniqueViolationError:
            raise http_error(409, "tags.duplicate", name=name) from None
    if not row:
        raise http_error(404, "tags.not_found")
    return _row_to_dto(row)


@router.delete("/tags/{tag_id}", status_code=204)
async def delete_tag(
    tag_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> None:
    async with acquire() as conn:
        result = await conn.execute(
            "delete from public.tags where id = $1 and org_id = $2",
            tag_id,
            user.org_id,
        )
    # asyncpg returns "DELETE n"
    if result == "DELETE 0":
        raise http_error(404, "tags.not_found")


# ─── Meeting ↔ Tag Verknüpfung ────────────────────────────────────────


async def _ensure_meeting_owned(conn, meeting_id: UUID, org_id) -> None:
    owned = await conn.fetchval(
        """
        select 1 from public.meetings
        where id = $1 and org_id = $2 and deleted_at is null
        """,
        meeting_id,
        org_id,
    )
    if not owned:
        raise http_error(404, "meeting.not_found")


async def _ensure_tag_owned(conn, tag_id: UUID, org_id) -> None:
    owned = await conn.fetchval(
        "select 1 from public.tags where id = $1 and org_id = $2",
        tag_id,
        org_id,
    )
    if not owned:
        raise http_error(404, "tags.not_found")


@router.post("/meetings/{meeting_id}/tags", status_code=201)
async def attach_tag_to_meeting(
    meeting_id: UUID,
    payload: MeetingTagAttach,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    async with acquire() as conn:
        await _ensure_meeting_owned(conn, meeting_id, user.org_id)
        await _ensure_tag_owned(conn, payload.tag_id, user.org_id)
        await conn.execute(
            """
            insert into public.meeting_tags (meeting_id, tag_id)
            values ($1, $2)
            on conflict (meeting_id, tag_id) do nothing
            """,
            meeting_id,
            payload.tag_id,
        )
    enqueue_webhook(meeting_id, "meeting.updated")
    return {"status": "ok"}


@router.delete("/meetings/{meeting_id}/tags/{tag_id}", status_code=204)
async def detach_tag_from_meeting(
    meeting_id: UUID,
    tag_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> None:
    async with acquire() as conn:
        await _ensure_meeting_owned(conn, meeting_id, user.org_id)
        await conn.execute(
            """
            delete from public.meeting_tags
            where meeting_id = $1 and tag_id = $2
            """,
            meeting_id,
            tag_id,
        )
    enqueue_webhook(meeting_id, "meeting.updated")
