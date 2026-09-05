"""Aufräumen — die beiden Fristen durchsetzen, die bisher nur dastanden.

Zwei Zusagen aus CLAUDE.md und dem Schema, die bis v0.1.81 niemand
eingelöst hat:

1. **Papierkorb-Frist.** „Soft-Delete + 30-Tage-Frist vor Hard-Delete."
   Gelöschte Besprechungen blieben unbegrenzt als Zeile liegen, ihre
   Tonaufnahme war dagegen sofort weg — die Frist galt also für das
   Falsche. Jetzt bleibt beides bis zum Ablauf und geht dann zusammen.

2. **Aufbewahrungsfrist für Aufnahmen.** `orgs.audio_retention_days`
   steht seit Migration 0001 in der Tabelle, mit Vorgabe 90, und wurde
   von keiner Zeile Code gelesen. Wer 90 Tage zusagt und unbegrenzt
   aufbewahrt, hat gegenüber einer Kanzlei ein Problem, kein Versäumnis.

**Die Fristen treffen Verschiedenes.** Die Papierkorb-Frist entfernt die
Besprechung ganz. Die Aufbewahrungsfrist entfernt nur die *Tonaufnahme* —
Transkript und Zusammenfassung bleiben lesbar. Das ist Absicht: das
Gesprächsprotokoll ist der Aktenbestandteil, die Tonspur das Rohmaterial.

`0` heißt bei beiden „aus": keine Papierkorbfrist bedeutet, dass sofort
endgültig gelöscht wird; keine Aufbewahrungsfrist bedeutet unbegrenzt.
Die zwei Nullen bedeuten also Gegenteiliges — deshalb steht es an beiden
Spalten als Kommentar in der Migration.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import asyncpg
from celery import shared_task

from app.config import settings
from app.db import dienst_kontext
from app.storage import delete_object
from app.worker import celery_app  # noqa: F401 -- side-effect: registers worker

log = logging.getLogger(__name__)


async def _connect() -> asyncpg.Connection:
    """Eigene Verbindung für diese Aufgabe — mit Dienst-Kontext.

    Hintergrundaufgaben haben keinen angemeldeten Nutzer. Unter der
    erzwungenen Zeilensicherheit aus Migration 0017 sähen sie ohne
    Kontext keine Zeile und könnten keine schreiben.
    """
    conn = await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
    )
    await dienst_kontext(conn)
    return conn


def _datei_weg(pfad: str | None) -> bool:
    """Datei entfernen. `True`, wenn danach nichts mehr da ist.

    Ein Fehlschlag beim Speicher darf die Zeile nicht freigeben: sonst
    entsteht genau der Zustand vom 19. August — eine Datei ohne
    Besprechung, die niemandem mehr gehört. Der nächste Lauf versucht es
    erneut.
    """
    if not pfad:
        return True
    try:
        delete_object(pfad)
        return True
    except FileNotFoundError:
        # Schon weg. Kein Grund, die Zeile ein weiteres Mal aufzuheben.
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Datei %s ließ sich nicht entfernen: %s", pfad, exc)
        return False


async def _papierkorb_leeren(conn: asyncpg.Connection) -> dict[str, int]:
    """Besprechungen entfernen, deren Papierkorb-Frist abgelaufen ist."""
    faellig = await conn.fetch(
        """
        select m.id, m.audio_path
        from public.meetings m
        join public.orgs o on o.id = m.org_id
        where m.deleted_at is not null
          and m.deleted_at + make_interval(days => o.trash_retention_days) <= now()
        """
    )

    entfernt = 0
    verschoben = 0
    for zeile in faellig:
        if not _datei_weg(zeile["audio_path"]):
            verschoben += 1
            continue
        # Transkript, Zusammenfassung, Abschnitte, Etiketten und
        # Sprecher-Zuordnungen hängen mit `on delete cascade` daran.
        await conn.execute("delete from public.meetings where id = $1", zeile["id"])
        entfernt += 1

    return {"entfernt": entfernt, "verschoben": verschoben}


async def _aufnahmen_altern(conn: asyncpg.Connection) -> dict[str, int]:
    """Tonaufnahmen entfernen, deren Aufbewahrungsfrist abgelaufen ist.

    Die Besprechung bleibt. `audio_path` wird geleert, damit jede
    bestehende Abfrage von selbst „keine Aufnahme" sieht, und
    `audio_deleted_at` hält fest, dass es eine gab — sonst wäre in der
    Oberfläche nicht zu unterscheiden, ob nie eine hochgeladen wurde oder
    ob die Frist sie geholt hat.
    """
    faellig = await conn.fetch(
        """
        select m.id, m.audio_path
        from public.meetings m
        join public.orgs o on o.id = m.org_id
        where m.audio_path is not null
          and m.audio_deleted_at is null
          and o.audio_retention_days > 0
          and m.recorded_at + make_interval(days => o.audio_retention_days) <= now()
        """
    )

    entfernt = 0
    verschoben = 0
    for zeile in faellig:
        if not _datei_weg(zeile["audio_path"]):
            verschoben += 1
            continue
        await conn.execute(
            """
            update public.meetings
            set audio_path = null, audio_deleted_at = now(), updated_at = now()
            where id = $1
            """,
            zeile["id"],
        )
        entfernt += 1

    return {"entfernt": entfernt, "verschoben": verschoben}


async def _durchlauf() -> dict[str, Any]:
    conn = await _connect()
    try:
        papierkorb = await _papierkorb_leeren(conn)
        aufnahmen = await _aufnahmen_altern(conn)
    finally:
        await conn.close()

    ergebnis = {"papierkorb": papierkorb, "aufnahmen": aufnahmen}
    if papierkorb["entfernt"] or aufnahmen["entfernt"]:
        log.info("Aufräumen: %s", ergebnis)
    return ergebnis


@shared_task(name="aufraeumen")
def aufraeumen() -> dict[str, Any]:
    """Täglich vom Beat gerufen (siehe `app.worker.beat_schedule`).

    Der Lauf ist absichtlich für sich stehend und wiederholbar: er hält
    keinen Zustand, und was er beim Speicherfehler liegen lässt, nimmt
    der nächste Lauf mit.
    """
    return asyncio.run(_durchlauf())
