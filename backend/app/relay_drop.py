"""Meeting-Zusammenfassungen als Markdown-Datei in ein gemeinsames Verzeichnis.

**Warum es das gibt.** Die Ablage legt das Markdown neben der Aufnahme in
den Insilo-eigenen Speicher — Relay, die Mail-App, sieht den nicht:
andere App, anderer Namespace. Dieses Modul legt die Zusammenfassung
zusätzlich in ein Verzeichnis, das beide Apps sehen (Olares appCommon,
`MEETING_EXPORT_DIR`). Relay pollt es und zeigt die Meetings in seinem
eigenen „Meetings"-Bereich.

**Contract mit Relay (schema 1).** Eine Datei pro Besprechung, flach,
Dateiname nur ASCII (Datum + UUID-Vorlauf), Titel und Metadaten in der
Frontmatter, Body ist das kanonische Markdown ohne Transkript:

    2026-09-12T14_30--a1b2c3d4.md
    ---
    insilo_id: "..."
    title: "..."
    recorded_at: "..."
    ...
    ---
    <render_meeting_markdown, include_transcript=False>

Die Frontmatter ist ein Mini-Dialekt, den Relay ohne YAML-Lib parst:
eine `key: value`-Zeile pro Schlüssel, keine mehrzeiligen Werte,
Listen als JSON-Arrays. Relay liest das Verzeichnis read-only; wer
hier schreibt, ist Insilo.

**Abgeleitet, nicht Quelle.** Wie die Ablage: die Datenbank bleibt die
Wahrheit, die Datei wird neu geschrieben, wenn sich der Inhalt ändert,
und sie darf jederzeit fehlen, ohne dass etwas kaputtgeht. Ein
Schreibfehlschlag hält weder die Verarbeitung noch eine Änderung auf.

**Sie verschwindet mit der Besprechung.** Beim endgültigen Löschen geht
sie mit.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC
from pathlib import Path
from typing import Any
from uuid import UUID

import asyncpg

from app.ablage import _einsammeln
from app.config import settings
from app.exports.markdown import render_meeting_markdown

log = logging.getLogger(__name__)

SCHEMA = 1


def _verzeichnis() -> Path | None:
    """Das Drop-Verzeichnis, oder `None`, wenn der Export deaktiviert ist."""
    roh = (settings.meeting_export_dir or "").strip()
    return Path(roh) if roh else None


def dateiname(besprechung: dict[str, Any]) -> str:
    """`<YYYY-MM-DD>T<HH>_<MM>--<id8>.md`, UTC aus `recorded_at`.

    Nur ASCII: der Titel lebt in der Frontmatter, nicht im Namen.
    """
    zeit = besprechung["recorded_at"]
    if zeit.tzinfo is None:
        zeit = zeit.replace(tzinfo=UTC)
    else:
        zeit = zeit.astimezone(UTC)
    stempel = zeit.strftime("%Y-%m-%dT%H_%M")
    return f"{stempel}--{str(besprechung['id'])[:8]}.md"


def _zitat(wert: Any) -> str:
    """Frontmatter-Skalar: Anführungszeichen, keine Zeilenumbrüche."""
    text = str(wert or "").replace('"', "'").replace("\n", " ").strip()
    return f'"{text}"'


def _liste(werte: list[str]) -> str:
    """Liste als JSON-Array — Relay parst es mit seiner JSON-Lib."""
    return json.dumps([str(w) for w in werte if str(w).strip()], ensure_ascii=False)


def _frontmatter(
    besprechung: dict[str, Any],
    transkript: dict[str, Any] | None,
    etiketten: list[dict[str, Any]],
) -> str:
    sprecher = (transkript or {}).get("speakers") or []
    namen = [str(s.get("name")) for s in sprecher if s.get("name")]
    dauer = int(besprechung.get("duration_sec") or 0)
    dauer_min = max(1, round(dauer / 60)) if dauer else 0
    return "\n".join(
        [
            "---",
            f"insilo_id: {_zitat(besprechung['id'])}",
            f"title: {_zitat(besprechung.get('title'))}",
            f"recorded_at: {_zitat(besprechung['recorded_at'].isoformat())}",
            f"duration_min: {dauer_min}",
            f"language: {_zitat(besprechung.get('language') or 'de')}",
            f"participants: {_liste(namen)}",
            f"tags: {_liste([t.get('name') for t in etiketten])}",
            f"template: {_zitat(besprechung.get('template_name') or '')}",
            "source_url: ''",
            f"schema: {SCHEMA}",
            "---",
            "",
        ]
    )


def _inhalt(
    besprechung: dict[str, Any],
    transkript: dict[str, Any] | None,
    zusammenfassung: dict[str, Any],
    etiketten: list[dict[str, Any]],
) -> str:
    """Frontmatter + kanonisches Markdown, ohne Transkript.

    Das Transkript bleibt in Insilo: Relay braucht die Zusammenfassung,
    und der Wortlaut gehört nicht in ein Verzeichnis, das jede App mit
    dem Recht sieht.
    """
    kopf = _frontmatter(besprechung, transkript, etiketten)
    body = render_meeting_markdown(
        meeting=besprechung,
        transcript=transkript,
        summary=zusammenfassung,
        tags=etiketten,
        template_name=besprechung.get("template_name"),
        include_transcript=False,
    )
    return kopf + body


def _atomar_schreiben(ziel: Path, data: bytes) -> None:
    """Neben die Ziel-Datei schreiben, dann umbenennen.

    Atomar: Relay sieht nie eine halbe Datei, und ein abgebrochener
    Lauf hinterlässt nur `.tmp`, das Relay ignoriert. Die Datei ist
    klein (ein Markdown-Dokument), der synchrone Schreibzug ist
    verschwindend.
    """
    ziel.parent.mkdir(parents=True, exist_ok=True)
    provisorisch = ziel.parent / (ziel.name + ".tmp")
    with open(provisorisch, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(provisorisch, ziel)


async def schreiben(conn: asyncpg.Connection, meeting_id: UUID) -> str | None:
    """Die Datei neu schreiben, wenn es eine Zusammenfassung gibt.

    Gibt den Dateinamen zurück oder `None` (deaktiviert, keine Zeile,
    keine Zusammenfassung). Wirft nicht — wie die Ablage.
    """
    verzeichnis = _verzeichnis()
    if verzeichnis is None:
        return None

    try:
        teile = await _einsammeln(conn, meeting_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("Relay-Export für %s: Lesen fehlgeschlagen: %s", meeting_id, exc)
        return None
    if teile is None:
        return None
    besprechung, transkript, zusammenfassung, etiketten = teile
    if not zusammenfassung:
        return None

    name = dateiname(besprechung)
    try:
        _atomar_schreiben(
            verzeichnis / name,
            _inhalt(besprechung, transkript, zusammenfassung, etiketten).encode("utf-8"),
        )
        return name
    except Exception as exc:  # noqa: BLE001
        log.warning("Relay-Export %s nicht geschrieben: %s", name, exc)
        return None


def fehlt(meeting_id: UUID | str) -> bool:
    """`True`, wenn der Export an ist und die Datei nicht liegt.

    Für den nächtlichen Nachzug-Lauf: wie die Ablage-Datei gilt hier
    „heilt Fehlendes, nicht Veraltetes".
    """
    verzeichnis = _verzeichnis()
    if verzeichnis is None:
        return False
    vorlauf = str(meeting_id)[:8]
    try:
        return not any(verzeichnis.glob(f"*--{vorlauf}.md"))
    except Exception:  # noqa: BLE001
        return False


def entfernen(meeting_id: UUID | str) -> bool:
    """Die Datei entfernen. `True`, wenn danach keine mehr da ist.

    Wie `ablage.entfernen`: eine fehlende Datei ist kein Fehler.
    """
    verzeichnis = _verzeichnis()
    if verzeichnis is None:
        return True
    vorlauf = str(meeting_id)[:8]
    try:
        for datei in verzeichnis.glob(f"*--{vorlauf}.md"):
            datei.unlink()
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Relay-Export %s ließ sich nicht entfernen: %s", vorlauf, exc)
        return False


__all__ = ["SCHEMA", "dateiname", "entfernen", "fehlt", "schreiben"]
