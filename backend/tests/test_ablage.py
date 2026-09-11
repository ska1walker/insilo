"""Prüft die Markdown-Dateien neben der Tonaufnahme.

Bis hierher lag im Datenverzeichnis nur die Tonspur. Wer die Besprechung
außerhalb von Insilo brauchte, kam nur über die Oberfläche oder die
Schnittstelle daran — ein Backup von `/app/data` trug den Ton, aber nicht
das, was gesagt wurde.

Zwei Eigenschaften tragen das Ganze, und beide stehen hier als Test:

1. Die Dateien **kommen**, sobald es Inhalt gibt — auch ohne
   eingerichtetes Sprachmodell, wenn also nie eine Zusammenfassung folgt.
2. Die Dateien **gehen**, wenn die Besprechung endgültig verschwindet.
   Sonst hätte „endgültig entfernen" den Gesprächsinhalt auf der Platte
   stehen gelassen — in einem Produkt, dessen ganzer Zweck das Gegenteil
   ist.
"""

from __future__ import annotations

import inspect
import json
from uuid import UUID

import pytest

from app import ablage, audit

ORG = UUID("11111111-1111-4111-8111-111111111111")
BESPRECHUNG = UUID("d0000000-0000-4000-8000-000000000001")

SEGMENTE = [
    {"start": 0.0, "end": 4.0, "text": "Guten Morgen.", "speaker": "s1"},
    {"start": 4.0, "end": 9.0, "text": "Zur Nachtragsforderung.", "speaker": "s2"},
]
SPRECHER = [{"id": "s1", "name": "Dr. Beispiel"}, {"id": "s2", "name": "Herr Muster"}]
INHALT = {"anliegen": "Durchsetzung offener Nachtragsforderungen."}


# ---------------------------------------------------------------------------
# Eine Verbindung, die sich wie asyncpg benimmt — ohne Datenbank
# ---------------------------------------------------------------------------


class Verbindung:
    """Liefert die vier Abfragen aus `ablage._einsammeln`.

    `jsonb_als_text` bildet nach, was asyncpg ohne gesetzten Codec tut:
    jsonb kommt als Zeichenkette zurück. Genau daran ist der
    Konfigurations-Abzug in v0.1.81 schon einmal gescheitert.
    """

    def __init__(
        self,
        *,
        transkript: bool = True,
        zusammenfassung: bool = True,
        besprechung: bool = True,
        jsonb_als_text: bool = False,
    ) -> None:
        self.transkript = transkript
        self.zusammenfassung = zusammenfassung
        self.besprechung = besprechung
        self.jsonb_als_text = jsonb_als_text

    def _j(self, wert):
        return json.dumps(wert) if self.jsonb_als_text else wert

    async def fetchrow(self, sql: str, *args):
        if "from public.meetings m" in sql:
            if not self.besprechung:
                return None
            return {
                "id": BESPRECHUNG,
                "org_id": ORG,
                "title": "Mandantengespräch Musterbau GmbH",
                "recorded_at": None,
                "duration_sec": 1847,
                "language": "de",
                "template_name": "Mandantengespräch",
            }
        if "from public.transcripts" in sql:
            if not self.transkript:
                return None
            return {
                "segments": self._j(SEGMENTE),
                "speakers": self._j(SPRECHER),
                "full_text": "Guten Morgen. Zur Nachtragsforderung.",
                "language": "de",
            }
        if "from public.summaries" in sql:
            if not self.zusammenfassung:
                return None
            return {"content": self._j(INHALT), "llm_model": "qwen2.5"}
        raise AssertionError(f"unerwartetes fetchrow: {sql!r}")

    async def fetch(self, sql: str, *args):
        if "from public.meeting_tags" in sql:
            return [{"name": "Mandat 2026-014", "color": "#caa960"}]
        raise AssertionError(f"unerwartetes fetch: {sql!r}")


@pytest.fixture
def speicher(monkeypatch):
    """Fängt ab, was geschrieben und was entfernt würde."""

    geschrieben: dict[str, str] = {}
    entfernt: list[str] = []

    def hoch(key, data, content_type):
        geschrieben[key] = data.decode("utf-8")

    def weg(key):
        entfernt.append(key)

    monkeypatch.setattr(ablage, "upload_bytes", hoch)
    monkeypatch.setattr(ablage, "delete_object", weg)
    return geschrieben, entfernt


# ---------------------------------------------------------------------------
# Wo die Dateien liegen
# ---------------------------------------------------------------------------


