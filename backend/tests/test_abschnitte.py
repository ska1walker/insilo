"""Lange Aufnahmen abschnittsweise erkennen, lange Transkripte verdichten.

Anlass (0.1.99): auch mit großzügigen Zeitriegeln bleibt eine Aufnahme von
anderthalb Stunden ein einziger Aufruf, der nichts meldet und bei dem ein
Abbruch alles kostet. Zerlegt man sie an Sprechpausen, ist jeder Aufruf
kurz, jeder fertige Abschnitt gesichert und der Fortschritt sichtbar.

Die Sprechertrennung bleibt ausdrücklich **außerhalb** der Abschnitte: sie
clustert Stimmen gegeneinander und läuft einmal über die ganze Datei. Je
Abschnitt geclustert hieße derselbe Mensch in Abschnitt drei anders als in
Abschnitt eins.
"""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from uuid import UUID

import pytest

from app import audiostuecke, verdichten

UUID_PROBE = UUID("00000000-0000-0000-0000-00000000c0de")

# ---------------------------------------------------------------------------
# Wo geschnitten wird
# ---------------------------------------------------------------------------


def test_schnitt_liegt_in_der_pause() -> None:
    """Der Kern der Sache: nicht nach Uhr, sondern wo niemand spricht."""
    pausen = [(170.0, 176.0), (400.0, 404.0)]
    punkte = audiostuecke.schnittpunkte(gesamt=600, pausen=pausen, ziel=180)
    assert punkte[0] == pytest.approx(173.0), "Mitte der Pause bei 170–176"


def test_ohne_pause_wird_hart_geschnitten() -> None:
    """Ein möglicher Wortfehler ist besser als ein Abschnitt ohne Ende."""
    punkte = audiostuecke.schnittpunkte(gesamt=600, pausen=[], ziel=180)
    assert punkte == [180.0, 360.0, 540.0]


def test_eine_pause_weit_weg_zaehlt_nicht() -> None:
    """Sonst wären die Abschnitte beliebig ungleich lang."""
    # Pause bei 300, gewünschtes Ende 180, Fenster ±45 → zu weit.
    punkte = audiostuecke.schnittpunkte(gesamt=600, pausen=[(299.0, 301.0)], ziel=180)
    assert punkte[0] == 180.0


def test_kurze_aufnahme_wird_nicht_geteilt() -> None:
    assert audiostuecke.schnittpunkte(gesamt=100, pausen=[], ziel=180) == []


def test_abschnitte_decken_die_aufnahme_lueckenlos_ab() -> None:
    """Ein verlorener Zwischenraum wäre ein Loch im Transkript."""
    teile = audiostuecke.abschnitte_aus(600.0, [173.0, 355.0])
    assert [round(t.start, 2) for t in teile] == [0.0, 173.0, 355.0]
    assert [round(t.ende, 2) for t in teile] == [173.0, 355.0, 600.0]
    assert sum(t.dauer for t in teile) == pytest.approx(600.0)
    for davor, danach in zip(teile, teile[1:], strict=False):
        assert davor.ende == danach.start


def test_kein_abschnitt_der_laenge_null() -> None:
    """Zwei Pausen direkt nebeneinander dürfen keinen leeren Teil ergeben."""
    teile = audiostuecke.abschnitte_aus(600.0, [173.0, 173.01])
    assert all(t.dauer > 0.05 for t in teile)


def test_schnitte_kommen_nacheinander() -> None:
    """Eine Pause hinter dem letzten Schnitt darf nicht zurückspringen."""
    pausen = [(10.0, 12.0), (170.0, 176.0), (190.0, 196.0)]
    punkte = audiostuecke.schnittpunkte(gesamt=900, pausen=pausen, ziel=180)
    assert punkte == sorted(punkte)
    assert all(b - a > 1.0 for a, b in zip(punkte, punkte[1:], strict=False))


# ---------------------------------------------------------------------------
# Der Schwellwert für „still"
# ---------------------------------------------------------------------------


