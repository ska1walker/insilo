"""Konfiguration neben dem Audio ablegen — damit ein Backup eine Datei ist.

**Warum es das gibt.** Am 19.8.2026 wurde Insilo über den Markt einmal
deinstalliert und neu installiert. Die Tonaufnahmen unter `/app/data`
überlebten das (Olares behält `appData`), die Datenbank nicht: Olares legt
sie beim Deinstallieren an. Damit waren Einstellungen, Vorlagen-Anpassungen,
Webhooks und der Sprecherkatalog weg — und schlimmer, die neue
Organisation bekam eine neue Kennung. Audio liegt aber unter
`audio/<org-id>/`, also zeigten zehn vorhandene Aufnahmen ins Leere.

**Was hier passiert.** Nach jeder Änderung an der Konfiguration wird sie
als eine Datei neben das Audio geschrieben. Beim Start liest Insilo sie
zurück, wenn die Datenbank leer ist. Ein Backup von `/app/data` enthält
damit alles, was zum Wiederherstellen nötig ist, und die Org-Kennung
bleibt dieselbe — die alten Aufnahmen finden wieder Anschluss.

**Die Datenbank bleibt die Wahrheit.** Diese Datei ist ein Abzug, keine
zweite Quelle. Gelesen wird sie nur, wenn nichts da ist, das sie
überschreiben könnte.

**Sie enthält Zugangsdaten** — API-Schlüssel für Sprachmodell und
Spracherkennung, Webhook-Geheimnisse, Hashes der Zugriffsschlüssel. Das
ist Absicht: eine Wiederherstellung, nach der die Hälfte neu einzutragen
ist, hilft niemandem. Die Datei liegt deshalb mit Rechten 0600 und sagt in
ihrem Kopf, was sie ist. Wer `/app/data` sichert, sichert Zugangsdaten
mit — das gehört in die Betriebsanleitung, nicht in eine Fußnote.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any
from uuid import UUID

import asyncpg

from app.config import settings

log = logging.getLogger(__name__)

# Neben dem Audio, nicht darin: `audio/` gehört den Aufnahmen. Der Pfad
# wird aus dem Audio-Verzeichnis abgeleitet, nicht aus `APP_DATA_DIR`:
# diese Variable trägt auf Olares den *Host*-Pfad des Volumes
# (`.Values.userspace.appData`), den es im Container nicht gibt.
DATEI = Path(settings.storage_local_path).parent / "konfiguration.json"

SCHEMA = 1


def _j(wert: Any) -> Any:
    """UUID und Datum in etwas verwandeln, das JSON verträgt."""
    if isinstance(wert, UUID):
        return str(wert)
    if hasattr(wert, "isoformat"):
        return wert.isoformat()
    return wert


def _jsonb(wert: Any) -> Any:
    """asyncpg liefert JSONB als Zeichenkette — hier wird wieder Struktur daraus.

    Ohne das landete beim Wiederherstellen `json.dumps("{\"a\": 1}")` in
    der Spalte, also eine Zeichenkette statt eines Objekts.
    """
    if isinstance(wert, str):
        with suppress(ValueError):
            return json.loads(wert)
    return wert


def _zeile(row: asyncpg.Record | None) -> dict[str, Any] | None:
    return {k: _j(v) for k, v in dict(row).items()} if row is not None else None


def _zeilen(rows: list[asyncpg.Record]) -> list[dict[str, Any]]:
    return [{k: _j(v) for k, v in dict(r).items()} for r in rows]


async def einsammeln(conn: asyncpg.Connection) -> dict[str, Any]:
    """Alles, was Konfiguration ist — und nichts, was Inhalt ist.

    Besprechungen, Transkripte und Zusammenfassungen bleiben draußen: das
    sind Gesprächsinhalte, sie gehören in ein Datenbank-Backup, nicht in
    eine Datei neben dem Audio.
    """
    org = await conn.fetchrow(
        """
        select id, name, slug, industry, settings, audio_retention_days
        from public.orgs where deleted_at is null
        order by created_at limit 1
        """
    )
    if org is None:
        return {}

    org_id = org["id"]
    org_daten = _zeile(org) or {}
    org_daten["settings"] = _jsonb(org_daten.get("settings"))
    daten: dict[str, Any] = {
        "schema": SCHEMA,
        "org": org_daten,
        "users": _zeilen(await conn.fetch(
            """
            select u.olares_username, u.email, u.display_name, u.ui_locale,
                   r.role::text as role
            from public.users u
            join public.user_org_roles r on r.user_id = u.id
            where r.org_id = $1 and u.deleted_at is null
            order by u.created_at
            """, org_id)),
        "einstellungen": _zeile(await conn.fetchrow(
            """
            select llm_base_url, llm_api_key, llm_model,
                   stt_base_url, stt_api_key, stt_model, ui_locale
            from public.org_settings where org_id = $1
            """, org_id)),
        "webhooks": _zeilen(await conn.fetch(
            """
            select url, secret, events, is_active, description, trigger_mode
            from public.org_webhooks where org_id = $1 order by created_at
            """, org_id)),
        "vorlagen_anpassungen": [
            {**v,
             "custom_fields": _jsonb(v.get("custom_fields")),
             "system_prompts": _jsonb(v.get("system_prompts"))}
            for v in _zeilen(await conn.fetch(
                """
                select template_id, display_name, display_description,
                       custom_fields, system_prompts
                from public.template_customizations where org_id = $1
                """, org_id))
        ],
        "sprecher": _zeilen(await conn.fetch(
            """
            select id, display_name, description, is_self,
                   voiceprint::text as voiceprint, sample_count
            from public.org_speakers where org_id = $1 order by created_at
            """, org_id)),
        "zugriffsschluessel": _zeilen(await conn.fetch(
            """
            select name, key_prefix, key_hash, scopes, created_at, revoked_at
            from public.api_keys where org_id = $1 order by created_at
            """, org_id)),
    }
    return daten


async def sichern(conn: asyncpg.Connection) -> bool:
    """Abzug schreiben. Atomar, damit ein Absturz keine halbe Datei hinterlässt."""
    daten = await einsammeln(conn)
    if not daten:
        return False

    kopf = {
        "_hinweis": (
            "Abzug der Insilo-Konfiguration. Wird beim Start gelesen, wenn "
            "die Datenbank leer ist — etwa nach einer Neuinstallation. "
            "ENTHÄLT ZUGANGSDATEN (API-Schlüssel, Webhook-Geheimnisse). "
            "Wer dieses Verzeichnis sichert, sichert sie mit."
        ),
        **daten,
    }

    DATEI.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(DATEI.parent), prefix=".konfiguration-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(kopf, f, ensure_ascii=False, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, DATEI)
    except BaseException:
        with suppress(OSError):
            os.unlink(tmp)
        raise
    return True



async def sichern_leise(conn: asyncpg.Connection) -> None:
    """Wie `sichern`, schluckt aber Fehler.

    Ein nicht schreibbarer Abzug darf keine Einstellung scheitern lassen:
    die Änderung steht bereits in der Datenbank, und die ist die Wahrheit.
    """
    try:
        await sichern(conn)
    except Exception as exc:  # noqa: BLE001
        log.warning("Konfigurations-Abzug nicht geschrieben: %s", exc)


async def wiederherstellen(conn: asyncpg.Connection) -> bool:
    """Abzug zurücklesen — nur in eine leere Datenbank.

    „Leer" heißt: keine Organisation. Sobald eine existiert, ist die
    Datenbank die Wahrheit und wird nicht angefasst; sonst würde ein alter
    Abzug laufende Einstellungen überschreiben.
    """
    if not DATEI.exists():
        return False

    vorhanden = await conn.fetchval(
        "select count(*) from public.orgs where deleted_at is null"
    )
    if vorhanden:
        return False

    try:
        daten = json.loads(DATEI.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        log.error("Konfigurations-Abzug unlesbar, übersprungen: %s", exc)
        return False

    if daten.get("schema") != SCHEMA:
        log.warning(
            "Konfigurations-Abzug hat Schema %s, erwartet %s — übersprungen",
            daten.get("schema"), SCHEMA,
        )
        return False

    org = daten.get("org") or {}
    if not org.get("id"):
        return False

    async with conn.transaction():
        # Die Kennung wird bewusst mitgenommen: Audio liegt unter
        # audio/<org-id>/, eine neue Kennung würde alle Aufnahmen abhängen.
        await conn.execute(
            """
            insert into public.orgs (id, name, slug, industry, settings, audio_retention_days)
            values ($1, $2, $3, $4, $5::jsonb, $6)
            on conflict (id) do nothing
            """,
            UUID(org["id"]), org.get("name") or "Organisation",
            org.get("slug") or "org", org.get("industry"),
            json.dumps(org.get("settings") or {}),
            org.get("audio_retention_days") or 90,
        )
        org_id = UUID(org["id"])

        for u in daten.get("users") or []:
            row = await conn.fetchrow(
                """
                insert into public.users (olares_username, email, display_name, ui_locale)
                values ($1, $2, $3, $4)
                on conflict (olares_username) do update set display_name = excluded.display_name
                returning id
                """,
                u["olares_username"], u.get("email"), u.get("display_name"),
                u.get("ui_locale"),
            )
            await conn.execute(
                """
                insert into public.user_org_roles (user_id, org_id, role)
                values ($1, $2, $3::public.user_role)
                on conflict (user_id, org_id) do nothing
                """,
                row["id"], org_id, u.get("role") or "owner",
            )

        e = daten.get("einstellungen")
        if e:
            await conn.execute(
                """
                insert into public.org_settings (
                    org_id, llm_base_url, llm_api_key, llm_model,
                    stt_base_url, stt_api_key, stt_model, ui_locale)
                values ($1,$2,$3,$4,$5,$6,$7,$8)
                on conflict (org_id) do nothing
                """,
                org_id, e.get("llm_base_url") or "", e.get("llm_api_key") or "",
                e.get("llm_model") or "", e.get("stt_base_url") or "",
                e.get("stt_api_key") or "", e.get("stt_model") or "",
                e.get("ui_locale") or "de",
            )

        for w in daten.get("webhooks") or []:
            await conn.execute(
                """
                insert into public.org_webhooks (
                    org_id, url, secret, events, is_active, description, trigger_mode)
                values ($1,$2,$3,$4,$5,$6,$7)
                """,
                org_id, w["url"], w["secret"], w.get("events") or ["meeting.ready"],
                w.get("is_active", True), w.get("description") or "",
                w.get("trigger_mode") or "automatic",
            )

        for v in daten.get("vorlagen_anpassungen") or []:
            # Nur, wenn es die Vorlage noch gibt — sonst läuft der
            # Fremdschlüssel auf. Werksvorlagen legt seed.sql an.
            await conn.execute(
                """
                insert into public.template_customizations (
                    org_id, template_id, display_name, display_description,
                    custom_fields, system_prompts)
                select $1, $2, $3, $4, $5::jsonb, $6::jsonb
                where exists (select 1 from public.templates where id = $2)
                on conflict (org_id, template_id) do nothing
                """,
                org_id, UUID(v["template_id"]),
                v.get("display_name"), v.get("display_description"),
                json.dumps(v.get("custom_fields") or []),
                json.dumps(v.get("system_prompts") or {}),
            )

        for sp in daten.get("sprecher") or []:
            await conn.execute(
                """
                insert into public.org_speakers (
                    id, org_id, display_name, description, is_self, voiceprint, sample_count)
                values ($1,$2,$3,$4,$5,$6::vector,$7)
                on conflict (id) do nothing
                """,
                UUID(sp["id"]), org_id, sp["display_name"], sp.get("description") or "",
                sp.get("is_self", False), sp.get("voiceprint"), sp.get("sample_count") or 0,
            )

        for k in daten.get("zugriffsschluessel") or []:
            await conn.execute(
                """
                insert into public.api_keys (
                    org_id, name, key_prefix, key_hash, scopes, revoked_at)
                values ($1,$2,$3,$4,$5,$6::timestamptz)
                """,
                org_id, k["name"], k["key_prefix"], k["key_hash"],
                k.get("scopes") or ["read:meetings"], k.get("revoked_at"),
            )

    log.info(
        "Konfiguration aus %s wiederhergestellt (Org %s, %d Sprecher, %d Webhooks)",
        DATEI, org_id, len(daten.get("sprecher") or []), len(daten.get("webhooks") or []),
    )
    return True
