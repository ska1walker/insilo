"""API-Key authentication for the external `/api/external/v1/*` endpoints.

Tokens look like `inskey_<24-byte-base32>`. We store:
- `key_prefix`  → the first 14 chars, indexed, used to narrow the lookup
- `key_hash`    → bcrypt(full_token), the only thing we can verify against

The raw token is returned exactly once at creation; after that we can
neither display nor reconstruct it. A check is roughly: prefix-lookup
(B-tree index) + one bcrypt verify ≈ a couple of ms.
"""

from __future__ import annotations

import secrets
from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

import bcrypt
from fastapi import Depends, Header, HTTPException, Request

from app import audit
from app.db import acquire
from app.errors import http_error

KEY_PREFIX = "inskey_"
KEY_PREFIX_LEN = 14  # "inskey_" (7) + 7 chars = unique enough for an index


# ---------------------------------------------------------------------------
# Hashing — bcrypt direkt, ohne passlib
#
# `passlib[bcrypt]` stand ohne Obergrenze in pyproject.toml, und passlib
# 1.7.4 (letzte Veröffentlichung 2020) ist mit bcrypt ab 4.1 unverträglich:
# beim Erkennen des Backends übergibt es einen überlangen Wert, den neuere
# bcrypt-Fassungen mit `ValueError` ablehnen statt ihn zu kürzen.
#
# Auf der Box am 5.9.2026 nachgemessen — bcrypt 5.0.0, und damit war die
# **gesamte externe Schnittstelle tot**: kein Zugriffsschlüssel ließ sich
# anlegen und keiner prüfen. Eine Obergrenze auf `bcrypt<4.1` hätte das
# behoben und dafür eine Bibliothek ohne Sicherheitsaktualisierungen
# eingefroren; passlib selbst bewegt sich seit fünf Jahren nicht.
#
# `bcrypt.checkpw` prüft die vorhandenen Hashes weiter — passlib hat
# nichts Eigenes geschrieben, sondern dasselbe Format.
# ---------------------------------------------------------------------------

# bcrypt schneidet nach 72 Byte ab bzw. lehnt ab. Unsere Schlüssel sind
# rund 39 Zeichen; die Grenze steht hier, damit eine künftige Änderung am
# Format nicht still die Hälfte des Geheimnisses verschenkt.
MAX_TOKEN_BYTES = 72


def _hashen(token: str) -> str:
    roh = token.encode("utf-8")
    if len(roh) > MAX_TOKEN_BYTES:
        raise ValueError(
            f"token is {len(roh)} bytes; bcrypt takes at most {MAX_TOKEN_BYTES}"
        )
    return bcrypt.hashpw(roh, bcrypt.gensalt()).decode("ascii")


def _pruefen(token: str, hashed: str) -> bool:
    """Vergleicht in konstanter Zeit; ein unbrauchbarer Hash ist kein Treffer.

    `checkpw` wirft bei einem Hash, den es nicht lesen kann, und bei einem
    zu langen Wert. Beides ist hier keine Störung, sondern schlicht „passt
    nicht" — eine Ausnahme würde den Aufruf mit 500 beenden und damit
    verraten, dass der Schlüssel dem Präfix nach existiert.
    """
    try:
        return bcrypt.checkpw(token.encode("utf-8"), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


@dataclass(frozen=True)
class ApiCaller:
    """The identity of an external caller authenticated via API-Key."""

    api_key_id: UUID
    org_id: UUID
    scopes: tuple[str, ...]
    name: str


def generate_api_key() -> tuple[str, str, str]:
    """Mint a new raw token. Returns (full_token, key_prefix, bcrypt_hash).

    The full token must be shown to the caller once and then discarded.
    """
    body = secrets.token_urlsafe(24).replace("-", "x").replace("_", "y")
    full = f"{KEY_PREFIX}{body}"
    prefix = full[:KEY_PREFIX_LEN]
    hashed = _hashen(full)
    return full, prefix, hashed


def _parse_bearer(header: str | None) -> str | None:
    if not header:
        return None
    parts = header.strip().split(None, 1)
    if len(parts) != 2:
        return None
    scheme, token = parts
    if scheme.lower() != "bearer":
        return None
    token = token.strip()
    if not token.startswith(KEY_PREFIX):
        return None
    return token


async def get_api_caller(
    request: Request,
    authorization: str | None = Header(None),
) -> ApiCaller:
    token = _parse_bearer(authorization)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing or malformed Authorization header (expected `Bearer inskey_…`).",
        )
    prefix = token[:KEY_PREFIX_LEN]

    async with acquire() as conn:
        rows = await conn.fetch(
            """
            select id, org_id, key_hash, scopes, name
            from public.api_keys
            where key_prefix = $1 and revoked_at is null
            """,
            prefix,
        )
        match = None
        for r in rows:
            if _pruefen(token, r["key_hash"]):
                match = r
                break
        if match is None:
            raise http_error(401, "auth.invalid_key")

        # Best-effort last-used update — don't block the request on it.
        await conn.execute(
            "update public.api_keys set last_used_at = now() where id = $1",
            match["id"],
        )

    # Fürs Protokoll: auf diesem Weg verlassen Daten die Box, hier hat der
    # Urheber keinen Namen aus X-Bfl-User, sondern einen Schlüssel.
    audit.merke_akteur(
        request.scope,
        org_id=match["org_id"],
        api_key_id=match["id"],
    )

    return ApiCaller(
        api_key_id=match["id"],
        org_id=match["org_id"],
        scopes=tuple(match["scopes"] or ()),
        name=match["name"],
    )


def require_scope(scope: str):
    """Dependency factory: enforce that the caller carries the given scope."""

    async def _checker(caller: ApiCaller = Depends(get_api_caller)) -> ApiCaller:
        if scope not in caller.scopes:
            raise http_error(403, "auth.missing_scope", scope=scope)
        return caller

    return _checker


def normalize_scopes(scopes: Iterable[str] | None) -> list[str]:
    """Cleanse user-supplied scope inputs against the allow-list."""
    allowed = {"read:meetings"}
    if not scopes:
        return ["read:meetings"]
    out = [s for s in scopes if s in allowed]
    return out or ["read:meetings"]


__all__ = [
    "ApiCaller",
    "KEY_PREFIX",
    "KEY_PREFIX_LEN",
    "generate_api_key",
    "get_api_caller",
    "require_scope",
    "normalize_scopes",
]
