"""Prüft den ersten Zugang auf eine leere Box.

Der Anlass: seit v0.1.85 ist die Selbstbedienung aus — `auto_provision`
steht auf `False` und das Chart setzt `INSILO_AUTO_PROVISION` nie. Damit
legte **niemand** mehr den ersten Nutzer an, und
`konfiguration.wiederherstellen` greift nur, wenn der Abzug im
Datenverzeichnis schon liegt. Eine frisch installierte Box antwortete
ihrem ersten Aufruf deshalb mit

    401 Unknown identity. Ask an administrator to add this user.

und war damit unbenutzbar, bis jemand mit `psql` daneben ging. Gefunden
am 6.9.2026 beim Schreiben des Handbuchs, nicht durch einen Test.

Die Ausnahme ist eng: sie greift **nur**, solange es keine Organisation
gibt. Genau das prüfen die Tests hier — vor allem den zweiten Namen, der
danach anklopft.
"""

from __future__ import annotations

import inspect
import re
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app import auth

ORG = UUID("11111111-1111-4111-8111-111111111111")


# ---------------------------------------------------------------------------
# Eine Verbindung, die sich wie asyncpg benimmt — ohne Datenbank
# ---------------------------------------------------------------------------


class _Transaktion:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False


class Verbindung:
    """Antwortet auf die Abfragen aus `auth.py`, und merkt sich was geschah.

    Bewusst grob: sie ordnet an Merkmalen des SQL zu, nicht an einem
    Parser. Was hier auffällt, wenn jemand eine Abfrage umschreibt, ist
    genau das, was auffallen soll — dann gehört der Test mit angepasst.
    """

    def __init__(self, *, orgs: int = 0, bekannt: str | None = None) -> None:
        self.orgs = orgs
        self.bekannt = bekannt
        self.sperren: list[int] = []
        self.protokoll: list[tuple[str, tuple]] = []
        self.reihenfolge: list[str] = []

    def transaction(self):
        return _Transaktion()

    async def fetchrow(self, sql: str, *args):
        if "from public.users u" in sql:
            self.reihenfolge.append("nachschlagen")
            if self.bekannt is not None and args[0] == self.bekannt:
                return {"id": uuid4(), "display_name": self.bekannt, "org_id": ORG}
            return None
        if "insert into public.users" in sql:
            self.reihenfolge.append("nutzer-anlegen")
            return {"id": uuid4(), "display_name": args[0]}
        raise AssertionError(f"unerwartetes fetchrow: {sql!r}")

    async def fetchval(self, sql: str, *args):
        if "count(*) from public.orgs" in sql:
            self.reihenfolge.append("zaehlen")
            return self.orgs
        if "insert into public.orgs" in sql:
            self.reihenfolge.append("org-anlegen")
            # Ab jetzt ist die Box nicht mehr leer.
            self.orgs += 1
            return ORG
        raise AssertionError(f"unerwartetes fetchval: {sql!r}")

    async def execute(self, sql: str, *args):
        if "pg_advisory_xact_lock" in sql:
            self.reihenfolge.append("sperren")
            self.sperren.append(args[0])
        elif "insert into public.user_org_roles" in sql:
            self.reihenfolge.append("rolle")
            self.protokoll.append(("rolle", args))
        elif "insert into public.audit_log" in sql:
            self.reihenfolge.append("protokoll")
            self.protokoll.append(("audit", args))
        elif "update public.users set last_seen_at" in sql:
            self.reihenfolge.append("gesehen")
        else:  # pragma: no cover — hilft beim Umbauen
            raise AssertionError(f"unerwartetes execute: {sql!r}")


@pytest.fixture(autouse=True)
def abzug_scheitert(monkeypatch):
    """Der Konfigurations-Abzug braucht Pool und Dateisystem — hier keines.

    Er scheitert hier also in **jedem** Test, und jeder Test läuft
    trotzdem durch. Das ist die Zusicherung: der Abzug ist eine
    Bequemlichkeit, keine Bedingung — wer sich anmeldet, kommt auch
    hinein, wenn `/app/data` gerade nicht schreibbar ist.
    """

    @asynccontextmanager
    async def nichts():
        raise RuntimeError("kein Pool im Test")
        yield  # pragma: no cover

    monkeypatch.setattr(auth, "acquire_als_dienst", nichts)


async def _durchlauf(monkeypatch, conn: Verbindung, name: str):
    @asynccontextmanager
    async def leihen():
        yield conn

    monkeypatch.setattr(auth, "acquire", leihen)
    monkeypatch.setattr(auth.settings, "auto_provision", False)
    return await auth._ensure_user_and_org(name)


# ---------------------------------------------------------------------------
# Die Regression, um die es geht
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_erste_identitaet_auf_leerer_box_kommt_hinein(monkeypatch) -> None:
    conn = Verbindung(orgs=0)
    user = await _durchlauf(monkeypatch, conn, "kanzlei")

    assert user.olares_username == "kanzlei"
    assert user.org_id == ORG
    rollen = [a for art, a in conn.protokoll if art == "rolle"]
    assert rollen, "keine Rolle vergeben"


