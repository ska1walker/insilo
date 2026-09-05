"""Prüft den Torwächter vor dem Backend und die abgeschaltete Selbstbedienung.

Der Anlass: das Backend hat bewusst keine Entrance und damit keinen
Envoy-Sidecar (Begründung im OlaresManifest). Damit stand
`insilo-backend:8000` jedem Pod im Cluster offen, und `X-Bfl-User` war
frei behauptbar — wer den Dienst erreichte, war, wer er zu sein
behauptete. Dazu legte ein unbekannter Name stillschweigend eine eigene
Organisation an.

Der wichtigste Test hier ist `test_geheimnis_haengt_am_richtigen_namen`.
Beim Prüflauf am 5.9. war der Torwächter offen, obwohl alles eingerichtet
schien: Pydantic las `INTERNAL_TOKEN`, der Helm-Chart setzte
`INSILO_INTERNAL_TOKEN`. Dieselbe Falle wie beim Whisper-Modell in
v0.1.52 — und ohne Test fällt sie erst auf, wenn jemand sie ausnutzt.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings

WURZEL = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Die Namen der Umgebungsvariablen
# ---------------------------------------------------------------------------


def test_geheimnis_haengt_am_richtigen_namen(monkeypatch: pytest.MonkeyPatch) -> None:
    """`INSILO_INTERNAL_TOKEN` — genau so, wie der Chart es setzt.

    Ohne den ausdrücklichen Aliasnamen liest Pydantic `INTERNAL_TOKEN`.
    Der Torwächter bliebe dann offen und **nichts würde es melden**: die
    App läuft, die Oberfläche funktioniert, nur die Prüfung greift nie.
    """
    monkeypatch.setenv("INSILO_INTERNAL_TOKEN", "geheim")
    assert Settings(_env_file=None).internal_token == "geheim"


def test_selbstbedienung_haengt_am_richtigen_namen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INSILO_AUTO_PROVISION", "1")
    assert Settings(_env_file=None).auto_provision is True


def test_selbstbedienung_ist_ohne_zutun_aus() -> None:
    """Die Vorgabe entscheidet, was in Betrieb gilt — das Deployment setzt nichts."""
    assert Settings(_env_file=None).auto_provision is False


def test_der_chart_setzt_beide_namen_so() -> None:
    """Der Name im Chart und der im Code müssen derselbe sein.

    Genau hier ist die Kette am 5.9. gerissen.
    """
    deployment = (WURZEL / "olares/templates/deployment-backend.yaml").read_text(encoding="utf-8")
    assert "INSILO_INTERNAL_TOKEN" in deployment
    assert "secretKeyRef" in deployment
    # Selbstbedienung darf im Deployment gar nicht auftauchen.
    assert "INSILO_AUTO_PROVISION" not in deployment


def test_das_geheimnis_erreicht_auch_das_frontend() -> None:
    """Sonst hängt der Next.js-Server nichts an und alles läuft in 401."""
    frontend = (WURZEL / "olares/templates/deployment-frontend.yaml").read_text(encoding="utf-8")
    assert "INSILO_INTERNAL_TOKEN" in frontend
    assert "insilo-internal" in frontend
    # Kein NEXT_PUBLIC_-Präfix: das Geheimnis darf nicht ins Bundle.
    assert "NEXT_PUBLIC_INSILO_INTERNAL" not in frontend


# ---------------------------------------------------------------------------
# Das Verhalten am Tor
# ---------------------------------------------------------------------------


def _klient(monkeypatch: pytest.MonkeyPatch, geheimnis: str) -> TestClient:
    from app import main
    from app.config import settings

    monkeypatch.setattr(settings, "internal_token", geheimnis)
    # `raise_server_exceptions=False`: ohne Datenbank scheitern die
    # Endpunkte dahinter — geprüft wird hier nur, wer überhaupt
    # durchgelassen wird.
    return TestClient(main.app, raise_server_exceptions=False)


def test_ohne_geheimnis_kommt_niemand_durch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Fremdpod-Fall: beliebige Identität, kein Geheimnis."""
    klient = _klient(monkeypatch, "geheim")
    antwort = klient.get("/api/v1/meetings", headers={"X-Bfl-User": "wer-auch-immer"})
    assert antwort.status_code == 401


