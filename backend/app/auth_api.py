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

from fastapi import Depends, Header, HTTPException
from passlib.context import CryptContext

from app.db import acquire

KEY_PREFIX = "inskey_"
KEY_PREFIX_LEN = 14  # "inskey_" (7) + 7 chars = unique enough for an index
BCRYPT = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
    hashed = BCRYPT.hash(full)
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
            if BCRYPT.verify(token, r["key_hash"]):
                match = r
                break
        if match is None:
            raise HTTPException(status_code=401, detail="Invalid API key.")

        # Best-effort last-used update — don't block the request on it.
        await conn.execute(
            "update public.api_keys set last_used_at = now() where id = $1",
            match["id"],
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
            raise HTTPException(status_code=403, detail=f"Missing scope: {scope}")
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
