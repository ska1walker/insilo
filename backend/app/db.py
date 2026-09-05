"""Verbindungspool und der Nutzerkontext, den die Zeilensicherheit liest."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

import asyncpg

from app.config import settings

_pool: asyncpg.Pool | None = None


async def init_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            min_size=2,
            max_size=10,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialised. Call init_pool() during startup.")
    return _pool


@asynccontextmanager
async def acquire():
    """Verbindung ohne Nutzerkontext — für Anmeldung und Wartung.

    Nur für die Tabellen, die von der erzwungenen Zeilensicherheit
    ausgenommen sind (`users`, `orgs`, `user_org_roles`) und für Vorgänge
    ohne Nutzer. Alles, was Fachdaten liest oder schreibt, gehört in
    `acquire_as`.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn


@asynccontextmanager
async def acquire_as(user_id: UUID) -> AsyncIterator[asyncpg.Connection]:
    """Verbindung mit gesetztem Nutzerkontext, in einer Transaktion.

    Die Regeln aus `0002_rls_policies.sql` lesen `app.current_user_id`.
    Gesetzt hat den Wert bis v0.1.81 **niemand** — die Zeilensicherheit
    war damit geschrieben, aber wirkungslos; getrennt wurden die Mandanten
    allein durch `where org_id = $1` in jeder einzelnen Abfrage.

    `SET LOCAL` gilt nur innerhalb einer Transaktion — deshalb die
    Transaktion, und nicht aus Bequemlichkeit. Ohne sie fiele der Wert
    nach der ersten Anweisung zurück und die Regeln blendeten alles aus.

    Der Pool gibt Verbindungen weiter; ein `set` ohne `local` bliebe an
    der Verbindung kleben und der nächste Aufruf liefe unter fremder
    Kennung. Genau das verhindert diese Funktion.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "select set_config('app.current_user_id', $1, true)", str(user_id)
            )
            yield conn


@asynccontextmanager
async def acquire_als_schluessel(org_id: UUID) -> AsyncIterator[asyncpg.Connection]:
    """Verbindung für die externe Schnittstelle — lesend, eine Organisation.

    Der Aufrufer weist sich mit einem Zugriffsschlüssel aus, nicht mit
    einer Olares-Identität; es gibt also keinen Nutzer, dessen Kontext
    sich setzen ließe. Unter erzwungener Zeilensicherheit käme dieser Weg
    ohne eigenen Kontext nicht an eine einzige Zeile.

    Deshalb `app.api_key_org`. Die Regeln aus Migration 0017 geben
    darauf **nur Leserechte** und nur für diese eine Organisation frei —
    schreiben lässt sich darüber nichts, und die Schnittstelle tut das
    auch nicht.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "select set_config('app.api_key_org', $1, true)", str(org_id)
            )
            yield conn


@asynccontextmanager
async def acquire_als_dienst() -> AsyncIterator[asyncpg.Connection]:
    """Wie `dienst_kontext`, aber aus dem Pool und auf eine Transaktion begrenzt.

    Für Systemvorgänge im Webdienst — den Konfigurations-Abzug etwa, der
    quer über alle Einrichtungstabellen liest und schreibt, ohne dass ein
    Nutzer ihn angestoßen hätte.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("select set_config('app.dienst', '1', true)")
            yield conn


async def dienst_kontext(conn: asyncpg.Connection) -> None:
    """Kennzeichnet eine Verbindung als Hintergrunddienst.

    Die Celery-Aufgaben arbeiten ohne angemeldeten Nutzer: Transkription,
    Zusammenfassung, Einbettung, Webhook-Versand und der Aufräumlauf
    laufen für sich. Unter erzwungener Zeilensicherheit sähen sie ohne
    Kontext nichts und könnten nichts schreiben.

    Sie bekommen deshalb `app.dienst`, das die Regeln in Migration 0017
    freigibt. Das ist eine ausdrückliche, benannte Ausnahme statt einer
    stillen: gesetzt wird sie **nur** hier und nur von Prozessen, die
    ohnehin mit den Zugangsdaten der Datenbank laufen — aus einer
    Anfrage heraus ist sie nicht erreichbar.

    `is_local = false`, weil die Aufgaben eine eigene Verbindung
    aufmachen und sie am Ende schließen: der Wert soll für die Dauer
    dieser Verbindung gelten, nicht nur für eine Transaktion.
    """
    await conn.execute("select set_config('app.dienst', '1', false)")
