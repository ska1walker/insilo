"""Wie viele Sprecher die Schätzung ausprobieren darf.

Eigenes Modul, und ausdrücklich ohne Abhängigkeiten: `diarize.py` zieht
torch, speechbrain und scikit-learn mit sich, und die stehen im Backend
nicht zur Verfügung. Die Regel hier ist reine Arithmetik und lässt sich
deshalb überall prüfen — sie war einen stillen Ausfall wert.

**Der Fall, um den es geht.** `silhouette_score` verlangt
`2 <= Anzahl der Label <= Anzahl der Proben - 1`. Probierte die Schätzung
so viele Cluster wie Segmente, bekam jedes Segment seinen eigenen, die
Bedingung war verletzt, und die Ausnahme riss die ganze Sprechertrennung
mit: Das Transkript kam, die Sprechernamen fehlten — ohne dass irgendwo
etwas davon stand. Betroffen war jede Aufnahme mit höchstens
`MAX_SPEAKERS` verwertbaren Segmenten, also jede kurze. Auf der Box
gefunden am 16.9.2026 an einer Aufnahme mit vier Segmenten.
"""

from __future__ import annotations


def k_bereich(anzahl_segmente: int, max_sprecher: int) -> range:
    """Die Cluster-Anzahlen, die ausprobiert werden dürfen.

    Leer, wenn es nichts auszuprobieren gibt — bei ein oder zwei
    Segmenten gibt es keine sinnvolle Aufteilung in zwei Gruppen, die
    `silhouette_score` bewerten könnte.
    """
    hoechstes = min(max_sprecher, anzahl_segmente - 1)
    if hoechstes < 2:
        return range(0)
    return range(2, hoechstes + 1)
