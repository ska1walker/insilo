"""Besprechungen einsammeln, die in einem Zwischenzustand hängen geblieben sind.

**Der Anlass.** Läuft die Erkennung in Celerys *hartes* Zeitlimit, wird
der Arbeitsprozess getötet. Kein `except` kommt mehr zum Zug, also setzt
niemand den Zustand auf „fehlgeschlagen" — die Besprechung steht auf
`transcribing`, für immer. In der Oberfläche dreht sich ein Rädchen, das
sich nie wieder bewegt; in der Datenbank sieht es aus wie laufende
Arbeit. Dasselbe passiert, wenn der Worker-Pod währenddessen neu startet
(Knoten aus, Speichergrenze, Markt-Upgrade).

Das weiche Zeitlimit fängt den Normalfall ab und liegt fünf Minuten vor
dem harten. Dieser Lauf ist für alles, was am weichen Limit vorbeikommt.

**Wie er entscheidet.** Es gibt keinen verlässlichen Weg, von außen zu
fragen, ob eine Celery-Aufgabe noch läuft — mit `task_acks_late` hängt
die Nachricht möglicherweise noch in der Warteschlange, und ein Blick in
die Worker-Statistik weiß nichts über einen Pod, den es nicht mehr gibt.
Also entscheidet die Zeit: `updated_at` wird beim Eintritt in jeden
Zustand gesetzt, und eine Aufgabe, die länger als ihr eigenes hartes
Limit plus Puffer nichts mehr geschrieben hat, läuft nicht mehr. Der
Puffer ist großzügig — lieber eine Viertelstunde zu spät aufgeräumt als
eine Aufgabe für tot erklärt, die noch arbeitet.

**Was er nicht tut.** Er stößt nichts von selbst neu an. Was eben noch an
einem Zeitlimit gescheitert ist, scheitert beim zweiten Mal genauso,
solange sich nichts an der Einrichtung geändert hat — und jeder Versuch
belegt den einen Worker für Stunden. Der Nutzer bekommt stattdessen eine
Besprechung, die ehrlich „fehlgeschlagen" sagt, die Aufnahme unversehrt
daneben und einen Knopf zum erneuten Anstoßen.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import asyncpg
from celery import shared_task

from app.config import settings
from app.db import dienst_kontext
from app.verarbeitungszeit import hartes_limit
from app.worker import celery_app  # noqa: F401 -- side-effect: registers worker

log = logging.getLogger(__name__)

# Zustände, in denen eine Besprechung nur vorübergehend steht. Bleibt sie
# darin stehen, arbeitet niemand mehr an ihr.
#
# `queued` gehört dazu: eine Besprechung, deren Aufgabe nie bei einem
# Worker ankam (Warteschlange weg, Worker nie gestartet), wartet sonst
# ebenso endlos. `draft` und `uploading` gehören *nicht* dazu — die
# gehören dem Browser, nicht dem Worker.
SCHWEBENDE_ZUSTAENDE = ("queued", "transcribing", "summarizing", "embedding")

# Zusätzlich zum harten Limit, bevor eine Aufgabe für tot erklärt wird.
PUFFER_SEC = 15 * 60

MELDUNG = (
    "Die Verarbeitung wurde unterbrochen und läuft nicht mehr — meist, "
    "weil sie das Zeitlimit überschritten hat oder der Dienst neu "
    "gestartet wurde. Die Aufnahme liegt unversehrt auf der Box und "
    "lässt sich erneut verarbeiten."
)


async def _connect() -> asyncpg.Connection:
    """Eigene Verbindung mit Dienst-Kontext — wie in `aufraeumen`.

    Ohne den Kontext sähe der Lauf unter der erzwungenen Zeilensicherheit
    aus Migration 0017 keine einzige Zeile und meldete fröhlich, es gebe
    nichts zu tun.
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


def grenze_sekunden() -> int:
    """Ab wann Stillstand als Abbruch gilt."""
    return hartes_limit() + PUFFER_SEC


async def _einsammeln(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    """Hängende Besprechungen auf „fehlgeschlagen" setzen.

    `error_message` wird nur gesetzt, wo keine steht: hat die Aufgabe es
    noch geschafft, einen Grund zu hinterlassen, ist der genauer als
    unsere allgemeine Vermutung.
    """
    zeilen = await conn.fetch(
        """
        update public.meetings
        set status = 'failed',
            error_message = coalesce(nullif(error_message, ''), $2),
            updated_at = now()
        where deleted_at is null
          and status = any($3::public.meeting_status[])
          and updated_at + make_interval(secs => $1) <= now()
        returning id, status, updated_at
        """,
        float(grenze_sekunden()),
        MELDUNG,
        list(SCHWEBENDE_ZUSTAENDE),
    )
    return [dict(z) for z in zeilen]


async def _durchlauf() -> dict[str, Any]:
    conn = await _connect()
    try:
        eingesammelt = await _einsammeln(conn)
    finally:
        await conn.close()

    if eingesammelt:
        # Die Oberfläche fragt ohnehin nach; der Webhook ist für alles
        # daneben — dieselbe Nachricht, die eine regulär gescheiterte
        # Verarbeitung schickt.
        from app.worker import celery_app as _app

        for zeile in eingesammelt:
            _app.send_task("notify_webhook", args=[str(zeile["id"]), "meeting.failed"])
        log.warning(
            "Wächter: %d Besprechung(en) hingen fest und stehen jetzt auf "
            "fehlgeschlagen: %s",
            len(eingesammelt),
            ", ".join(str(z["id"]) for z in eingesammelt),
        )

    return {"eingesammelt": len(eingesammelt), "grenze_sec": grenze_sekunden()}


@shared_task(name="waechter")
def waechter() -> dict[str, Any]:
    """Alle fünf Minuten vom Beat gerufen (siehe `app.worker.beat_schedule`).

    Hält keinen Zustand und ist beliebig wiederholbar: was er einmal
    eingesammelt hat, steht auf `failed` und fällt beim nächsten Lauf
    nicht mehr in die Auswahl.
    """
    return asyncio.run(_durchlauf())
