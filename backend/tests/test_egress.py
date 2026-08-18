"""Prüft die Erkennung box-interner Ziele.

Diese Funktion entscheidet, ob dem Nutzer „Alles bleibt auf dieser Box"
angezeigt wird. Eine falsche Zusage ist hier teurer als jede andere
Fehlfunktion in Insilo — deshalb steht sie unter Test, inklusive der
Fälle, in denen sie bewusst pessimistisch sein soll.
"""

from __future__ import annotations

import pytest

from app.egress import ist_boxintern

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
