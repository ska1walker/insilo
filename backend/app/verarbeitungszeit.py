"""Wie lange ein Erkennungsaufruf stehen darf.

**Warum das gerechnet wird und nicht festgeschrieben.** Bis 0.1.98 stand
im Code `httpx.Timeout(60 * 25)` — fünfundzwanzig Minuten, für jede
Aufnahme gleich. Dazu kam Celerys hartes Limit von dreißig Minuten. Auf
einer Box ohne GPU braucht der mitgelieferte Dienst aber mehr Rechenzeit,
als die Aufnahme lang ist: gemessen am 16.9.2026 mit `large-v3`, `int8`,
sechs Kernen, `beam_size=5` und Sprechertrennung im selben Aufruf **795 s
für 626 s Audio**, Faktor 1,3. Der Riegel fiel damit bei ungefähr zwanzig
Minuten Aufnahme — und die Besprechung landete auf „fehlgeschlagen",
obwohl nichts kaputt war. Ein externer Endpunkt mit GPU schaffte dasselbe
Audio in 38,5 s, Faktor 0,06.

Zwischen 0,06 und 1,3 liegt der Faktor zwanzig. Ein einzelner fester Wert
kann für beide Wege nicht richtig sein: kurz genug für den schnellen Weg
heißt zu kurz für den langsamen, und lang genug für den langsamen heißt,
dass ein hängender schneller Dienst eine halbe Stunde lang niemandem
auffällt. Also hängt der Riegel an der Länge der Aufnahme.

**Was der Riegel ist und was nicht.** Er erkennt einen Dienst, der nicht
mehr antwortet. Er bewertet keine Geschwindigkeit und ist keine Zusage an
den Nutzer. Deshalb die Faustregel für die Vorgabewerte: er darf nie bei
einer Aufgabe zuschlagen, die noch fertig geworden wäre. Lieber wartet
eine hängende Aufgabe zu lange — dafür gibt es seit 0.1.99 den Wächter,
der sie aufräumt (`app/tasks/waechter.py`).
"""

from __future__ import annotations

from app.config import settings

# Untere Kante dessen, was eine Aufnahme an Bytes je Sekunde belegt.
# MediaRecorder schreibt Opus in WebM mit ungefähr 15 kB/s; eine auf
# 64 kbit/s gedrückte MP3 liegt bei 8 kB/s. Wir rechnen mit 8000, damit
# die Schätzung eher zu lang als zu kurz ausfällt — zu lang ist hier die
# harmlose Richtung.
BYTES_JE_SEKUNDE = 8000


def geschaetzte_dauer(dauer_sec: int | None, bytes_: int) -> float:
    """Wie lang die Aufnahme wahrscheinlich ist, in Sekunden.

    Die Dauer in der Datenbank stammt aus dem Browser und kann fehlen
    oder danebenliegen: bei einer hochgeladenen Datei, deren Länge sich
    nicht auslesen ließ, steht dort eine Sekunde. Die Dateigröße lügt
    nicht, ist aber ungenau. Das Größere von beidem ist für einen Riegel
    die richtige Wahl — es verlängert ihn im Zweifel.
    """
    aus_groesse = max(0, bytes_) / BYTES_JE_SEKUNDE
    return max(float(dauer_sec or 0), aus_groesse)


def stt_zeitlimit(dauer_sec: int | None, bytes_: int) -> float:
    """Riegel für einen Erkennungsaufruf, in Sekunden.

    Unten begrenzt, damit ein kurzer Schnipsel nicht an einem Riegel von
    zwei Sekunden scheitert; oben begrenzt, damit ein hängender Dienst
    nicht den einen Worker für immer belegt.
    """
    roh = geschaetzte_dauer(dauer_sec, bytes_) * settings.stt_zeitfaktor
    return min(
        max(roh, float(settings.stt_zeitlimit_min_sec)),
        float(settings.verarbeitung_zeitlimit_sec),
    )


def hartes_limit() -> int:
    """Das harte Limit der ganzen Aufgabe, für den Celery-Aufsatz."""
    return max(60, int(settings.verarbeitung_zeitlimit_sec))


def weiches_limit() -> int:
    """Fünf Minuten vor dem harten.

    Der Abstand ist der Unterschied zwischen einer aufgeräumten und einer
    hängenden Besprechung: beim weichen Limit fliegt eine Ausnahme *in*
    der Aufgabe, die gefangen wird und den Zustand auf „fehlgeschlagen"
    setzt. Das harte Limit killt den Prozess — dann läuft kein `except`
    mehr, und die Besprechung stünde ohne den Wächter für immer auf
    „wird transkribiert".
    """
    return max(30, hartes_limit() - 300)