def test_falsches_geheimnis_kommt_nicht_durch(monkeypatch: pytest.MonkeyPatch) -> None:
    klient = _klient(monkeypatch, "geheim")
    antwort = klient.get(
        "/api/v1/meetings",
        headers={"X-Bfl-User": "alice", "X-Insilo-Internal": "geraten"},
    )
    assert antwort.status_code == 401


def test_health_bleibt_offen(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Kubelet-Probes haben kein Geheimnis.

    Wären sie mit abgeriegelt, würde Kubernetes die Pods dauerhaft als
    ungesund einstufen und im Kreis neu starten.
    """
    klient = _klient(monkeypatch, "geheim")
    assert klient.get("/health").status_code == 200


def test_externe_schnittstelle_bleibt_am_torwaechter_vorbei(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sie weist sich mit einem Zugriffsschlüssel aus und prüft selbst.

    Ein 401 ist hier richtig — aber es muss von der Schlüsselprüfung
    kommen, nicht vom Torwächter. Der Unterschied steht im Text.
    """
    klient = _klient(monkeypatch, "geheim")
    antwort = klient.get("/api/external/v1/meetings")
    assert antwort.status_code == 401
    assert "Authorization" in antwort.json()["detail"]


def test_ohne_eingerichtetes_geheimnis_bleibt_das_tor_offen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sonst bräche ein Upgrade ohne Secret die ganze App.

    Der Preis ist, dass eine fehlende Einrichtung nicht auffällt —
    deshalb sagt es der Start deutlich ins Protokoll.
    """
    klient = _klient(monkeypatch, "")
    antwort = klient.get("/api/v1/meetings", headers={"X-Bfl-User": "alice"})
    assert antwort.status_code != 401


# ---------------------------------------------------------------------------
# Der Browser darf die Identität nicht mehr behaupten
# ---------------------------------------------------------------------------


def test_authelia_gewinnt_ueber_den_browser() -> None:
    """Die Identität wird serverseitig ersetzt, sobald Authelia sie liefert.

    Am 5.9. an der Box nachgemessen: der Envoy-Sidecar setzt
    `X-Bfl-User` **nicht** — kein `request_headers_to_add`, und
    `allowed_upstream_headers` kennt nur `authorization`,
    `proxy-authorization`, `remote-*` und `authelia-*`. Die Kopfzeile
    einfach wegzulassen hätte die Anmeldung abgeschaltet.

    Also bleibt sie, wird aber überschrieben, wo Authelia etwas sagt:
    `Remote-User` gewinnt. Fällt das weg, ist die Absicherung still
    verschwunden.
    """
    quelle = (WURZEL / "frontend/middleware.ts").read_text(encoding="utf-8")
    assert 'request.headers.get("Remote-User")' in quelle
    assert 'kopfzeilen.set("X-Bfl-User", vonAuthelia)' in quelle


def test_middleware_haengt_das_geheimnis_serverseitig_an() -> None:
    """Und entfernt, was der Browser selbst mitgeschickt hat."""
    quelle = (WURZEL / "frontend/middleware.ts").read_text(encoding="utf-8")
    assert "process.env.INSILO_INTERNAL_TOKEN" in quelle
    assert 'kopfzeilen.set("X-Insilo-Internal"' in quelle
    assert 'kopfzeilen.delete("X-Insilo-Internal")' in quelle
    # Kein `NEXT_PUBLIC_`-Zugriff: was so heißt, landet im Bundle und
    # damit im Browser. (Der Begriff darf im Kommentar stehen — geprüft
    # wird die Verwendung.)
    assert "process.env.NEXT_PUBLIC" not in quelle


# ---------------------------------------------------------------------------
# Zeilensicherheit
# ---------------------------------------------------------------------------


def test_zeilensicherheit_wird_erzwungen_und_drei_tabellen_ausgenommen() -> None:
    """`enable` allein trägt nicht — das Backend ist Eigentümerin der Tabellen.

    Ausgenommen bleiben `users`, `orgs` und `user_org_roles`: die
    Anmeldung löst die Identität auf, bevor es einen Kontext gibt, den
    die Regeln lesen könnten.
    """
    sql = (WURZEL / "supabase/migrations/0017_zeilensicherheit_erzwingen.sql").read_text(
        encoding="utf-8"
    )
    assert "force row level security" in sql
    for ausgenommen in ("'users'", "'orgs'", "'user_org_roles'"):
        assert ausgenommen not in sql, f"{ausgenommen} darf nicht mitgezwungen werden"
    for gezwungen in ("'meetings'", "'transcripts'", "'summaries'", "'audit_log'"):
        assert gezwungen in sql


def test_jeder_router_setzt_den_nutzerkontext() -> None:
    """Ein `acquire()` ohne Kontext liefe unter erzwungener Sicherheit leer.

    Ausnahmen sind benannt: `auth.py` löst die Identität erst auf, und
    das Protokoll schreibt über eine eigene Regel.
    """
    ohne_kontext: list[str] = []
    for p in sorted((WURZEL / "backend/app/routers").glob("*.py")):
        for nr, zeile in enumerate(p.read_text(encoding="utf-8").split("\n"), 1):
            if re.search(r"\bacquire\(\) as conn", zeile):
                ohne_kontext.append(f"{p.name}:{nr}")
    assert not ohne_kontext, (
        "Router ohne Nutzerkontext (acquire statt acquire_as): " + ", ".join(ohne_kontext)
    )


def test_health_checks_lesen_org_tabellen_mit_kontext() -> None:
    """Sonst melden sie das Gegenteil der Wirklichkeit.

    Beim Ausrollen von v0.1.82 auf die Box gefunden: beide Checks lasen
    `org_settings` ohne Kontext und sahen unter der erzwungenen
    Zeilensicherheit **null Zeilen**. `/health/llm` meldete „nicht
    eingerichtet", obwohl eine Adresse eingetragen war — und `/health/stt`
    meldete `mode=local` für eine Box, deren Ton an einen externen Dienst
    geht.

    Der zweite Fall ist der Grund für diesen Test: eine Anwendung, die
    Datensouveränität nachweisen soll, darf den Weg nach draußen nicht
    unterschlagen.
    """
    quelle = (WURZEL / "backend/app/main.py").read_text(encoding="utf-8")
    for name in ("health_llm", "health_stt"):
        anfang = quelle.index(f"async def {name}(")
        ende = quelle.index("@app.get", anfang + 10)
        rumpf = quelle[anfang:ende]
        assert "org_settings" in rumpf, f"{name} liest org_settings nicht mehr — Test anpassen"
        assert "acquire_als_dienst()" in rumpf, (
            f"{name} liest eine org-gebundene Tabelle ohne Kontext und sieht nichts"
        )


def test_hintergrundaufgaben_kennzeichnen_ihre_verbindung() -> None:
    """Sonst sähen sie unter erzwungener Sicherheit keine Zeile."""
    for name in ("transcribe", "summarize", "embed", "notify", "aufraeumen"):
        quelle = (WURZEL / f"backend/app/tasks/{name}.py").read_text(encoding="utf-8")
        assert "dienst_kontext(conn)" in quelle, f"{name} läuft ohne Dienst-Kontext"


def test_saatgut_laeuft_als_dienst() -> None:
    """Werksvorlagen haben keine Organisation — die Nutzerregel lässt sie nicht durch.

    Ohne diese Zeile scheitert `seed.sql` mit „new row violates
    row-level security policy" bei **jeder** Neuinstallation. Gefunden
    beim Einspielen auf eine Kopie, nicht beim Lesen.
    """
    saat = (WURZEL / "supabase/seed.sql").read_text(encoding="utf-8")
    assert "set_config('app.dienst', '1', false)" in saat
