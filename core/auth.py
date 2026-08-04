"""Dashboard authentication: a single password (set via the UI), stored hashed.

- Password is hashed with PBKDF2-HMAC-SHA256 (stdlib, no extra deps).
- Sessions are opaque bearer tokens held in memory; they're cleared on restart
  (so a core restart means re-login) and on password change.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

import aiosqlite

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"{_ALGO}${_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        if algo != _ALGO:
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


# ── In-memory session tokens ────────────────────────────────────────────────
_TOKENS: set[str] = set()


def issue_token() -> str:
    token = secrets.token_urlsafe(32)
    _TOKENS.add(token)
    return token


def check_token(token: str | None) -> bool:
    return bool(token) and token in _TOKENS


def revoke_token(token: str | None) -> None:
    _TOKENS.discard(token)


def revoke_all() -> None:
    _TOKENS.clear()


def bearer_from_header(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


# ── Password hash storage (single-row `auth` table) ──────────────────────────
async def get_password_hash(db: aiosqlite.Connection) -> str | None:
    row = await (await db.execute("SELECT password_hash FROM auth WHERE id = 1")).fetchone()
    return row["password_hash"] if row else None


async def set_password_hash(db: aiosqlite.Connection, password_hash: str) -> None:
    await db.execute(
        "INSERT INTO auth (id, password_hash, updated_at) VALUES (1, ?, datetime('now')) "
        "ON CONFLICT(id) DO UPDATE SET password_hash = excluded.password_hash, "
        "updated_at = excluded.updated_at",
        (password_hash,),
    )
    await db.commit()
