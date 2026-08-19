"""Prüft die Erkennung box-interner Ziele.

Diese Funktion entscheidet, ob dem Nutzer „Alles bleibt auf dieser Box"
angezeigt wird. Eine falsche Zusage ist hier teurer als jede andere
Fehlfunktion in Insilo — deshalb steht sie unter Test, inklusive der
Fälle, in denen sie bewusst pessimistisch sein soll.
"""

from __future__ import annotations

import pytest

from app.egress import ist_boxintern, ist_eigene_zone
from app.llm_config import LLMConfig, auth_header

# ─── bleibt in der Box ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        # Kubernetes: kurzer Dienstname im eigenen Namespace
        "http://insilo-whisper:8001",
        "http://litellm-svc/v1",
        # Namespace-Pfad und vollqualifiziert
        "http://litellm-svc.litellm-kai.svc.cluster.local/v1",
        "http://citus-headless.user-system-kai.svc/v1",
        # Loopback
        "http://localhost:11434/v1",
        "http://127.0.0.1:8000",
        "http://[::1]:8000",
        # Privates Kundennetz
        "http://192.168.1.17:11434/v1",
        "http://10.0.0.5/v1",
        "http://172.16.3.9:8080",
        # Kein Ziel konfiguriert = es geht nichts hinaus
        "",
        "   ",
    ],
)
def test_intern(url: str) -> None:
    assert ist_boxintern(url) is True


# ─── verlässt die Box ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        "https://api.openai.com/v1",
        "https://api.anthropic.com/v1",
        "https://generativelanguage.googleapis.com/v1",
        "http://duo.aimighty.de/api",
        # Öffentliche IP
        "http://8.8.8.8:11434/v1",
        # Sieht intern aus, ist es aber nicht
        "https://localhost.evil.example/v1",
        "https://cluster.local.example.com/v1",
    ],
)
def test_extern(url: str) -> None:
    assert ist_boxintern(url) is False


# ─── im Zweifel extern ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        "kaputt",  # kein Schema, kein Host
        "http://",  # leerer Host
        "://x",
    ],
)
def test_unklar_gilt_als_extern(url: str) -> None:
    """Was nicht eindeutig intern ist, wird nicht als intern gemeldet.

    Ein zu Unrecht angezeigter Hinweis kostet eine Rückfrage. Eine zu
    Unrecht angezeigte Entwarnung kostet das Kernversprechen.
    """
    assert ist_boxintern(url) is False


def test_grossschreibung_und_punkt_am_ende() -> None:
    assert ist_boxintern("http://INSILO-Whisper:8001") is True
    assert ist_boxintern("http://litellm.svc.cluster.local./v1") is True
    assert ist_boxintern("https://API.OpenAI.com/v1") is False


# ─── eigene Box unter öffentlicher Adresse ────────────────────────────

ZONE = "kaivostudio.olares.de"


@pytest.mark.parametrize(
    "url",
    [
        "https://llm.kaivostudio.olares.de/v1",
        "https://e5d605f3.kaivostudio.olares.de/api",
        "https://kaivostudio.olares.de/v1",
        "https://LLM.KaivoStudio.Olares.DE/v1",   # Groß-/Kleinschreibung
        "https://llm.kaivostudio.olares.de./v1",  # Punkt am Ende
    ],
)
def test_eigene_zone(url: str) -> None:
    assert ist_eigene_zone(url, ZONE) is True


@pytest.mark.parametrize(
    "url",
    [
        "https://api.openai.com/v1",
        # Fremde Olares-Box — andere Zone, nicht unsere
        "https://llm.anderernutzer.olares.de/v1",
        # Sieht ähnlich aus, ist es aber nicht: die Zone muss auf einer
        # Punktgrenze enden, sonst wäre "boesekaivostudio.olares.de" dabei
        "https://boesekaivostudio.olares.de/v1",
        # Zone als Präfix statt Suffix
        "https://kaivostudio.olares.de.angreifer.example/v1",
    ],
)
def test_fremde_zone(url: str) -> None:
    assert ist_eigene_zone(url, ZONE) is False


def test_ohne_zone_keine_aussage() -> None:
    """Ohne OLARES_ZONE lässt sich nichts belegen — dann nicht behaupten."""
    assert ist_eigene_zone("https://llm.kaivostudio.olares.de/v1", "") is False
    assert ist_eigene_zone("https://llm.kaivostudio.olares.de/v1", None) is False


def test_eigene_zone_ist_nicht_clusterintern() -> None:
    """Beide Begriffe sauber trennen: die öffentliche Route verlässt die
    Box tatsächlich, auch wenn sie zurückkommt."""
    url = "https://llm.kaivostudio.olares.de/v1"
    assert ist_eigene_zone(url, ZONE) is True
    assert ist_boxintern(url) is False


# ─── kein Endpunkt eingerichtet ───────────────────────────────────────


def test_leere_konfiguration_ist_nicht_eingerichtet() -> None:
    """Ohne Adresse ist nichts anzusprechen — und nichts zu behaupten."""
    assert LLMConfig(base_url="", api_key="", model="").eingerichtet is False
    assert LLMConfig(base_url="   ", api_key="k", model="m").eingerichtet is False


def test_gesetzte_adresse_ist_eingerichtet() -> None:
    assert LLMConfig(
        base_url="https://llm.kaivostudio.olares.de/v1", api_key="k", model="m"
    ).eingerichtet is True


def test_leere_adresse_gilt_weder_als_intern_noch_als_eigene_box() -> None:
    """Sonst würde eine fehlende Einrichtung als Entwarnung durchgehen.

    `ist_boxintern("")` ist bewusst True (kein Ziel = nichts geht hinaus),
    deshalb muss der Aufrufer den leeren Fall vorher abfangen — genau das
    prüft der Router über `eingerichtet`.
    """
    assert ist_eigene_zone("", ZONE) is False


# ─── Kopfzeile zum Endpunkt ───────────────────────────────────────────


def test_ohne_schluessel_keine_kopfzeile() -> None:
    """`Bearer ` mit leerem Wert ist kein gültiger Kopfwert.

    httpx lehnt ihn mit „Illegal header value" ab, bevor die Verbindung
    zustande kommt — der Nutzer sah einen Verbindungsfehler, wo der
    Endpunkt nie angesprochen wurde. Seit v0.1.72 ist der leere Schlüssel
    der Normalfall, also darf er keinen Fehler mehr erzeugen.
    """
    assert auth_header("") == {}
    assert auth_header("   ") == {}
    assert auth_header(None) == {}  # type: ignore[arg-type]


def test_mit_schluessel_kopfzeile_gesetzt() -> None:
    assert auth_header("sk-123") == {"Authorization": "Bearer sk-123"}
    # Umschließende Leerzeichen aus dem Formular fallen weg — sonst wäre
    # der Kopfwert wieder ungültig.
    assert auth_header("  sk-123  ") == {"Authorization": "Bearer sk-123"}


def test_konfiguration_liefert_dieselbe_kopfzeile() -> None:
    ohne = LLMConfig(base_url="https://llm.example/v1", api_key="", model="m")
    mit = LLMConfig(base_url="https://llm.example/v1", api_key="sk-9", model="m")
    assert ohne.auth_header == {}
    assert mit.auth_header == {"Authorization": "Bearer sk-9"}
