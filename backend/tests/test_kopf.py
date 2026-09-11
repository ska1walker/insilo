"""Prüft, was von einer Zusammenfassung oben steht.

Der Anlass war ein Blick auf die fertige Besprechung: sechs bis zehn
Felder gleichen Gewichts untereinander, darunter der vollständige
Wortlaut. Bei einer Stunde Besprechung ist das Transkript rund zehnmal
so lang wie die Zusammenfassung — was jemand eigentlich sucht, steht
dann irgendwo dazwischen.

Zwei Eigenschaften tragen die Lösung:

1. **Die Reihenfolge steht im Backend**, nicht im Bauteil. Ansicht und
   Markdown-Datei fragen dieselbe Funktion; sonst liefen sie
   auseinander, sobald jemand eine Vorlage ändert.
2. **Eine Vorlage kann widersprechen.** Es gibt fünf Werks-Vorlagen und
   eigene Felder obendrein. Eine fest verdrahtete Liste von Feldnamen
   gäbe einer Kanzlei-Vorlage („Anliegen, Sachverhalt, Fristen") einen
   leeren Kopf.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.exports.markdown import (
    KOPF_FELDER,
    rang,
    render_meeting_markdown,
    sortieren,
)

WURZEL = Path(__file__).resolve().parents[2]

# Die Felder der fünf Werks-Vorlagen, wie sie in supabase/seed.sql stehen.
WERKS_VORLAGEN: dict[str, list[str]] = {
    "Allgemeine Besprechung": [
        "_analyse", "kurzfassung", "anwesende", "kernthemen",
        "wichtige_aussagen", "beschluesse", "offene_fragen", "naechste_schritte",
    ],
    "Mandantengespräch": [
        "_analyse", "kurzfassung", "mandantenname", "sachverhalt", "rechtsfragen",
        "eingebrachte_unterlagen", "vereinbarte_leistungen",
        "wichtige_termine_fristen", "honorarvereinbarung", "naechste_schritte_mandat",
    ],
    "Vertriebsgespräch": [
        "_analyse", "kurzfassung", "kunde", "schmerzpunkte", "aktuelle_loesung",
        "bant", "einwaende", "vereinbarte_naechste_schritte", "follow_up_datum",
        "verkaufschance_einschaetzung",
    ],
    "Jahresgespräch": [
        "_analyse", "kurzfassung", "kunde", "anwesende", "bestandsuebersicht",
        "risikoveraenderungen", "cross_selling_potenziale", "kundenwuensche",
        "beschluesse", "wiedervorlage",
    ],
    "Schnellnotiz": ["_analyse", "kerninhalt", "naechste_schritte", "kontext"],
}


def _gefuellt(felder: list[str]) -> dict[str, str]:
    return {f: "x" for f in felder}


# ---------------------------------------------------------------------------
# Jede Werks-Vorlage bekommt einen brauchbaren Kopf
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("vorlage", sorted(WERKS_VORLAGEN))
def test_jede_werksvorlage_hat_einen_kopf(vorlage: str) -> None:
    """Ein leerer Kopf wäre schlimmer als gar keine Sortierung.

    Dann stünde die Besprechung unter „Mehr" und der sichtbare Teil wäre
    leer — genau das Gegenteil der Absicht.
    """
    kopf, mehr = sortieren(_gefuellt(WERKS_VORLAGEN[vorlage]))
    assert kopf, f"{vorlage} hätte einen leeren Kopf"
    assert 2 <= len(kopf) <= 4, f"{vorlage}: {len(kopf)} Felder im Kopf — {kopf}"
    assert mehr, f"{vorlage} klappt gar nichts ein — dann bringt es nichts"


def test_die_kurzfassung_steht_ganz_oben() -> None:
    kopf, _ = sortieren(_gefuellt(WERKS_VORLAGEN["Allgemeine Besprechung"]))
    assert kopf[0] == "kurzfassung"


def test_aufgaben_stehen_vor_dem_thema() -> None:
    """Was zu tun ist, kommt vor dem, worum es ging.

    Wer nach einer Besprechung draufschaut, sucht seine Aufgabe, nicht
    die Tagesordnung.
    """
    kopf, _ = sortieren(_gefuellt(WERKS_VORLAGEN["Allgemeine Besprechung"]))
    assert kopf.index("beschluesse") < kopf.index("kernthemen")
    assert kopf.index("naechste_schritte") < kopf.index("kernthemen")


def test_beschluesse_vor_offenen_aufgaben() -> None:
    """Beschlüsse tragen Verantwortliche und Frist, offene Aufgaben nicht."""
    kopf, _ = sortieren(_gefuellt(WERKS_VORLAGEN["Allgemeine Besprechung"]))
    assert kopf.index("beschluesse") < kopf.index("naechste_schritte")


# ---------------------------------------------------------------------------
# Leeres bleibt draußen
# ---------------------------------------------------------------------------


def test_leere_felder_stehen_weder_oben_noch_unten() -> None:
    inhalt = {
        "kurzfassung": "Ein Satz.",
        "beschluesse": [],
        "kernthemen": None,
        "anwesende": "",
        "offene_fragen": ["offen"],
    }
    kopf, mehr = sortieren(inhalt)
    assert kopf == ["kurzfassung"]
    assert mehr == ["offene_fragen"]


def test_die_denkfelder_des_modells_werden_nicht_einsortiert() -> None:
    kopf, mehr = sortieren({"_analyse": "gedacht", "kurzfassung": "gesagt"})
    assert kopf == ["kurzfassung"]
    assert mehr == []


# ---------------------------------------------------------------------------
# Eine Vorlage darf widersprechen
# ---------------------------------------------------------------------------


def test_eine_vorlage_kann_ein_feld_hochstufen() -> None:
    """Ohne das bekäme eine eigene Vorlage einen leeren Kopf."""
    schema = {"properties": {"aktenzeichen": {"type": "string", "x-rang": "kopf"}}}
    kopf, mehr = sortieren({"aktenzeichen": "2026-014", "anwesende": ["A"]}, schema)
    assert kopf == ["aktenzeichen"]
    assert mehr == ["anwesende"]


def test_eine_vorlage_kann_ein_feld_herunterstufen() -> None:
    schema = {"properties": {"kernthemen": {"type": "array", "x-rang": "mehr"}}}
    kopf, mehr = sortieren({"kurzfassung": "x", "kernthemen": ["a"]}, schema)
    assert kopf == ["kurzfassung"]
    assert mehr == ["kernthemen"]


def test_ein_unsinniger_rang_wird_ignoriert() -> None:
    """Ein Tippfehler im Schema darf kein Feld verschwinden lassen."""
    schema = {"properties": {"kernthemen": {"x-rang": "oben"}}}
    kopf, _ = sortieren({"kernthemen": ["a"]}, schema)
    assert kopf == ["kernthemen"], "Vorbelegung hätte greifen müssen"


def test_ein_unbekanntes_feld_landet_unter_mehr() -> None:
    """Eigene Felder ohne Angabe verdrängen den Kopf nicht."""
    assert rang("aktenzeichen") == "mehr"
    kopf, mehr = sortieren({"kurzfassung": "x", "aktenzeichen": "2026-014"})
    assert kopf == ["kurzfassung"]
    assert mehr == ["aktenzeichen"]


# ---------------------------------------------------------------------------
# Eine Stelle, nicht zwei
# ---------------------------------------------------------------------------


def test_die_datei_folgt_derselben_reihenfolge() -> None:
    """Ansicht und Markdown-Datei müssen dasselbe zuerst zeigen.

    Die Datei kennt kein Aufklappen, also steht alles untereinander —
    aber in der Reihenfolge, in der jemand es liest.
    """
    inhalt = {
        "anwesende": ["Dr. Beispiel"],
        "kernthemen": ["Nachtrag"],
        "beschluesse": [{"beschluss": "Frist setzen", "frist": "30.11."}],
        "kurzfassung": "Die Forderung wird durchgesetzt.",
    }
    text = render_meeting_markdown(
        meeting={"id": "x", "title": "T", "recorded_at": None, "duration_sec": 60},
        transcript=None,
        summary={"content": inhalt},
        include_transcript=False,
    )
    stellen = {f: text.index(t) for f, t in (
        ("kurzfassung", "Kurzfassung"),
        ("beschluesse", "Beschlüsse"),
        ("kernthemen", "Kernthemen"),
        ("anwesende", "Anwesende"),
    )}
    assert stellen["kurzfassung"] < stellen["beschluesse"] < stellen["kernthemen"]
    assert stellen["kernthemen"] < stellen["anwesende"]


def test_die_oberflaeche_fuehrt_keine_eigene_feldliste() -> None:
    """Eine zweite Tabelle mit Feldnamen wäre die nächste, die veraltet.

    `summary-view.tsx` bekommt Kopf und Rest fertig vom Endpunkt. Steht
    dort wieder ein Feldname im Quelltext, ist die eine Stelle keine mehr.
    """
    quelle = (WURZEL / "frontend/components/summary-view.tsx").read_text(
        encoding="utf-8"
    )
    assert "summary.kopf" in quelle
    for feld in ("kernthemen", "beschluesse", "naechste_schritte", "kurzfassung"):
        assert feld not in quelle, (
            f"'{feld}' steht wieder in summary-view.tsx — die Reihenfolge "
            "gehört ins Backend"
        )


def test_der_endpunkt_liefert_kopf_und_rest_mit() -> None:
    quelle = (WURZEL / "backend/app/routers/meetings.py").read_text(encoding="utf-8")
    assert "from app.exports.markdown import sortieren" in quelle
    assert '"kopf": kopf' in quelle
    assert "t.output_schema" in quelle


# ---------------------------------------------------------------------------
# Die Vorbelegung und die Werks-Vorlagen müssen zusammenpassen
# ---------------------------------------------------------------------------


def test_kein_kopf_feld_ohne_beschriftung() -> None:
    """Ein Feld oben ohne Namen wäre eine Überschrift aus Unterstrichen."""
    labels = json.loads(
        (WURZEL / "frontend/messages/de.json").read_text(encoding="utf-8")
    )["summaryLabels"]
    ohne = [f for f in KOPF_FELDER if f not in labels]
    assert not ohne, f"ohne Beschriftung in de.json: {ohne}"


def test_die_werksvorlagen_kennen_die_kurzfassung() -> None:
    """Vier ja, die Schnellnotiz nicht — die *ist* die Kurzfassung."""
    seed = (WURZEL / "supabase/seed.sql").read_text(encoding="utf-8")
    schemata = re.findall(r"\$schema\$(\{.*?\})\$schema\$", seed, re.S)
    assert len(schemata) == 5, f"{len(schemata)} Vorlagen — Test anpassen"

    mit = [i for i, b in enumerate(schemata) if "kurzfassung" in json.loads(b)["properties"]]
    assert mit == [0, 1, 2, 3], f"Vorlagen mit Kurzfassung: {mit}"

    for i in mit:
        d = json.loads(schemata[i])
        assert "kurzfassung" in d["required"], (
            f"Vorlage {i}: kurzfassung ist nicht verlangt — dann füllt das "
            "Modell sie im JSON-Modus nicht zuverlässig"
        )


def test_die_werksvorlagen_aendert_nur_der_seed() -> None:
    """Eine Migration, die an den Werks-Vorlagen dreht, ist wirkungslos.

    Der Init-Container führt jede Datei unter `/sql/` bei jedem Start aus,
    und `0099_seed.sql` endet mit `on conflict (id) do update set
    output_schema = excluded.output_schema, version = excluded.version`.
    Der Seed überschreibt also alles, was eine Migration vorher an ihnen
    geändert hat — auf der Box daran gesehen, dass die Versionsziffer nach
    dem Ausrollen auf 2 stand statt auf 3.
    """
    sql = (WURZEL / "supabase/migrations/0018_kurzfassung.sql").read_text(
        encoding="utf-8"
    )
    ohne_kommentar = "\n".join(
        z for z in sql.splitlines() if not z.lstrip().startswith("--")
    )
    assert "public.templates" not in ohne_kommentar or "comment on column" in ohne_kommentar
    assert "update public.templates" not in ohne_kommentar, (
        "0018 ändert wieder Vorlagen — der Seed macht das gleich zunichte"
    )


def test_der_seed_zaehlt_die_vorlagen_hoch() -> None:
    """Ein geändertes Schema ohne neue Versionsziffer ist eine stille Lüge.

    `summaries.template_version` hält fest, welche Fassung eine
    Zusammenfassung erzeugt hat. Bliebe sie stehen, sähen zwei
    Zusammenfassungen aus derselben Fassung verschieden aus.
    """
    seed = (WURZEL / "supabase/seed.sql").read_text(encoding="utf-8")
    bloecke = seed.split("-- ============================================================")
    fuer_vorlagen = [b for b in bloecke if "output_schema" in b or "kurzfassung" in b]
    mit_kurzfassung = [b for b in fuer_vorlagen if "kurzfassung" in b]
    assert len(mit_kurzfassung) == 4, f"{len(mit_kurzfassung)} Vorlagen mit Kurzfassung"
    for b in mit_kurzfassung:
        assert re.search(r"\n  3\n\)", b), (
            "eine Vorlage mit Kurzfassung steht noch auf der alten Version"
        )


def test_die_oberflaeche_kennt_dieselben_tat_felder() -> None:
    """Ein Beschluss führt mit dem Beschluss, nicht mit der Frist.

    `jsonb` behält die Schlüsselreihenfolge nicht — Postgres sortiert
    nach Länge, also stand `frist` vor `beschluss`. Auf der Box gesehen,
    nachdem die Beschlüsse in den Kopf gewandert waren. Beide Seiten
    müssen dasselbe Feld für den Satz halten, sonst liest sich die Datei
    anders als die Ansicht.
    """
    from app.exports.markdown import _TASK_OBJECT_KEYS

    quelle = (WURZEL / "frontend/components/summary-view.tsx").read_text(
        encoding="utf-8"
    )
    block = quelle[quelle.index("const TAT_FELDER") : quelle.index("] as const;")]
    vorne = {m.strip().strip('",') for m in block.splitlines() if '"' in m}
    fehlend = _TASK_OBJECT_KEYS - vorne
    assert not fehlend, f"summary-view.tsx kennt diese Felder nicht: {sorted(fehlend)}"


# ---------------------------------------------------------------------------
# Der Fall, den erst die Box gezeigt hat
# ---------------------------------------------------------------------------


def test_ohne_kopf_wird_nichts_eingeklappt() -> None:
    """Zwölf von zwölf Zusammenfassungen auf der Box hatten `kopf: []`.

    Kurze Aufnahmen, bei denen das Modell nur `anwesende` und
    `wichtige_aussagen` gefüllt hat — beides gehört unter „Mehr", und
    eine Kurzfassung gab es für sie noch nicht. Wäre es dabei geblieben,
    zeigte die Zusammenfassung oben **nichts** und versteckte alles
    hinter einem Aufklapper.

    Die Tests oben füllen jedes Feld und kommen an diesen Fall nie heran.
    Gefunden hat ihn erst der Abruf gegen die laufende Box.
    """
    kopf, mehr = sortieren({"anwesende": ["A"], "wichtige_aussagen": ["x"]})
    assert kopf == ["anwesende", "wichtige_aussagen"]
    assert mehr == [], "es gibt nichts, was den Kopf tragen würde — also kein Aufklapper"


def test_ein_einziges_kopf_feld_reicht_aber() -> None:
    """Sobald oben etwas steht, darf der Rest weg."""
    kopf, mehr = sortieren({"kurzfassung": "Ein Satz.", "anwesende": ["A"]})
    assert kopf == ["kurzfassung"]
    assert mehr == ["anwesende"]