def test_schwelle_richtet_sich_nach_dem_pegel_der_datei() -> None:
    """Die Regression, die die Messung am 16.9.2026 gezeigt hat.

    Der erste Entwurf nahm feste -30 dB. Eine Testdatei mit mittlerem
    Pegel -55,6 dB galt damit vollständig als Pause — und mit ihr jede
    leise aufgenommene Besprechung.
    """
    assert audiostuecke.stille_schwelle(-21.1) == -31
    assert audiostuecke.stille_schwelle(-55.6) < -55, "leise Datei braucht leisere Schwelle"


def test_schwelle_wird_nie_zu_hoch() -> None:
    """Zu hoch hieße: gesprochene Stellen gelten als Pause."""
    assert audiostuecke.stille_schwelle(-2.0) <= audiostuecke.SCHWELLE_MAX_DB
    assert audiostuecke.stille_schwelle(None) <= audiostuecke.SCHWELLE_MAX_DB


def test_schwelle_wird_nie_zu_niedrig() -> None:
    """Zu niedrig findet keine Pausen — das führt zum harten Schnitt."""
    assert audiostuecke.stille_schwelle(-120.0) >= audiostuecke.SCHWELLE_MIN_DB


# ---------------------------------------------------------------------------
# Zeiten umrechnen
# ---------------------------------------------------------------------------


def test_segmentzeiten_bekommen_den_versatz() -> None:
    """Ohne das begänne jeder Abschnitt wieder bei null."""
    segmente = [{"start": 0.0, "end": 3.2, "text": "Guten Morgen."}]
    versetzt = audiostuecke.versetzen(segmente, 355.0)
    assert versetzt[0]["start"] == 355.0
    assert versetzt[0]["end"] == pytest.approx(358.2)
    assert versetzt[0]["text"] == "Guten Morgen."
    # Das Original bleibt unberührt.
    assert segmente[0]["start"] == 0.0


# ---------------------------------------------------------------------------
# Die Sprecher bleiben außen vor
# ---------------------------------------------------------------------------


def test_abschnitte_werden_ohne_sprechertrennung_erkannt() -> None:
    """Sonst hieße derselbe Mensch in jedem Abschnitt anders.

    **Auf beiden Wegen.** Der erste Entwurf setzte das Flag nur für den
    mitgelieferten Dienst. Bei einem externen Endpunkt lief die
    Sprechertrennung dann je Abschnitt *und* am Ende noch einmal — im
    echten Durchlauf gegen Speaches am 16.9.2026 fünfmal statt einmal.
    """
    from app.tasks import transcribe

    quelle = inspect.getsource(transcribe._erkennen)
    assert quelle.count("diarisieren=False") == 2, (
        "beide Wege — der mitgelieferte Dienst und der externe Endpunkt"
    )


def test_auch_der_externe_weg_kann_ohne_sprechertrennung() -> None:
    """Die Gegenstelle: der Parameter muss dort auch etwas bewirken."""
    from app.tasks import transcribe

    quelle = " ".join(inspect.getsource(transcribe._transkribieren_extern).split())
    assert "if diarisieren else []" in quelle


def test_sprecher_kommen_einmal_ueber_die_ganze_datei() -> None:
    from app.tasks import transcribe

    quelle = " ".join(inspect.getsource(transcribe._stueckweise).split())
    assert "_sprecher_ergaenzen( audio_bytes" in quelle, (
        "die Sprechertrennung muss die ganze Aufnahme sehen, nicht einen Abschnitt"
    )


def test_der_dienst_kann_text_ohne_sprecher_liefern() -> None:
    """Die Gegenstelle zu `diarisieren=False`."""
    quelle = Path(__file__).resolve().parents[2] / "services/whisper/app/main.py"
    text = quelle.read_text(encoding="utf-8")
    assert "diarisieren: bool = Form(default=True)" in text
    assert "and diarisieren:" in text