def test_dateien_liegen_beim_ton_und_teilen_den_stamm() -> None:
    """Der Punkt der Übung: in einer Auflistung stehen die drei beieinander."""
    from app.routers.meetings import _audio_key

    ton = _audio_key(ORG, BESPRECHUNG, "audio/webm")
    t = ablage.schluessel(ORG, BESPRECHUNG, ablage.SUFFIX_TRANSKRIPT)
    z = ablage.schluessel(ORG, BESPRECHUNG, ablage.SUFFIX_ZUSAMMENFASSUNG)

    assert ton == f"{ORG}/{BESPRECHUNG}.webm"
    assert t == f"{ORG}/{BESPRECHUNG}.transkript.md"
    assert z == f"{ORG}/{BESPRECHUNG}.zusammenfassung.md"
    # Gleicher Ordner, gleicher Stamm — nur die Endung trennt sie.
    assert t.rsplit("/", 1)[0] == ton.rsplit("/", 1)[0]
    assert t.startswith(ton[: -len(".webm")])


# ---------------------------------------------------------------------------
# Was geschrieben wird
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_beide_dateien_wenn_beides_da_ist(speicher) -> None:
    geschrieben, _ = speicher
    keys = await ablage.schreiben(Verbindung(), BESPRECHUNG)

    assert sorted(keys) == sorted(geschrieben)
    assert len(geschrieben) == 2
    assert any(k.endswith(ablage.SUFFIX_TRANSKRIPT) for k in geschrieben)
    assert any(k.endswith(ablage.SUFFIX_ZUSAMMENFASSUNG) for k in geschrieben)


@pytest.mark.asyncio
async def test_ohne_sprachmodell_kommt_trotzdem_das_transkript(speicher) -> None:
    """Die wichtigste der beiden Hälften.

    Eine frisch eingerichtete Box hat kein Sprachmodell, also nie eine
    Zusammenfassung. Käme die Datei erst am Ende der Verarbeitung, läge
    dort für immer nur Ton.
    """
    geschrieben, _ = speicher
    await ablage.schreiben(Verbindung(zusammenfassung=False), BESPRECHUNG)

    assert len(geschrieben) == 1
    (key,) = geschrieben
    assert key.endswith(ablage.SUFFIX_TRANSKRIPT)


@pytest.mark.asyncio
async def test_ohne_inhalt_keine_datei(speicher) -> None:
    """Eine Datei, die nur aus einer Kopfzeile besteht, behauptet Inhalt."""
    geschrieben, _ = speicher
    await ablage.schreiben(
        Verbindung(transkript=False, zusammenfassung=False), BESPRECHUNG
    )
    assert geschrieben == {}


@pytest.mark.asyncio
async def test_geloeschte_besprechung_schreibt_nichts(speicher) -> None:
    geschrieben, _ = speicher
    assert await ablage.schreiben(Verbindung(besprechung=False), BESPRECHUNG) == []
    assert geschrieben == {}


# ---------------------------------------------------------------------------
# Was drinsteht
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transkript_traegt_den_wortlaut_mit_sprechernamen(speicher) -> None:
    geschrieben, _ = speicher
    await ablage.schreiben(Verbindung(), BESPRECHUNG)
    text = next(v for k, v in geschrieben.items() if k.endswith(ablage.SUFFIX_TRANSKRIPT))

    assert "# Mandantengespräch Musterbau GmbH" in text
    assert "Zur Nachtragsforderung." in text
    assert "Dr. Beispiel" in text
    assert "Mandat 2026-014" in text


@pytest.mark.asyncio
async def test_die_zusammenfassung_ist_nicht_noch_einmal_das_transkript(speicher) -> None:
    """Sonst läge der Wortlaut zweimal auf der Platte.

    Wer ihn braucht, nimmt die Datei daneben — das ist der ganze Grund,
    warum es zwei sind und nicht eine.
    """
    geschrieben, _ = speicher
    await ablage.schreiben(Verbindung(), BESPRECHUNG)
    text = next(
        v for k, v in geschrieben.items() if k.endswith(ablage.SUFFIX_ZUSAMMENFASSUNG)
    )

    assert "Nachtragsforderungen" in text          # die Zusammenfassung
    assert "Volltranskript" not in text
    assert "Zur Nachtragsforderung." not in text   # der Wortlaut


