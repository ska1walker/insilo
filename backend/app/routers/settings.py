"""Per-org settings: LLM endpoint + key + model.

The API never returns the raw `llm_api_key` — it returns `llm_api_key_set`
(bool) and the masked tail of the stored key. On PUT, an empty string means
"clear the override" (fall back to env), while a non-empty string overwrites.

If the client wants to keep the existing key untouched while changing other
fields, it sends `llm_api_key: null` (or omits the field).
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import CurrentUser, get_current_user
from app.config import settings as env_settings
from app.db import acquire
from app.llm_config import auth_header, load_llm_config

router = APIRouter(prefix="/api/v1", tags=["settings"])


class SettingsRead(BaseModel):
    llm_base_url: str
    llm_api_key_set: bool
    llm_api_key_hint: str  # last 4 chars if set, else ""
    llm_model: str

    # Spracherkennung. Leere Adresse = der mitgelieferte Whisper-Dienst
    # transkribiert, und kein Audio verlässt die Box.
    stt_base_url: str
    stt_api_key_set: bool
    stt_api_key_hint: str
    stt_model: str

    # Defaults from the deployment env — useful in the UI to show
    # "Aktuell aktiv: <env-default>" when the user has no override.
    defaults: dict[str, str]


class SettingsWrite(BaseModel):
    llm_base_url: str = Field(default="", max_length=500)
    # null = leave key untouched; "" = clear; anything else = overwrite.
    llm_api_key: str | None = None
    llm_model: str = Field(default="", max_length=200)

    stt_base_url: str = Field(default="", max_length=500)
    stt_api_key: str | None = None
    stt_model: str = Field(default="", max_length=200)


def _mask_hint(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 4:
        return "•" * len(key)
    return f"…{key[-4:]}"


def _row_to_read(row: dict[str, Any] | None) -> SettingsRead:
    r = row or {}
    api_key = r.get("llm_api_key", "") or ""
    stt_key = r.get("stt_api_key", "") or ""
    return SettingsRead(
        llm_base_url=r.get("llm_base_url", "") or "",
        llm_api_key_set=bool(api_key),
        llm_api_key_hint=_mask_hint(api_key),
        llm_model=r.get("llm_model", "") or "",
        stt_base_url=r.get("stt_base_url", "") or "",
        stt_api_key_set=bool(stt_key),
        stt_api_key_hint=_mask_hint(stt_key),
        stt_model=r.get("stt_model", "") or "",
        defaults={
            "llm_base_url": env_settings.llm_base_url,
            "llm_model": env_settings.llm_model,
            "stt_base_url": env_settings.stt_base_url,
            "stt_model": env_settings.stt_model,
        },
    )


@router.get("/settings", response_model=SettingsRead)
async def get_settings(user: CurrentUser = Depends(get_current_user)) -> SettingsRead:
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            select llm_base_url, llm_api_key, llm_model,
                   stt_base_url, stt_api_key, stt_model
            from public.org_settings
            where org_id = $1
            """,
            user.org_id,
        )
    return _row_to_read(dict(row) if row else None)


class TestRequest(BaseModel):
    """Optional override values for testing without saving."""
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""


class TestResult(BaseModel):
    ok: bool
    detail: str
    model: str | None = None
    elapsed_ms: int | None = None