def test_ohne_ffmpeg_bleibt_es_beim_alten_weg() -> None:
    """Ein fehlendes ffmpeg soll ein Rückschritt sein, kein Ausfall."""
    from app.tasks import transcribe

    quelle = inspect.getsource(transcribe._do_transcribe)
    assert "if tr is None:" in quelle
    assert "_transkribieren_lokal(" in quelle


# ---------------------------------------------------------------------------
# Verdichten vor der Zusammenfassung
# ---------------------------------------------------------------------------


def test_kurzes_transkript_wird_nicht_angefasst() -> None:
    assert not verdichten.zu_lang("kurz", 24_000)


def test_langes_transkript_wird_geteilt() -> None:
    zeilen = "\n".join(f"[Kai]: Satz Nummer {i}." for i in range(2000))
    teile = verdichten.teilen(zeilen, 5_000)
    assert len(teile) > 1
    assert all(len(t) <= 5_000 for t in teile)


def test_geteilt_wird_an_zeilenenden() -> None:
    """Mitten in einer Zeile zu schneiden zerreißt die Sprecherzuordnung."""
    zeilen = "\n".join(f"[Kai]: Satz Nummer {i}." for i in range(400))
    for teil in verdichten.teilen(zeilen, 1_000):
        for zeile in teil.split("\n"):
            assert zeile.startswith("[Kai]: ") or zeile == ""


def test_nichts_geht_beim_teilen_verloren() -> None:
    zeilen = "\n".join(f"[Kai]: Satz Nummer {i}." for i in range(500))
    teile = verdichten.teilen(zeilen, 2_000)
    assert "\n".join(teile) == zeilen


def test_eine_einzige_zu_lange_zeile_wird_hart_geteilt() -> None:
    """Ein Transkript ohne Sprecherzuordnung ist *eine* Zeile."""
    eine = "x" * 12_000
    teile = verdichten.teilen(eine, 5_000)
    assert len(teile) == 3
    assert "".join(teile) == eine


def test_zusammengesetzt_steht_die_reihenfolge_drin() -> None:
    """Ohne die Überschriften liest sich das Ganze zusammenhanglos."""
    zusammen = verdichten.zusammensetzen(["Erstens.", "Zweitens."], "de")
    assert "Abschnitt 1 von 2" in zusammen
    assert "Abschnitt 2 von 2" in zusammen
    assert zusammen.index("Erstens.") < zusammen.index("Zweitens.")


def test_leere_abschnitte_fallen_raus() -> None:
    assert "von 3" in verdichten.zusammensetzen(["A", "  ", "C"], "de")


@pytest.mark.parametrize("locale", ["de", "en", "fr", "es", "it"])
def test_aufforderung_in_allen_sprachen(locale: str) -> None:
    """Das Modell soll ein einheitliches Sprachsignal bekommen."""
    text = verdichten.aufforderung(locale)
    assert len(text) > 100
    assert text != verdichten.AUFFORDERUNG["de"] or locale == "de"


def test_unbekannte_sprache_faellt_auf_deutsch() -> None:
    assert verdichten.aufforderung("xx") == verdichten.AUFFORDERUNG["de"]


def test_verdichten_besteht_auf_dem_wesentlichen() -> None:
    """Was eine Kanzlei aus einer Besprechung braucht, darf nicht wegfallen."""
    de = verdichten.AUFFORDERUNG["de"]
    for wort in ("Namen", "Zahlen", "Termine", "Beschluss"):
        assert wort in de


def test_scheitert_das_verdichten_geht_der_volle_wortlaut_hinaus() -> None:
    """Sichtbar scheitern ist besser als stillschweigend kürzen."""
    from app.tasks import summarize

    quelle = inspect.getsource(summarize._vorverdichten)
    assert "return transkript" in quelle
    assert quelle.count("return transkript") >= 3


# ---------------------------------------------------------------------------
# Der ganze Weg: zerlegen, erkennen, zusammensetzen, fortsetzen
# ---------------------------------------------------------------------------