@pytest.mark.asyncio
async def test_der_erste_wird_inhaber_nicht_mitglied(monkeypatch) -> None:
    """`owner` steht im SQL, nicht in den Parametern — deshalb am Quelltext."""
    quelle = inspect.getsource(auth._erstzugang)
    treffer = re.search(
        r"insert into public\.user_org_roles.*?values \(\$1, \$2, '(\w+)'\)",
        quelle,
        re.S,
    )
    assert treffer and treffer.group(1) == "owner"


@pytest.mark.asyncio
async def test_der_zweite_unbekannte_bleibt_draussen(monkeypatch) -> None:
    """Der Kern der Sache — sonst wäre es die alte Selbstbedienung.

    Dieselbe Verbindung wie oben: nach dem ersten Durchlauf steht eine
    Organisation, und ein zweiter fremder Name muss abprallen.
    """
    conn = Verbindung(orgs=0)
    await _durchlauf(monkeypatch, conn, "kanzlei")

    with pytest.raises(HTTPException) as fehler:
        await _durchlauf(monkeypatch, conn, "fremder")
    assert fehler.value.status_code == 401


@pytest.mark.asyncio
async def test_auf_besetzter_box_gar_kein_erstzugang(monkeypatch) -> None:
    conn = Verbindung(orgs=1)

    with pytest.raises(HTTPException) as fehler:
        await _durchlauf(monkeypatch, conn, "fremder")
    assert fehler.value.status_code == 401
    assert "org-anlegen" not in conn.reihenfolge


@pytest.mark.asyncio
async def test_bekannter_nutzer_laeuft_am_erstzugang_vorbei(monkeypatch) -> None:
    conn = Verbindung(orgs=1, bekannt="kanzlei")
    user = await _durchlauf(monkeypatch, conn, "kanzlei")

    assert user.org_id == ORG
    assert conn.reihenfolge == ["nachschlagen", "gesehen"]
    assert not conn.sperren, "für einen bekannten Nutzer wird nicht gesperrt"


# ---------------------------------------------------------------------------
# Gleichzeitigkeit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_erst_sperren_dann_zaehlen(monkeypatch) -> None:
    """Andersherum läsen zwei gleichzeitige erste Aufrufe beide „leer".

    Das Ergebnis wären zwei Organisationen auf einer Box, jede mit einer
    eigenen Inhaberin — und die Aufnahmen der einen unsichtbar für die
    andere.
    """
    conn = Verbindung(orgs=0)
    await _durchlauf(monkeypatch, conn, "kanzlei")

    assert conn.reihenfolge.index("sperren") < conn.reihenfolge.index("zaehlen")
    assert conn.sperren == [auth._SPERRE_ERSTZUGANG]


@pytest.mark.asyncio
async def test_die_sperre_haengt_an_der_transaktion(monkeypatch) -> None:
    """`pg_advisory_lock` ohne `xact` bliebe an der Poolverbindung kleben."""
    quelle = inspect.getsource(auth._erstzugang)
    assert "pg_advisory_xact_lock" in quelle
    assert re.search(r"pg_advisory_lock\b", quelle) is None


# ---------------------------------------------------------------------------
# Nachweis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_der_erstzugang_steht_im_protokoll(monkeypatch) -> None:
    """„Wer wurde wann Inhaber dieser Box" gehört genau dorthin."""
    from app import audit

    conn = Verbindung(orgs=0)
    await _durchlauf(monkeypatch, conn, "kanzlei")

    eintraege = [a for art, a in conn.protokoll if art == "audit"]
    assert len(eintraege) == 1
    assert audit.ERSTEINRICHTUNG in eintraege[0]
    assert "kanzlei" in eintraege[0]


def test_die_oberflaeche_kennt_den_vorgang() -> None:
    """`AKTIONEN` fällt aus den Pfadregeln — dieser Vorgang hat keinen Pfad.

    Ohne `OHNE_PFAD` stünde im Protokoll der technische Name.
    """
    from pathlib import Path
    import json

    from app import audit

    assert audit.ERSTEINRICHTUNG in audit.AKTIONEN

    wurzel = Path(__file__).resolve().parents[2]
    schluessel = audit.ERSTEINRICHTUNG.replace(".", "_")
    for sprache in ("de", "en", "fr", "es", "it"):
        texte = json.loads(
            (wurzel / f"frontend/messages/{sprache}.json").read_text(encoding="utf-8")
        )
        assert schluessel in texte["protokoll"]["aktionen"], (
            f"{sprache}.json kennt {schluessel} nicht"
        )


# ---------------------------------------------------------------------------
# Die Bedingung selbst
# ---------------------------------------------------------------------------


def test_leer_heisst_ueberall_dasselbe() -> None:
    """Eine Regel, zwei Aufrufer.

    `konfiguration.wiederherstellen` und `_erstzugang` müssen sich einig
    sein, wann eine Datenbank leer ist — sonst schriebe der eine eine
    Organisation, während der andere den Abzug darüberlegt.
    """
    from app import konfiguration

    bedingung = "count(*) from public.orgs where deleted_at is null"
    assert bedingung in inspect.getsource(auth._erstzugang)
    assert bedingung in inspect.getsource(konfiguration.wiederherstellen)
