"""Wie viele Sprecher die Schätzung ausprobieren darf.

Auf der Box gefunden (16.9.2026): eine Aufnahme mit vier Segmenten ging
durch die Erkennung, kam aber ohne Sprechernamen zurück. Im Protokoll des
Erkennungsdienstes stand der Grund:

    diarization failed: Number of labels is 4.
    Valid values are 2 to n_samples - 1 (inclusive)

`_estimate_speakers` probierte so viele Cluster wie Segmente. Beim
letzten Durchgang bekam damit jedes Segment seinen eigenen Cluster,
`silhouette_score` lehnte das ab, und die Ausnahme riss die **ganze**
Sprechertrennung mit — gefangen wurde sie eine Ebene höher, mit einer
Protokollzeile und ohne Spur in der Oberfläche. Betroffen war jede
Aufnahme mit höchstens `MAX_SPEAKERS` verwertbaren Segmenten, also jede
kurze.

Die Regel steht seit 0.1.100 in `services/whisper/app/clustergroesse.py`
— ein Modul ohne Abhängigkeiten, damit sie hier prüfbar ist. `diarize.py`
selbst zieht torch, speechbrain und scikit-learn mit sich, die im Backend
nicht installiert sind.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[2]
MODUL = WURZEL / "services/whisper/app/clustergroesse.py"


def _laden():
    """Das Modul über seinen Pfad laden, am Paketnamen `app` vorbei.

    Backend und Erkennungsdienst heißen beide `app`; ein gewöhnlicher
    Import fände hier das Backend.
    """
    spec = importlib.util.spec_from_file_location("insilo_clustergroesse", MODUL)
    modul = importlib.util.module_from_spec(spec)
    sys.modules["insilo_clustergroesse"] = modul
    spec.loader.exec_module(modul)
    return modul


clustergroesse = _laden()
MAX_SPRECHER = 6


@pytest.mark.parametrize("segmente", [2, 3, 4, 5, 6, 7, 8, 12, 200])
def test_k_bleibt_unter_der_segmentzahl(segmente: int) -> None:
    """Die Regression: `k == n` ist genau, was `silhouette_score` ablehnt."""
    for k in clustergroesse.k_bereich(segmente, MAX_SPRECHER):
        assert k < segmente, f"k={k} bei {segmente} Segmenten wäre ein Cluster je Segment"
        assert k >= 2, "unter zwei Gruppen gibt es nichts zu vergleichen"


@pytest.mark.parametrize("segmente", [0, 1, 2])
def test_zu_wenig_segmente_ergeben_nichts_zu_probieren(segmente: int) -> None:
    """Bei zwei Segmenten gäbe es nur `k=2`, und das ist ein Cluster je Segment."""
    assert list(clustergroesse.k_bereich(segmente, MAX_SPRECHER)) == []


def test_der_fall_von_der_box() -> None:
    """Vier Segmente — genau die Aufnahme, an der es aufgefallen ist."""
    assert list(clustergroesse.k_bereich(4, MAX_SPRECHER)) == [2, 3]


def test_lange_aufnahmen_probieren_bis_zur_obergrenze() -> None:
    """Bei genug Segmenten begrenzt `MAX_SPEAKERS`, nicht die Segmentzahl."""
    assert list(clustergroesse.k_bereich(200, MAX_SPRECHER)) == [2, 3, 4, 5, 6]


def test_die_obergrenze_wird_eingehalten() -> None:
    for n in range(2, 60):
        for k in clustergroesse.k_bereich(n, MAX_SPRECHER):
            assert k <= MAX_SPRECHER


def test_diarize_benutzt_die_regel() -> None:
    """Sonst stünde sie hier und im Dienst etwas anderes."""
    quelle = (WURZEL / "services/whisper/app/diarize.py").read_text(encoding="utf-8")
    assert "k_bereich(len(embeddings), MAX_SPEAKERS)" in quelle
    assert "min(MAX_SPEAKERS, len(embeddings))" not in quelle, (
        "der alte Bereich ist zurück — kurze Aufnahmen verlieren wieder ihre Sprecher"
    )