class _Abschnittsspeicher:
    """Ersetzt die vier Datenbankzugriffe von `_stueckweise`."""

    def __init__(self) -> None:
        self.abgelegt: dict[int, dict] = {}
        self.fortschritt: list[tuple[int, int]] = []

    async def fertige(self, _mid, teile):
        nach_index = {t.index: t for t in teile}
        return {
            i: e for i, e in self.abgelegt.items()
            if i in nach_index
            and abs(nach_index[i].start - e["start"]) < 0.5
            and abs(nach_index[i].ende - e["ende"]) < 0.5
        }

    async def ablegen(self, _mid, teil, ergebnis):
        self.abgelegt[teil.index] = {**ergebnis, "start": teil.start, "ende": teil.ende}

    async def melden(self, _mid, fertig, gesamt):
        self.fortschritt.append((fertig, gesamt))


@pytest.fixture
def stueckweise(monkeypatch: pytest.MonkeyPatch):
    """`_stueckweise` mit vorgegebener Aufteilung und erfundener Erkennung."""
    from app.tasks import transcribe

    speicher = _Abschnittsspeicher()
    gerufen: list[tuple[int, str]] = []
    scheitert_ab: dict[str, int | None] = {"index": None}

    teile = [
        audiostuecke.Abschnitt(0, 0.0, 300.0),
        audiostuecke.Abschnitt(1, 300.0, 610.0),
        audiostuecke.Abschnitt(2, 610.0, 900.0),
    ]

    monkeypatch.setattr(audiostuecke, "aufteilen", lambda _p, *a, **k: list(teile))

    def _schneiden(_quelle, teil, ziel):
        ziel.write_bytes(b"ton-" + str(teil.index).encode())
        return True

    monkeypatch.setattr(audiostuecke, "schneiden", _schneiden)

    async def _erkennen(inhalt, _mime, _sprache, _stt, _zeitlimit):
        index = int(inhalt.decode().split("-")[1])
        if scheitert_ab["index"] is not None and index >= scheitert_ab["index"]:
            raise RuntimeError("Endpunkt weg")
        gerufen.append((index, "erkannt"))
        # Jeder Abschnitt beginnt für sich bei null — genau das muss der
        # Versatz später geraderücken.
        return transcribe.Transkript(
            segments=[{"start": 1.0, "end": 9.0, "text": f"Teil {index}."}],
            full_text=f"Teil {index}.",
            cluster_centroids=[],
            language="de",
            model="attrappe",
            duration=None,
            quelle="lokal",
        )

    async def _sprecher(_bytes, _mime, segmente, _zeitlimit):
        gerufen.append((len(segmente), "sprecher"))
        return [[0.1] * 3]

    monkeypatch.setattr(transcribe, "_erkennen", _erkennen)
    monkeypatch.setattr(transcribe, "_sprecher_ergaenzen", _sprecher)
    monkeypatch.setattr(transcribe, "_fertige_abschnitte", speicher.fertige)
    monkeypatch.setattr(transcribe, "_abschnitt_ablegen", speicher.ablegen)
    monkeypatch.setattr(transcribe, "_fortschritt", speicher.melden)

    class _STT:
        eingerichtet = False
        base_url = ""

    async def lauf():
        return await transcribe._stueckweise(
            UUID_PROBE, b"ganze-aufnahme", "audio/webm", "de", _STT(), 3600.0
        )

    return lauf, speicher, gerufen, scheitert_ab, teile


def test_jeder_abschnitt_wird_einzeln_erkannt(stueckweise) -> None:
    lauf, _speicher, gerufen, _s, teile = stueckweise
    tr = asyncio.run(lauf())

    erkannt = [i for i, was in gerufen if was == "erkannt"]
    assert erkannt == [0, 1, 2]
    assert tr is not None
    assert tr.duration == teile[-1].ende


