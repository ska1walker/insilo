"""Eine lange Aufnahme in Abschnitte zerlegen, an Sprechpausen.

**Warum überhaupt.** Eine Besprechung von anderthalb Stunden geht bisher
als ein einziger Aufruf an die Spracherkennung. Der Aufruf dauert dann —
je nach Weg — zwischen anderthalb Minuten und zwei Stunden, und in dieser
Zeit gibt es nichts: keinen Fortschritt, keinen Teilerfolg, und wenn
irgendetwas dazwischenkommt, war alles umsonst. Seit 0.1.99 sind die
Zeitriegel großzügig genug, dass er meistens durchläuft
(`app/verarbeitungszeit.py`) — aber „meistens" ist keine Eigenschaft, auf
die man eine Aktennotiz baut.

In Abschnitten zerlegt gilt stattdessen: jeder einzelne Aufruf ist kurz,
jeder fertige Abschnitt ist gesichert, und die Oberfläche kann sagen, wie
weit es ist. Bricht der siebte von zwölf ab, fangen die ersten sechs beim
nächsten Versuch nicht von vorn an.

**Warum an Sprechpausen und nicht alle zehn Minuten.** Ein harter Schnitt
landet mit hoher Wahrscheinlichkeit mitten in einem Wort. Whisper hört
dann zweimal einen Halbsatz und schreibt zweimal Unsinn — an genau der
Stelle, an der jemand später nachliest. `silencedetect` sagt uns, wo
wirklich nichts gesprochen wird; wir schneiden in die Mitte der Pause,
die dem gewünschten Abschnittsende am nächsten liegt. Findet sich keine,
wird hart geschnitten: ein möglicher Wortfehler ist besser als ein
Abschnitt, der beliebig lang wird.

**Warum die Sprecher hier nicht vorkommen.** Die Sprechertrennung läuft
**einmal am Ende über die ganze Datei**, nicht je Abschnitt. Sie clustert
Stimmen gegeneinander; täte sie das je Abschnitt, hieße derselbe Mensch
in Abschnitt drei anders als in Abschnitt eins. `diarize()` im
Whisper-Dienst nimmt ohnehin die ganze Datei plus eine Segmentliste
entgegen — der zusammengeführten Liste ist nicht anzusehen, dass der Text
stückweise entstanden ist.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.config import settings

log = logging.getLogger(__name__)

# Wie weit unter dem mittleren Pegel der Datei eine Stelle liegen muss, um
# als Pause zu gelten — und die Grenzen, in denen sich das bewegen darf.
#
# **Warum relativ und nicht fest.** Der erste Entwurf nahm feste -30 dBFS.
# Gemessen am 16.9.2026: eine übliche Aufnahme liegt im Mittel bei -21 dB,
# eine Testdatei aber bei -55 dB mit Spitzen von -32,5 dB. Bei festen
# -30 dB galt damit die **ganze** Datei als Pause — und genauso erginge es
# jeder leise aufgenommenen Besprechung, etwa mit dem Mikrofon am anderen
# Tischende. Geschnitten würde dann irgendwo, mitten im Satz.
#
# Die Grenzen sichern die harmlose Richtung ab: ein zu *niedriger*
# Schwellwert findet keine Pausen und führt zum harten Schnitt, ein zu
# hoher hielte gesprochene Stellen für still. Deshalb nie über -25 dB.
ABSTAND_ZUM_MITTEL_DB = 10
SCHWELLE_MAX_DB = -25
SCHWELLE_MIN_DB = -70

# Eine halbe Sekunde ist kürzer als jede Atempause zwischen zwei Sätzen
# und länger als der Verschluss vor einem harten Konsonanten.
STILLE_SEK = 0.5

# Wie weit ein Schnitt vom rechnerischen Abschnittsende abweichen darf, um
# eine Pause zu treffen. Ein Viertel der Abschnittslänge: genug, um fast
# immer eine zu finden, wenig genug, dass die Abschnitte gleichmäßig bleiben.
SUCHFENSTER = 0.25

# Womit die geschnittenen Abschnitte gemeldet werden. Opus ist das, was
# jedes Whisper-Modell intern ohnehin bekommt, und klein genug, dass auch
# fremde Endpunkte mit Größengrenze sie annehmen.
MEDIENTYP_STUECK = "audio/ogg"


@dataclass(frozen=True)
class Abschnitt:
    """Ein Stück der Aufnahme, in Sekunden ab Beginn."""

    index: int
    start: float
    ende: float

    @property
    def dauer(self) -> float:
        return self.ende - self.start


def arbeitsordner() -> str | None:
    """Wohin die Abschnitte zwischenzeitlich geschrieben werden.

    `/app/cache` auf der Box — einer der drei Pfade, die Olares erlaubt,
    und im Gegensatz zum Container-Layer kein flüchtiger Knotenspeicher,
    dessen Füllstand den Pod verdrängen kann. `None` heißt „nimm den
    Systemordner": so läuft es in der lokalen Entwicklung, wo es
    `/app/cache` nicht gibt.
    """
    # Der eingestellte Pfad zuerst, `/app/cache` als Rückfall: so landet es
    # auch dann richtig, wenn jemand die Einstellung verstellt oder eine
    # Umgebungsvariable etwas anderes bedeutet, als ihr Name vermuten lässt.
    for kandidat in (settings.stueck_cache_dir, "/app/cache"):
        if not kandidat:
            continue
        try:
            pfad = Path(kandidat)
            if not pfad.is_dir():
                continue
            unterordner = pfad / "abschnitte"
            unterordner.mkdir(exist_ok=True)
            return str(unterordner)
        except OSError as exc:
            log.warning("Zwischenspeicher %s nicht nutzbar: %s", kandidat, exc)
    return None


def verfuegbar() -> bool:
    """Ist ffmpeg da?

    Nein heißt nicht „kaputt": der Aufrufer fällt dann auf den Weg ohne
    Abschnitte zurück. Das ist der Zustand, in dem Insilo bis 0.1.98 war.
    """
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def _laufen(befehl: list[str], zeitlimit: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        befehl,
        capture_output=True,
        text=True,
        timeout=zeitlimit,
        check=False,
    )


def dauer_sekunden(pfad: Path) -> float | None:
    """Die echte Länge der Datei, laut ffprobe.

    Genauer als alles, was der Browser mitschickt — und der einzige Wert,
    nach dem sich die Aufteilung richten darf. Ein falsch geratener Wert
    ergäbe Abschnitte, die über das Dateiende hinausreichen.
    """
    fertig = _laufen(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(pfad),
        ],
        zeitlimit=60,
    )
    if fertig.returncode != 0:
        log.warning("ffprobe konnte %s nicht lesen: %s", pfad.name, fertig.stderr[:200])
        return None
    try:
        wert = float(fertig.stdout.strip())
    except ValueError:
        return None
    return wert if wert > 0 else None


_MITTLERER_PEGEL = re.compile(r"mean_volume:\s*(-?[\d.]+) dB")
_STILLE_ANFANG = re.compile(r"silence_start:\s*(-?[\d.]+)")
_STILLE_ENDE = re.compile(r"silence_end:\s*(-?[\d.]+)")


def mittlerer_pegel(pfad: Path, zeitlimit: float = 900) -> float | None:
    """Der mittlere Pegel der Datei in dBFS, laut ffmpeg."""
    fertig = _laufen(
        ["ffmpeg", "-nostdin", "-i", str(pfad), "-af", "volumedetect", "-f", "null", "-"],
        zeitlimit=zeitlimit,
    )
    treffer = _MITTLERER_PEGEL.search(fertig.stderr)
    return float(treffer.group(1)) if treffer else None


def stille_schwelle(mittel: float | None) -> int:
    """Ab wann eine Stelle als Pause zählt, gemessen am Pegel der Datei."""
    if mittel is None:
        return SCHWELLE_MAX_DB
    roh = round(mittel - ABSTAND_ZUM_MITTEL_DB)
    return max(SCHWELLE_MIN_DB, min(SCHWELLE_MAX_DB, roh))


def stillen(
    pfad: Path, schwelle_db: int | None = None, zeitlimit: float = 900,
) -> list[tuple[float, float]]:
    """Alle Sprechpausen als (Anfang, Ende) in Sekunden.

    ffmpeg schreibt sie nach stderr, während es die Datei einmal
    durchläuft — das ist ein reiner Dekodierlauf ohne Ausgabe und
    entsprechend schnell (deutlich über hundertfache Echtzeit). Weil der
    Schwellwert vom Pegel der Datei abhängt, sind es zwei solche Läufe;
    gegen eine Stunde Spracherkennung fällt das nicht ins Gewicht.
    """
    if schwelle_db is None:
        schwelle_db = stille_schwelle(mittlerer_pegel(pfad, zeitlimit))
    fertig = _laufen(
        [
            "ffmpeg", "-nostdin", "-i", str(pfad),
            "-af", f"silencedetect=noise={schwelle_db}dB:d={STILLE_SEK}",
            "-f", "null", "-",
        ],
        zeitlimit=zeitlimit,
    )
    anfaenge = [float(m) for m in _STILLE_ANFANG.findall(fertig.stderr)]
    enden = [float(m) for m in _STILLE_ENDE.findall(fertig.stderr)]
    # Die letzte Stille kann bis zum Dateiende laufen; dann fehlt ihr Ende.
    paare = list(zip(anfaenge, enden, strict=False))
    return [(a, e) for a, e in paare if e > a]


def schnittpunkte(
    gesamt: float, pausen: list[tuple[float, float]], ziel: float,
) -> list[float]:
    """Wo geschnitten wird, in Sekunden — ohne 0 und ohne das Dateiende.

    Rein rechnerisch, ohne ffmpeg: so lässt sich die Aufteilung prüfen,
    ohne eine Audiodatei zu bauen.
    """
    if ziel <= 0 or gesamt <= ziel:
        return []

    fenster = ziel * SUCHFENSTER
    punkte: list[float] = []
    naechstes = ziel
    while naechstes < gesamt:
        # Nur Pausen, die hinter dem letzten Schnitt liegen — sonst
        # entstünde ein Abschnitt der Länge null.
        untergrenze = max(naechstes - fenster, (punkte[-1] if punkte else 0.0) + 1.0)
        kandidaten = [
            (a + e) / 2
            for a, e in pausen
            if untergrenze <= (a + e) / 2 <= min(naechstes + fenster, gesamt - 1.0)
        ]
        if kandidaten:
            punkt = min(kandidaten, key=lambda m: abs(m - naechstes))
        elif naechstes < gesamt - 1.0:
            # Keine Pause in Reichweite: hart schneiden. Ein möglicher
            # Wortfehler ist besser als ein Abschnitt ohne Obergrenze.
            punkt = naechstes
        else:
            break
        punkte.append(punkt)
        naechstes = punkt + ziel
    return punkte


def abschnitte_aus(gesamt: float, punkte: list[float]) -> list[Abschnitt]:
    """Aus den Schnittpunkten die Abschnitte machen."""
    grenzen = [0.0, *punkte, gesamt]
    return [
        Abschnitt(index=i, start=grenzen[i], ende=grenzen[i + 1])
        for i in range(len(grenzen) - 1)
        if grenzen[i + 1] - grenzen[i] > 0.05
    ]


def aufteilen(pfad: Path, ziel_sekunden: int | None = None) -> list[Abschnitt] | None:
    """Die Aufnahme in Abschnitte einteilen — oder `None`, wenn nicht nötig.

    `None` heißt in jedem Fall „nimm den Weg ohne Abschnitte": zu kurz,
    ffmpeg fehlt, oder die Datei ließ sich nicht lesen. Der Aufrufer muss
    diesen Fall können, sonst wäre ein fehlendes ffmpeg ein Ausfall statt
    eines Rückschritts auf das bisherige Verhalten.
    """
    ziel = ziel_sekunden or settings.stueck_sekunden
    if ziel <= 0 or not verfuegbar():
        return None

    gesamt = dauer_sekunden(pfad)
    if gesamt is None or gesamt <= max(ziel, settings.stueck_ab_sekunden):
        return None

    schwelle = stille_schwelle(mittlerer_pegel(pfad))
    pausen = stillen(pfad, schwelle)
    # Gilt fast alles als Pause, ist der Pegel nicht zu gebrauchen —
    # dann lieber nach Uhr schneiden als an falsch erkannten Stellen.
    if sum(e - a for a, e in pausen) > 0.8 * gesamt:
        log.warning("Pegelmessung unbrauchbar (%d dB), es wird nach Uhr geteilt", schwelle)
        pausen = []
    teile = abschnitte_aus(gesamt, schnittpunkte(gesamt, pausen, ziel))
    if len(teile) < 2:
        return None
    log.info(
        "Aufnahme von %.0fs in %d Abschnitte geteilt (%d Pausen bei %d dB)",
        gesamt, len(teile), len(pausen), schwelle,
    )
    return teile


def schneiden(quelle: Path, teil: Abschnitt, ziel: Path) -> bool:
    """Einen Abschnitt als Ogg/Opus herausschreiben.

    Neu kodiert, nicht kopiert: ein Stromkopie-Schnitt kann nur an
    Bildgruppengrenzen ansetzen und läge damit wieder irgendwo. Opus mono
    bei 16 kHz ist genau das, was jedes Whisper-Modell intern benutzt —
    die Abschnitte werden dadurch klein (rund 3 kB/s), was auch fremden
    Endpunkten mit Größengrenze entgegenkommt.
    """
    fertig = _laufen(
        [
            "ffmpeg", "-nostdin", "-y",
            "-ss", f"{teil.start:.3f}",
            "-t", f"{teil.dauer:.3f}",
            "-i", str(quelle),
            "-vn", "-ac", "1", "-ar", "16000",
            "-c:a", "libopus", "-b:a", "24k",
            "-f", "ogg", str(ziel),
        ],
        zeitlimit=600,
    )
    if fertig.returncode != 0 or not ziel.exists() or ziel.stat().st_size == 0:
        log.warning(
            "Abschnitt %d (%.1f–%.1fs) ließ sich nicht schneiden: %s",
            teil.index, teil.start, teil.ende, fertig.stderr[-300:],
        )
        return False
    return True


def versetzen(segmente: list[dict], versatz: float) -> list[dict]:
    """Segmentzeiten eines Abschnitts auf die ganze Aufnahme umrechnen.

    Ohne das begänne jeder Abschnitt wieder bei null, und das Transkript
    hätte zwölfmal die Minute drei.
    """
    verschoben = []
    for s in segmente:
        kopie = dict(s)
        kopie["start"] = float(s.get("start") or 0.0) + versatz
        kopie["end"] = float(s.get("end") or 0.0) + versatz
        verschoben.append(kopie)
    return verschoben