@router.post("/settings/test", response_model=TestResult)
async def test_settings(
    body: TestRequest | None = None,
    user: CurrentUser = Depends(get_current_user),
) -> TestResult:
    """Testet die LLM-Verbindung — Formularwerte schlagen die gespeicherten.

    Feldweise, nicht als Block: das Schlüssel-Feld trägt die Zusage „leer
    lassen, um den Schlüssel beizubehalten". Wurde der Block als Ganzes
    übernommen, sobald *irgendein* Feld gefüllt war, ging der Test mit
    leerem Schlüssel hinaus — und scheiterte an einem `Bearer `-Kopf, den
    httpx zu Recht ablehnt.
    """
    async with acquire() as conn:
        cfg = await load_llm_config(conn, user.org_id)

    def _waehle(aus_formular: str, gespeichert: str) -> str:
        return aus_formular.strip() or (gespeichert or "")

    use_url = _waehle(body.llm_base_url if body else "", cfg.base_url)
    use_key = _waehle(body.llm_api_key if body else "", cfg.api_key)
    use_model = _waehle(body.llm_model if body else "", cfg.model)

    if not use_url:
        return TestResult(ok=False, detail="Keine Endpunkt-URL konfiguriert.")

    payload = {
        "model": use_model or "test",
        "messages": [{"role": "user", "content": "Antworte mit OK."}],
        "max_tokens": 4,
        "stream": False,
    }
    started = asyncio.get_event_loop().time()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                resp = await client.post(
                    f"{use_url.rstrip('/')}/chat/completions",
                    json=payload,
                    headers=auth_header(use_key),
                )
    except httpx.ConnectError as exc:
        return TestResult(
            ok=False,
            detail=f"Endpunkt nicht erreichbar: {exc.__class__.__name__}.",
        )
    except httpx.TimeoutException:
        return TestResult(
            ok=False,
            detail="Zeitüberschreitung — Endpunkt antwortet nicht in 10 Sekunden.",
        )
    except Exception as exc:  # noqa: BLE001
        return TestResult(ok=False, detail=f"Unerwarteter Fehler: {exc}")

    elapsed_ms = int((asyncio.get_event_loop().time() - started) * 1000)

    if resp.status_code != 200:
        body = resp.text[:300]
        return TestResult(
            ok=False,
            detail=f"HTTP {resp.status_code}: {body}",
            elapsed_ms=elapsed_ms,
        )

    try:
        data = resp.json()
        used_model = data.get("model") or use_model
        # Any choices present = compatible OpenAI shape.
        if not data.get("choices"):
            return TestResult(
                ok=False,
                detail="Antwort hat kein `choices`-Feld (nicht OpenAI-kompatibel?).",
                elapsed_ms=elapsed_ms,
            )
    except ValueError:
        return TestResult(
            ok=False,
            detail="Antwort war kein gültiges JSON.",
            elapsed_ms=elapsed_ms,
        )

    return TestResult(
        ok=True,
        detail="Verbindung erfolgreich.",
        model=used_model,
        elapsed_ms=elapsed_ms,
    )


@router.put("/settings", response_model=SettingsRead)
async def put_settings(
    payload: SettingsWrite,
    user: CurrentUser = Depends(get_current_user),
) -> SettingsRead:
    async with acquire() as conn:
        async with conn.transaction():
            existing = await conn.fetchrow(
                """
                select llm_api_key, stt_api_key
                from public.org_settings where org_id = $1
                """,
                user.org_id,
            )

            def _schluessel(feld: str, neuer: str | None) -> str:
                """null im Payload = behalten; "" = löschen; sonst ersetzen."""
                if existing and neuer is None:
                    return existing[feld] or ""
                return neuer or ""

            api_key = _schluessel("llm_api_key", payload.llm_api_key)
            stt_key = _schluessel("stt_api_key", payload.stt_api_key)

            row = await conn.fetchrow(
                """
                insert into public.org_settings (
                    org_id, llm_base_url, llm_api_key, llm_model,
                    stt_base_url, stt_api_key, stt_model, updated_by
                )
                values ($1, $2, $3, $4, $5, $6, $7, $8)
                on conflict (org_id) do update set
                    llm_base_url = excluded.llm_base_url,
                    llm_api_key  = excluded.llm_api_key,
                    llm_model    = excluded.llm_model,
                    stt_base_url = excluded.stt_base_url,
                    stt_api_key  = excluded.stt_api_key,
                    stt_model    = excluded.stt_model,
                    updated_by   = excluded.updated_by
                returning llm_base_url, llm_api_key, llm_model,
                          stt_base_url, stt_api_key, stt_model
                """,
                user.org_id,
                payload.llm_base_url.strip(),
                api_key,
                payload.llm_model.strip(),
                payload.stt_base_url.strip(),
                stt_key,
                payload.stt_model.strip(),
                user.user_id,
            )
    return _row_to_read(dict(row))