def test_die_zeiten_stimmen_nach_dem_zusammensetzen(stueckweise) -> None:
    """Ohne Versatz hätte das Transkript dreimal die Sekunde eins."""
    lauf, _speicher, _g, _s, _t = stueckweise
    tr = asyncio.run(lauf())

    starts = [s["start"] for s in tr.segments]
    assert starts == [1.0, 301.0, 611.0]
    assert starts == sorted(starts), "die Segmente müssen aufsteigend liegen"
    assert tr.full_text == "Teil 0. Teil 1. Teil 2."


def test_sprecher_einmal_ueber_alle_segmente(stueckweise) -> None:
    """Nicht je Abschnitt: sonst heißt derselbe Mensch dreimal anders."""
    lauf, _speicher, gerufen, _s, _t = stueckweise
    asyncio.run(lauf())

    sprecherlaeufe = [n for n, was in gerufen if was == "sprecher"]
    assert sprecherlaeufe == [3], "einmal, mit allen drei Segmenten"


def test_fortschritt_wird_gemeldet(stueckweise) -> None:
    lauf, speicher, _g, _s, _t = stueckweise
    asyncio.run(lauf())

    assert speicher.fortschritt == [(0, 3), (1, 3), (2, 3), (3, 3)]


def test_ein_zweiter_versuch_faengt_nicht_von_vorn_an(stueckweise) -> None:
    """Der eigentliche Gewinn: der langsame Weg kostet eine Stunde."""
    lauf, speicher, gerufen, scheitert_ab, _t = stueckweise

    scheitert_ab["index"] = 2
    with pytest.raises(RuntimeError):
        asyncio.run(lauf())
    assert sorted(speicher.abgelegt) == [0, 1]

    gerufen.clear()
    scheitert_ab["index"] = None
    tr = asyncio.run(lauf())

    assert [i for i, was in gerufen if was == "erkannt"] == [2], (
        "nur der fehlende Abschnitt wird noch einmal erkannt"
    )
    assert [s["start"] for s in tr.segments] == [1.0, 301.0, 611.0]


def test_geaenderte_aufteilung_verwirft_den_zwischenstand(stueckweise) -> None:
    """Sonst säße alter Wortlaut an der falschen Zeit im Transkript."""
    lauf, speicher, gerufen, _s, _t = stueckweise
    asyncio.run(lauf())

    # Jemand stellt die Abschnittslänge um: Abschnitt 1 zeigt jetzt
    # woandershin.
    speicher.abgelegt[1]["start"] = 250.0
    gerufen.clear()
    asyncio.run(lauf())

    assert 1 in [i for i, was in gerufen if was == "erkannt"]


