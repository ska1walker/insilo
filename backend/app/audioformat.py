"""Tonformate: welche Endung eine Aufnahme bekommt und als was sie ausgeliefert wird.

Bis 0.1.96 stand das an drei Stellen, jede mit eigener Liste, und jede
kannte andere Formate. Aus dem Browser kamen nur webm und mp4, das fiel nie
auf. Mit dem Hochladen von Dateien kommen mp3, flac, aac und das
`audio/x-m4a` des iPhones dazu — mit den alten Listen landete eine mp3 als
`.webm` in der Ablage und wurde als `application/octet-stream` ausgeliefert,
den kein Browser abspielt.
"""

from __future__ import annotations

# Reihenfolge zählt: der erste Treffer gewinnt. `mp4` vor `mpeg` wäre egal,
# aber `x-m4a` muss vor einem allgemeinen `m4a`-Suchwort stehen, und `aacp`
# enthält `aac`.
_KENNUNGEN: tuple[tuple[str, str], ...] = (
    ("webm", "webm"),
    ("x-m4a", "m4a"),
    ("m4a", "m4a"),
    ("mp4", "m4a"),
    ("aac", "aac"),
    ("ogg", "ogg"),
    ("opus", "ogg"),
    ("wav", "wav"),
    ("wave", "wav"),
    ("mpeg", "mp3"),
    ("mp3", "mp3"),
    ("flac", "flac"),
    ("3gpp", "3gp"),
)

# Endungen, die aus einem Dateinamen übernommen werden dürfen.
_DATEIENDUNGEN = {
    "webm": "webm",
    "m4a": "m4a",
    "mp4": "m4a",
    "aac": "aac",
    "ogg": "ogg",
    "oga": "ogg",
    "opus": "ogg",
    "wav": "wav",
    "mp3": "mp3",
    "flac": "flac",
    "3gp": "3gp",
}

MEDIENTYP: dict[str, str] = {
    "webm": "audio/webm",
    "m4a": "audio/mp4",
    "aac": "audio/aac",
    "ogg": "audio/ogg",
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "flac": "audio/flac",
    "3gp": "audio/3gpp",
}

VORGABE = "webm"


def audio_endung(mime: str | None, dateiname: str | None = None) -> str:
    """Endung für die Ablage.

    Der MIME-Typ entscheidet, wenn er etwas sagt. Ist er leer oder nichts
    sagend (`application/octet-stream`, wie manche Android-Dateiauswahl ihn
    liefert), zählt die Endung des Dateinamens. Sonst `webm` — das Format,
    das der Recorder im Browser liefert.
    """
    kennung = (mime or "").lower()
    for such, endung in _KENNUNGEN:
        if such in kennung:
            return endung
    if dateiname and "." in dateiname:
        roh = dateiname.rsplit(".", 1)[-1].lower()
        if roh in _DATEIENDUNGEN:
            return _DATEIENDUNGEN[roh]
    return VORGABE