@pytest.mark.asyncio
async def test_jsonb_als_zeichenkette_wird_wieder_struktur(speicher) -> None:
    """asyncpg ohne Codec gibt jsonb als Text zurück — v0.1.81 lässt grüßen."""
    geschrieben, _ = speicher
    await ablage.schreiben(Verbindung(jsonb_als_text=True), BESPRECHUNG)

    text = next(v for k, v in geschrieben.items() if k.endswith(ablage.SUFFIX_TRANSKRIPT))
    assert "Dr. Beispiel" in text
    # Nicht der rohe JSON-Text, der bei einem Fehlschlag durchschlüge.
    assert '{"start":' not in text


@pytest.mark.asyncio
async def test_markdown_wird_als_text_abgelegt(speicher, monkeypatch) -> None:
    """Sonst bietet ein Browser die Datei zum Herunterladen statt zum Lesen an."""
    typen: list[str] = []
    monkeypatch.setattr(
        ablage, "upload_bytes", lambda k, d, t: typen.append(t)
    )
    await ablage.schreiben(Verbindung(), BESPRECHUNG)
    assert typen and all(t.startswith("text/markdown") for t in typen)


# ---------------------------------------------------------------------------
# Ein klemmender Speicher hält nichts auf
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schreibfehler_haelt_die_verarbeitung_nicht_auf(monkeypatch) -> None:
    """Die Datenbank hat den Inhalt bereits; die Datei ist die Zugabe."""

    def platte_voll(key, data, content_type):
        raise OSError("No space left on device")

    monkeypatch.setattr(ablage, "upload_bytes", platte_voll)
    assert await ablage.schreiben(Verbindung(), BESPRECHUNG) == []


@pytest.mark.asyncio
async def test_lesefehler_haelt_die_verarbeitung_nicht_auf(monkeypatch) -> None:
    class Kaputt:
        async def fetchrow(self, *_a, **_k):
            raise RuntimeError("Verbindung weg")

    assert await ablage.schreiben(Kaputt(), BESPRECHUNG) == []


# ---------------------------------------------------------------------------
# Was geht wieder weg
# ---------------------------------------------------------------------------


def test_entfernen_raeumt_beide(speicher) -> None:
    _, entfernt = speicher
    assert ablage.entfernen(ORG, BESPRECHUNG) is True
    assert entfernt == [
        f"{ORG}/{BESPRECHUNG}.transkript.md",
        f"{ORG}/{BESPRECHUNG}.zusammenfassung.md",
    ]


def test_eine_fehlende_datei_ist_kein_fehler(monkeypatch) -> None:
    def nicht_da(key):
        raise FileNotFoundError(key)

    monkeypatch.setattr(ablage, "delete_object", nicht_da)
    assert ablage.entfernen(ORG, BESPRECHUNG) is True


def test_klemmender_speicher_meldet_sich(monkeypatch) -> None:
    """`False` heißt: die Zeile bleibt stehen, der nächste Lauf holt es nach."""

    def klemmt(key):
        raise OSError("read-only file system")

    monkeypatch.setattr(ablage, "delete_object", klemmt)
    assert ablage.entfernen(ORG, BESPRECHUNG) is False


# ---------------------------------------------------------------------------
# Die beiden Wege, auf denen eine Besprechung endgültig verschwindet
# ---------------------------------------------------------------------------


def test_endgueltig_loeschen_raeumt_die_markdown_dateien() -> None:
    from app.routers.meetings import purge_meeting

    assert "ablage.entfernen" in inspect.getsource(purge_meeting)


def test_der_aufraeumlauf_raeumt_sie_auch() -> None:
    from app.tasks import aufraeumen

    quelle = inspect.getsource(aufraeumen._papierkorb_leeren)
    assert "ablage.entfernen" in quelle
    # Ohne org_id in der Abfrage ließe sich der Schlüssel nicht bilden.
    assert "m.org_id" in quelle


def test_die_aufbewahrungsfrist_laesst_sie_stehen() -> None:
    """Sie holt die Tonspur als Rohmaterial — Transkript und Zusammenfassung
    sind ausdrücklich das, was bleiben soll. Stünde hier ein `entfernen`,
    verlöre die Frist genau den Unterschied, für den es sie gibt.
    """
    from app.tasks import aufraeumen

    assert "ablage" not in inspect.getsource(aufraeumen._aufnahmen_altern)


# ---------------------------------------------------------------------------
# Die Auslöser
# ---------------------------------------------------------------------------