def test_misslungener_schnitt_faellt_auf_den_alten_weg_zurueck(
    stueckweise, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein still fehlendes Stück wäre schlimmer als ein langsamer Lauf."""
    lauf, _speicher, _g, _s, _t = stueckweise
    monkeypatch.setattr(audiostuecke, "schneiden", lambda *a, **k: False)

    assert asyncio.run(lauf()) is None


def test_ohne_aufteilung_kein_stueckweiser_weg(
    stueckweise, monkeypatch: pytest.MonkeyPatch,
) -> None:
    lauf, _speicher, _g, _s, _t = stueckweise
    monkeypatch.setattr(audiostuecke, "aufteilen", lambda *a, **k: None)

    assert asyncio.run(lauf()) is None


class _ZeilenVerbindung:
    """Nur so viel Verbindung, wie `_fertige_abschnitte` anfasst."""

    def __init__(self, zeilen: list[dict]) -> None:
        self.zeilen = zeilen

    async def fetch(self, _sql: str, *_args):
        return self.zeilen

    async def close(self) -> None:
        return None


@pytest.fixture
def abschnitte_lesen(monkeypatch: pytest.MonkeyPatch):
    """`_fertige_abschnitte` selbst — nicht die Attrappe aus dem Fixture oben."""
    from app.tasks import transcribe

    zustand: dict = {"zeilen": []}

    async def _connect():
        return _ZeilenVerbindung(zustand["zeilen"])

    monkeypatch.setattr(transcribe, "_connect", _connect)
    return transcribe._fertige_abschnitte, zustand


def _zeile(idx: int, start: float, ende: float) -> dict:
    return {
        "idx": idx, "start_sec": start, "end_sec": ende,
        "segments": '[{"start": 1.0, "end": 2.0, "text": "x"}]',
        "text": "x", "language": "de",
    }


def test_passender_zwischenstand_wird_uebernommen(abschnitte_lesen) -> None:
    lesen, zustand = abschnitte_lesen
    teile = [audiostuecke.Abschnitt(0, 0.0, 300.0), audiostuecke.Abschnitt(1, 300.0, 600.0)]
    zustand["zeilen"] = [_zeile(0, 0.0, 300.0), _zeile(1, 300.0, 600.0)]

    gefunden = asyncio.run(lesen(UUID_PROBE, teile))

    assert sorted(gefunden) == [0, 1]
    # jsonb kommt je nach Verbindung als Text — beides muss ankommen.
    assert gefunden[0]["segments"][0]["text"] == "x"


def test_verschobener_zwischenstand_wird_verworfen(abschnitte_lesen) -> None:
    """Die Regression: sonst säße alter Wortlaut an der falschen Zeit.

    Stellt jemand `INSILO_STUECK_SEKUNDEN` um, zeigt Abschnitt 1 auf eine
    andere Stelle der Aufnahme als beim letzten Versuch.
    """
    lesen, zustand = abschnitte_lesen
    teile = [audiostuecke.Abschnitt(0, 0.0, 300.0), audiostuecke.Abschnitt(1, 300.0, 600.0)]
    zustand["zeilen"] = [_zeile(0, 0.0, 300.0), _zeile(1, 250.0, 550.0)]

    gefunden = asyncio.run(lesen(UUID_PROBE, teile))

    assert sorted(gefunden) == [0], "Abschnitt 1 liegt woanders und muss neu"


def test_ueberzaehliger_zwischenstand_wird_verworfen(abschnitte_lesen) -> None:
    """Weniger Abschnitte als beim letzten Mal: der Rest gehört nirgends hin."""
    lesen, zustand = abschnitte_lesen
    teile = [audiostuecke.Abschnitt(0, 0.0, 600.0)]
    zustand["zeilen"] = [_zeile(0, 0.0, 600.0), _zeile(1, 600.0, 900.0)]

    assert sorted(asyncio.run(lesen(UUID_PROBE, teile))) == [0]


def test_ohne_zwischenstand_ist_nichts_zu_uebernehmen(abschnitte_lesen) -> None:
    lesen, zustand = abschnitte_lesen
    zustand["zeilen"] = []

    assert asyncio.run(lesen(UUID_PROBE, [audiostuecke.Abschnitt(0, 0.0, 300.0)])) == {}


# ---------------------------------------------------------------------------
# Wohin die Abschnitte geschrieben werden
# ---------------------------------------------------------------------------


def test_zwischenspeicher_liegt_in_app_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    """Olares erlaubt nur drei Pfade (CLAUDE.md, Constraint 5).

    `/tmp` wäre auf der Box der flüchtige Speicher des Knotens — eine
    Aufnahme von 500 MB dort kann den Pod verdrängen lassen.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "app_cache_dir", str(tmp_path))
    ordner = audiostuecke.arbeitsordner()

    assert ordner is not None
    assert ordner.startswith(str(tmp_path))
    assert Path(ordner).is_dir()


def test_ohne_app_cache_nimmt_der_code_den_systemordner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In der lokalen Entwicklung gibt es `/app/cache` nicht."""
    from app.config import settings

    monkeypatch.setattr(settings, "app_cache_dir", "/gibt/es/nicht")
    assert audiostuecke.arbeitsordner() is None


def test_der_schnitt_landet_nicht_in_tmp() -> None:
    """Die Regression, um die es geht."""
    from app.tasks import transcribe

    quelle = " ".join(inspect.getsource(transcribe._stueckweise).split())
    assert "dir=audiostuecke.arbeitsordner()" in quelle
