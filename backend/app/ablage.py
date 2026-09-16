"""Transkript und Zusammenfassung als Markdown neben die Tonaufnahme legen.

**Warum es das gibt.** Bis hierher lag im Datenverzeichnis nur die
Tonspur. Wer die Besprechung außerhalb von Insilo brauchte — in der
Akte, im Dokumentenmanagement, in einem Ordner, den ohnehin jemand
sichert — kam nur über die Oberfläche oder die Schnittstelle daran. Die
Datei daneben schließt das: sie ist lesbar, ohne dass ein Dienst läuft,
und ein Backup von `/app/data` trägt den Inhalt mit.

**Zwei Dateien je Besprechung**, neben der Aufnahme und mit demselben
Stamm, damit sie in einer Auflistung beieinanderstehen:

    audio/<org-id>/<meeting-id>.webm
    audio/<org-id>/<meeting-id>.transkript.md
    audio/<org-id>/<meeting-id>.zusammenfassung.md

Der Titel steht in der Datei (Kopfzeile und `# Überschrift`), nicht im
Namen: er lässt sich ändern, und zwei Besprechungen dürfen gleich heißen.

**Abgeleitet, nicht Quelle.** Die Datenbank bleibt die Wahrheit. Diese
Dateien werden neu geschrieben, wenn sich der Inhalt ändert, und sie
dürfen jederzeit fehlen, ohne dass etwas kaputtgeht — ein
Schreibfehlschlag hält weder die Verarbeitung noch eine Änderung auf.

**Sie verschwinden mit der Besprechung.** Beim endgültigen Löschen gehen
sie mit; sonst bliebe der Gesprächsinhalt auf der Platte liegen,
nachdem jemand ausdrücklich „endgültig entfernen" gedrückt hat. Die
**Aufbewahrungsfrist für Aufnahmen** lässt sie dagegen stehen: die
entfernt die Tonspur als Rohmaterial und hält Transkript und
Zusammenfassung ausdrücklich fest.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

import asyncpg

from app import weitergabe
from app.exports.markdown import render_meeting_markdown
from app.storage import delete_object, upload_bytes

log = logging.getLogger(__name__)

SUFFIX_TRANSKRIPT = ".transkript.md"
SUFFIX_ZUSAMMENFASSUNG = ".zusammenfassung.md"

SUFFIXE = (SUFFIX_TRANSKRIPT, SUFFIX_ZUSAMMENFASSUNG)

# Vorgänge aus `audit._REGELN`, nach denen die Dateien nicht mehr stimmen.
# Die Middleware in `main.py` liest sie hier ab — eine Stelle, nicht fünf
# Endpunkte. Was die Verarbeitung selbst anstößt (Transkription,
# Zusammenfassung), schreibt direkt in den Aufgaben; hierher gehören nur
# die Änderungen von Hand.
AUSLOESER: frozenset[str] = frozenset({
    "meeting.update",            # Titel geändert
    "meeting.tag",
    "meeting.untag",
    "transcript.rename_speakers",
    "meeting.assign_speaker",
})

# Markdown ist Text; der Typ steht hier, damit der S3-Rücken ihn nicht
# als application/octet-stream ablegt und ein Browser ihn zum Herunterladen
# statt zum Lesen anbietet.
TYP = "text/markdown; charset=utf-8"


def schluessel(org_id: UUID | str, meeting_id: UUID | str, suffix: str) -> str:
    return f"{org_id}/{meeting_id}{suffix}"


def _jsonb(wert: Any) -> Any:
    """asyncpg gibt jsonb als Zeichenkette zurück, wenn kein Codec gesetzt ist.

    Dieselbe Falle wie beim Konfigurations-Abzug (HANDOFF, v0.1.81) und
    im Protokoll-Leser. Ohne das bekäme der Renderer eine Zeichenkette,
    wo er eine Liste erwartet, und lieferte eine Datei ohne Abschnitte.
    """
    if isinstance(wert, str):
        try:
            return json.loads(wert)
        except ValueError:
            return None
    return wert


async def _einsammeln(
    conn: asyncpg.Connection, meeting_id: UUID
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None, list[dict[str, Any]]] | None:
    """Alles, was in die beiden Dateien gehört. `None`, wenn es die Zeile nicht gibt."""
    besprechung = await conn.fetchrow(
        f"""
        select m.id, m.org_id, m.title, m.recorded_at, m.duration_sec,
               m.language, t.name as template_name,
               {weitergabe.SPALTE}
        from public.meetings m
        left join public.templates t on t.id = m.template_id
        where m.id = $1
        """,
        meeting_id,
    )
    if besprechung is None:
        return None

    transkript = await conn.fetchrow(
        """
        select segments, speakers, full_text, language
        from public.transcripts where meeting_id = $1
        """,
        meeting_id,
    )
    zusammenfassung = await conn.fetchrow(
        """
        select content, llm_model
        from public.summaries
        where meeting_id = $1 and is_current = true
        order by created_at desc limit 1
        """,
        meeting_id,
    )
    etiketten = await conn.fetch(
        """
        select t.name, t.color
        from public.meeting_tags mt
        join public.tags t on t.id = mt.tag_id
        where mt.meeting_id = $1
        order by t.name asc
        """,
        meeting_id,
    )

    t = None
    if transkript is not None:
        t = {
            "segments": _jsonb(transkript["segments"]) or [],
            "speakers": _jsonb(transkript["speakers"]) or [],
            "full_text": transkript["full_text"],
            "language": transkript["language"],
        }

    z = None
    if zusammenfassung is not None:
        inhalt = _jsonb(zusammenfassung["content"])
        if inhalt:
            z = {"content": inhalt, "llm_model": zusammenfassung["llm_model"]}

    return dict(besprechung), t, z, [dict(r) for r in etiketten]


async def schreiben(conn: asyncpg.Connection, meeting_id: UUID) -> list[str]:
    """Die Dateien neu schreiben, soweit es Inhalt gibt. Gibt die Schlüssel zurück.

    Wirft nicht: die Datenbank hat den Inhalt bereits, und eine volle
    oder klemmende Platte darf weder eine Aufnahme noch eine Umbenennung
    scheitern lassen. Was schiefging, steht im Protokoll des Dienstes.

    Ohne Transkript wird keine Transkript-Datei geschrieben, ohne
    Zusammenfassung keine Zusammenfassungs-Datei — eine Datei, die nur
    aus einer Kopfzeile besteht, behauptet Inhalt, den es nicht gibt.
    """
    try:
        teile = await _einsammeln(conn, meeting_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("Markdown-Ablage für %s: Lesen fehlgeschlagen: %s", meeting_id, exc)
        return []

    if teile is None:
        return []
    besprechung, transkript, zusammenfassung, etiketten = teile

    org_id = besprechung["org_id"]
    vorlage = besprechung.get("template_name")
    geschrieben: list[str] = []

    aufgaben: list[tuple[str, str]] = []
    if transkript and (transkript.get("segments") or transkript.get("full_text")):
        aufgaben.append((
            SUFFIX_TRANSKRIPT,
            render_meeting_markdown(
                meeting=besprechung,
                transcript=transkript,
                summary=None,
                tags=etiketten,
                template_name=vorlage,
                include_transcript=True,
            ),
        ))
    if zusammenfassung:
        aufgaben.append((
            SUFFIX_ZUSAMMENFASSUNG,
            render_meeting_markdown(
                meeting=besprechung,
                transcript=transkript,
                summary=zusammenfassung,
                tags=etiketten,
                template_name=vorlage,
                # Die Zusammenfassung soll die Zusammenfassung sein. Wer
                # den Wortlaut braucht, nimmt die Datei daneben.
                include_transcript=False,
            ),
        ))

    for suffix, text in aufgaben:
        k = schluessel(org_id, meeting_id, suffix)
        try:
            upload_bytes(k, text.encode("utf-8"), TYP)
            geschrieben.append(k)
        except Exception as exc:  # noqa: BLE001
            log.warning("Markdown-Ablage %s nicht geschrieben: %s", k, exc)

    return geschrieben


def entfernen(org_id: UUID | str, meeting_id: UUID | str) -> bool:
    """Beide Dateien entfernen. `True`, wenn danach keine mehr da ist.

    Wie `_datei_weg` im Aufräumlauf: eine fehlende Datei ist kein Fehler,
    ein klemmender Speicher schon — dann bleibt die Zeile stehen und der
    nächste Lauf versucht es erneut.
    """
    sauber = True
    for suffix in SUFFIXE:
        k = schluessel(org_id, meeting_id, suffix)
        try:
            delete_object(k)
        except FileNotFoundError:
            pass
        except Exception as exc:  # noqa: BLE001
            log.warning("Markdown-Ablage %s ließ sich nicht entfernen: %s", k, exc)
            sauber = False
    return sauber


__all__ = [
    "AUSLOESER",
    "SUFFIXE",
    "SUFFIX_TRANSKRIPT",
    "SUFFIX_ZUSAMMENFASSUNG",
    "entfernen",
    "schluessel",
    "schreiben",
]
