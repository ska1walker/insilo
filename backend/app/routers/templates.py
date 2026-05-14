"""Templates: system templates (read-only) + per-org templates (full CRUD).

The 4 seed system templates ship with fixed schemas tied to specific use
cases (Mandantengespräch, Vertriebsgespräch, …). Orgs can customize their
system_prompt via the /prompt endpoints below — name/description/schema
stay frozen.

Org templates are fully editable: name, description, system_prompt — they
all use a default flexible schema (DEFAULT_USER_SCHEMA) so the
SummaryView's generic renderer can display them without per-template
knowledge.
"""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import CurrentUser, get_current_user
from app.db import acquire

router = APIRouter(prefix="/api/v1", tags=["templates"])


# Sensible default schema for user-created templates. Flexible enough to
# cover most meeting shapes; SummaryView already knows the field names
# via LABEL_OVERRIDES.
DEFAULT_USER_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "zusammenfassung": {"type": "string"},
        "kernpunkte": {"type": "array", "items": {"type": "string"}},
        "entscheidungen": {"type": "array", "items": {"type": "string"}},
        "aufgaben": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "was": {"type": "string"},
                    "wer": {"type": "string"},
                    "wann": {"type": "string"},
                },
            },
        },
        "offene_fragen": {"type": "array", "items": {"type": "string"}},
    },
}


def _base_dto(row) -> dict:
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
    """All active templates visible to the user: system-wide + own org.

    Each row carries `is_customized` so the UI can show a small badge
    next to templates the org has tailored.
    """
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            select t.id, t.name, t.description, t.category, t.is_system,
                   t.version, t.output_schema,
                   (c.template_id is not null) as is_customized
            from public.templates t
            left join public.template_customizations c
                on c.template_id = t.id and c.org_id = $1
            where t.is_active = true
              and (t.is_system = true or t.org_id = $1)
            order by t.is_system desc, t.name asc
            """,
            user.org_id,
        )
    out = []
    for r in rows:
        dto = _base_dto(r)
        dto["is_customized"] = r["is_customized"]
        out.append(dto)
    return out


@router.get("/templates/{template_id}")
async def get_template(
    template_id: UUID, user: CurrentUser = Depends(get_current_user)
) -> dict:
    """Full template detail including effective and default system prompts."""
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            select t.id, t.name, t.description, t.category, t.is_system,
                   t.version, t.output_schema, t.system_prompt as default_prompt,
                   c.system_prompt as custom_prompt,
                   c.updated_at as custom_updated_at
            from public.templates t
            left join public.template_customizations c
                on c.template_id = t.id and c.org_id = $2
            where t.id = $1
              and t.is_active = true
              and (t.is_system = true or t.org_id = $2)
            """,
            template_id,
            user.org_id,
        )
    if not row:
        raise HTTPException(404, "template not found")

    dto = _base_dto(row)
    dto["default_prompt"] = row["default_prompt"]
    dto["custom_prompt"] = row["custom_prompt"]
    dto["is_customized"] = row["custom_prompt"] is not None
    dto["effective_prompt"] = row["custom_prompt"] or row["default_prompt"]
    dto["custom_updated_at"] = (
        row["custom_updated_at"].isoformat() if row["custom_updated_at"] else None
    )
    return dto


class PromptUpdate(BaseModel):
    system_prompt: str = Field(..., min_length=10, max_length=20_000)


@router.put("/templates/{template_id}/prompt")
async def upsert_template_prompt(
    template_id: UUID,
    payload: PromptUpdate,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Override a template's system prompt for the calling org.

    Idempotent — repeating the call just updates the override. Use the
    DELETE variant to revert to the system default.
    """
    async with acquire() as conn:
        # Ensure the template is one the user can see.
        tpl = await conn.fetchrow(
            """
            select id from public.templates
            where id = $1
              and is_active = true
              and (is_system = true or org_id = $2)
            """,
            template_id,
            user.org_id,
        )
        if not tpl:
            raise HTTPException(404, "template not found")

        await conn.execute(
            """
            insert into public.template_customizations (
                org_id, template_id, system_prompt, updated_by
            )
            values ($1, $2, $3, $4)
            on conflict (org_id, template_id) do update set
                system_prompt = excluded.system_prompt,
                updated_by = excluded.updated_by
            """,
            user.org_id,
            template_id,
            payload.system_prompt.strip(),
            user.user_id,
        )
    return {"status": "ok", "template_id": str(template_id)}


@router.delete("/templates/{template_id}/prompt", status_code=204)
async def reset_template_prompt(
    template_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> None:
    """Drop the org's customization. Worker reverts to the template default."""
    async with acquire() as conn:
        await conn.execute(
            """
            delete from public.template_customizations
            where org_id = $1 and template_id = $2
            """,
            user.org_id,
            template_id,
        )


# ─── Org-Template CRUD ────────────────────────────────────────────────


class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    system_prompt: str = Field(..., min_length=10, max_length=20_000)


class TemplateUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    system_prompt: str = Field(..., min_length=10, max_length=20_000)


@router.post("/templates", status_code=201)
async def create_template(
    payload: TemplateCreate,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Create a new org-owned template with the flexible default schema."""
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            insert into public.templates (
                org_id, name, description, category,
                system_prompt, output_schema,
                is_system, is_active, version, created_by
            )
            values ($1, $2, $3, 'custom', $4, $5::jsonb, false, true, 1, $6)
            returning id, name, description, category, is_system, version, output_schema
            """,
            user.org_id,
            payload.name.strip(),
            payload.description.strip(),
            payload.system_prompt.strip(),
            json.dumps(DEFAULT_USER_SCHEMA),
            user.user_id,
        )
    dto = _base_dto(row)
    dto["is_customized"] = False
    return dto


@router.put("/templates/{template_id}")
async def update_template(
    template_id: UUID,
    payload: TemplateUpdate,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Update an org-owned template's name, description and system_prompt.

    System templates are read-only here — use PUT /templates/{id}/prompt
    for the customization override.
    """
    async with acquire() as conn:
        tpl = await conn.fetchrow(
            """
            select id, is_system from public.templates
            where id = $1 and is_active = true
            """,
            template_id,
        )
        if not tpl:
            raise HTTPException(404, "template not found")
        if tpl["is_system"]:
            raise HTTPException(
                403,
                "system templates can only be customized via /prompt — name and "
                "description are fixed",
            )

        row = await conn.fetchrow(
            """
            update public.templates
            set name = $2, description = $3, system_prompt = $4,
                version = version + 1, updated_at = now()
            where id = $1 and org_id = $5 and is_active = true
            returning id, name, description, category, is_system, version, output_schema
            """,
            template_id,
            payload.name.strip(),
            payload.description.strip(),
            payload.system_prompt.strip(),
            user.org_id,
        )
        if not row:
            raise HTTPException(404, "template not found in your organisation")
    dto = _base_dto(row)
    dto["is_customized"] = False
    return dto


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> None:
    """Soft-delete an org-owned template. System templates are protected."""
    async with acquire() as conn:
        tpl = await conn.fetchrow(
            "select is_system, org_id from public.templates where id = $1 and is_active = true",
            template_id,
        )
        if not tpl:
            raise HTTPException(404, "template not found")
        if tpl["is_system"]:
            raise HTTPException(403, "system templates cannot be deleted")
        if tpl["org_id"] != user.org_id:
            raise HTTPException(404, "template not found in your organisation")

        await conn.execute(
            """
            update public.templates set is_active = false, updated_at = now()
            where id = $1 and org_id = $2
            """,
            template_id,
            user.org_id,
        )
