"""Templates: read-only system templates + org-private templates (Phase 2 MVP)."""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth import CurrentUser, get_current_user
from app.db import acquire

router = APIRouter(prefix="/api/v1", tags=["templates"])


def _row_to_dto(row) -> dict:
    schema = row["output_schema"]
    if isinstance(schema, str):
        schema = json.loads(schema)
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "description": row["description"],
        "category": row["category"],
        "is_system": row["is_system"],
        "version": row["version"],
        "output_schema": schema,
    }


@router.get("/templates")
async def list_templates(user: CurrentUser = Depends(get_current_user)) -> list[dict]:
    """All active templates visible to the user: system-wide + own org."""
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            select id, name, description, category, is_system, version, output_schema
            from public.templates
            where is_active = true
              and (is_system = true or org_id = $1)
            order by is_system desc, name asc
            """,
            user.org_id,
        )
    return [_row_to_dto(r) for r in rows]


@router.get("/templates/{template_id}")
async def get_template(
    template_id: UUID, user: CurrentUser = Depends(get_current_user)
) -> dict:
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            select id, name, description, category, is_system, version,
                   system_prompt, output_schema
            from public.templates
            where id = $1
              and is_active = true
              and (is_system = true or org_id = $2)
            """,
            template_id,
            user.org_id,
        )
    if not row:
        from fastapi import HTTPException
        raise HTTPException(404, "template not found")
    dto = _row_to_dto(row)
    dto["system_prompt"] = row["system_prompt"]
    return dto
