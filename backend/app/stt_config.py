"""Spracherkennung: mitgelieferter Dienst oder externer Endpunkt.

Bis v0.1.76 war die Spracherkennung fest verdrahtet — der Whisper-Dienst im
eigenen Namespace. Deshalb galt „kein Audio verlässt die Box" ohne
Ausnahme, in jeder Konfiguration.

Seit v0.1.77 lässt sich stattdessen ein OpenAI-kompatibler STT-Server
eintragen. Das ist ein Zugewinn (eine GPU-gestützte Instanz transkribiert
um Größenordnungen schneller als Whisper auf der CPU) und zugleich der
Punkt, an dem die Zusage genauer werden muss: **jetzt kann Audio die Box
verlassen**, und der Datenschutz-Nachweis muss das benennen.

Wie beim Sprachmodell gibt es bewusst keinen Vorgabewert. Leer heißt: der
mitgelieferte Dienst übernimmt, und die Zusage hält ohne Sternchen.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import asyncpg

from app.config import settings
from app.llm_config import auth_header


@dataclass(frozen=True)
class STTConfig:
    base_url: str
    api_key: str
    model: str

    @property
    def eingerichtet(self) -> bool:
        """Ist ein externer Endpunkt eingetragen?

        Nein heißt nicht „kaputt", sondern „der mitgelieferte Dienst
        transkribiert" — der Normalfall und der datensparsamste.
        """
        return bool(self.base_url.strip())

    @property
    def auth_header(self) -> dict[str, str]:
        """Ohne Schlüssel gar keine Kopfzeile — siehe llm_config."""
        return auth_header(self.api_key)


async def load_stt_config(conn: asyncpg.Connection, org_id: UUID) -> STTConfig:
    row = await conn.fetchrow(
        """
        select stt_base_url, stt_api_key, stt_model
        from public.org_settings
        where org_id = $1
        """,
        org_id,
    )

    base_url = (row["stt_base_url"] if row else "") or settings.stt_base_url
    api_key = (row["stt_api_key"] if row else "") or settings.stt_api_key
    model = (row["stt_model"] if row else "") or settings.stt_model

    return STTConfig(
        base_url=base_url.strip().rstrip("/"),
        api_key=api_key.strip(),
        model=model.strip(),
    )