def test_jeder_ausloeser_ist_ein_echter_vorgang() -> None:
    """Ein Tippfehler hier schaltete die Auffrischung still ab.

    `AUSLOESER` wird gegen `audit.deuten` gehalten; ein Name, den keine
    Regel je liefert, würde nie zutreffen und niemandem auffallen.
    """
    unbekannt = ablage.AUSLOESER - set(audit.AKTIONEN)
    assert not unbekannt, f"kein solcher Vorgang: {sorted(unbekannt)}"


def test_die_ausloeser_tragen_eine_besprechungskennung() -> None:
    """Ohne Kennung wüsste die Middleware nicht, welche Dateien gemeint sind."""
    arten = {
        aktion: art
        for _, _, aktion, art in audit._REGELN
        if aktion in ablage.AUSLOESER
    }
    assert set(arten) == set(ablage.AUSLOESER)
    assert all(art == "meeting" for art in arten.values()), arten


@pytest.mark.parametrize(
    ("methode", "pfad"),
    [
        ("PATCH", f"/api/v1/meetings/{BESPRECHUNG}"),
        ("POST", f"/api/v1/meetings/{BESPRECHUNG}/tags"),
        ("PUT", f"/api/v1/meetings/{BESPRECHUNG}/transcript/speakers"),
        ("POST", f"/api/v1/meetings/{BESPRECHUNG}/clusters/0/assign"),
    ],
)
def test_diese_aufrufe_frischen_die_dateien_auf(methode: str, pfad: str) -> None:
    vorgang = audit.deuten(methode, pfad)
    assert vorgang is not None
    assert vorgang.aktion in ablage.AUSLOESER
    assert vorgang.kennung == BESPRECHUNG


@pytest.mark.parametrize(
    ("methode", "pfad"),
    [
        # Lesen ändert nichts.
        ("GET", f"/api/v1/meetings/{BESPRECHUNG}"),
        # In den Papierkorb legen lässt die Dateien stehen — zurückholen
        # soll sie ja wiederfinden.
        ("DELETE", f"/api/v1/meetings/{BESPRECHUNG}"),
        # Und das Endgültige räumt selbst auf, statt neu zu schreiben.
        ("DELETE", f"/api/v1/meetings/{BESPRECHUNG}/permanent"),
    ],
)
def test_diese_aufrufe_nicht(methode: str, pfad: str) -> None:
    vorgang = audit.deuten(methode, pfad)
    assert vorgang is None or vorgang.aktion not in ablage.AUSLOESER


# ---------------------------------------------------------------------------
# Der Nachzug
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nachzug_schreibt_nur_was_fehlt(monkeypatch, speicher) -> None:
    """Der einmalige Fall: Besprechungen von vor der Neuerung.

    Und der bleibende: ein Schreibfehlschlag hält die Verarbeitung
    bewusst nicht auf, also muss ihn jemand nachholen.
    """
    from app.tasks import aufraeumen

    geschrieben, _ = speicher
    vorhanden = {f"{ORG}/{BESPRECHUNG}.transkript.md"}
    monkeypatch.setattr(aufraeumen, "exists", lambda k: k in vorhanden)

    ANDERE = UUID("d0000000-0000-4000-8000-000000000002")

    class Lauf(Verbindung):
        async def fetch(self, sql: str, *args):
            if "from public.meetings m" in sql and "transcripts" in sql:
                return [
                    {"id": BESPRECHUNG, "org_id": ORG},
                    {"id": ANDERE, "org_id": ORG},
                ]
            return await super().fetch(sql, *args)

    ergebnis = await aufraeumen._markdown_nachziehen(Lauf())

    assert ergebnis == {"geschrieben": 1, "geprueft": 2}
    # Nur die fehlende wurde angefasst — die vorhandene blieb liegen.
    assert all(k.startswith(f"{ORG}/") for k in geschrieben)
    assert geschrieben, "die fehlende Datei wurde nicht geschrieben"


def test_der_nachzug_laesst_den_papierkorb_in_ruhe() -> None:
    """Was gelöscht ist, bekommt keine Datei zurück."""
    from app.tasks import aufraeumen

    assert "m.deleted_at is null" in inspect.getsource(aufraeumen._markdown_nachziehen)


def test_die_middleware_haengt_an_derselben_tabelle() -> None:
    """Eine zweite Pfadliste in `main.py` wäre die nächste, die veraltet."""
    from app import main

    quelle = inspect.getsource(main.markdown_ablage)
    assert "audit.deuten" in quelle
    assert "ablage.AUSLOESER" in quelle
