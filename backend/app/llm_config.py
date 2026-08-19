"""Per-org LLM configuration with env-default fallback.

The deployment ships with sane defaults baked into the env (LLM_BASE_URL,
LLM_API_KEY, LLM_MODEL). The user can override any field via the
Einstellungen UI, which writes into `public.org_settings`. Empty strings in
the DB mean "use the env default" — we never propagate empty strings to
the LLM call.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import asyncpg

from app.config import settings


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str

    @property
    def eingerichtet(self) -> bool:
        """Ohne Adresse ist nichts anzusprechen.

        Es gibt bewusst keinen Vorgabewert: jede geratene Adresse wäre bei
        einem anderen Kunden falsch (siehe app/config.py). Aufrufer prüfen
        das hier, statt in einen Verbindungsfehler zu laufen.
        """
        return bool(self.base_url.strip())

    @property
    def auth_header(self) -> dict[str, str]:
        """Kopfzeile für den Endpunkt — ohne Schlüssel gar keine.

        `Bearer ` mit leerem Wert ist kein gültiger Kopfwert; httpx lehnt
        ihn mit „Illegal header value" ab, bevor eine Verbindung zustande
        kommt. Seit v0.1.72 ist der leere Schlüssel der Normalfall (kein
        Vorgabewert mehr), und lokale Endpunkte verlangen ohnehin keinen.
        """
        return auth_header(self.api_key)


def auth_header(api_key: str) -> dict[str, str]:
    """Wie `LLMConfig.auth_header`, für Aufrufer ohne fertige Konfiguration."""
    key = (api_key or "").strip()
    return {"Authorization": f"Bearer {key}"} if key else {}


async def load_llm_config(conn: asyncpg.Connection, org_id: UUID) -> LLMConfig:
    row = await conn.fetchrow(
        """
        select llm_base_url, llm_api_key, llm_model
        from public.org_settings
        where org_id = $1
        """,
        org_id,
    )

    base_url = (row["llm_base_url"] if row else "") or settings.llm_base_url
    api_key = (row["llm_api_key"] if row else "") or settings.llm_api_key
    model = (row["llm_model"] if row else "") or settings.llm_model

    return LLMConfig(
        base_url=base_url.rstrip("/"),
        api_key=api_key,
        model=model,
    )
