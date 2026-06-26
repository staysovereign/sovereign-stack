from __future__ import annotations

import unicodedata

import aiosqlite

from core.models.message import NormalizedMessage


def platform_chat_id_for(message: NormalizedMessage) -> str:
    """
    Extract the platform-specific conversation identifier needed to send a reply.
    - Telegram: chat_id from metadata
    - WhatsApp: room_id from metadata
    - Email: sender's email address
    - SMS: sender's phone number
    """
    meta = message.metadata
    platform = message.platform.value

    if platform == "telegram":
        return str(meta.get("chat_id") or message.sender.id)
    if platform == "whatsapp":
        return str(meta.get("room_id") or message.sender.id)
    if platform == "email":
        return message.sender.email or message.sender.id
    if platform == "sms":
        return message.sender.phone or message.sender.id
    return message.sender.id


async def get_active_session(db: aiosqlite.Connection) -> aiosqlite.Row | None:
    """Most recent session within its 15-minute window, not yet used."""
    return await (
        await db.execute(
            """
            SELECT * FROM reply_sessions
            WHERE used = 0 AND datetime('now') < expires_at
            ORDER BY created_at DESC LIMIT 1
            """
        )
    ).fetchone()


async def get_session_by_name(name: str, db: aiosqlite.Connection) -> aiosqlite.Row | None:
    """
    Most recent delivery (active or expired) from a sender whose name fuzzy-matches.
    Strips accents so 'mama' matches 'Mamá'.
    """
    rows = await (
        await db.execute(
            "SELECT * FROM reply_sessions ORDER BY created_at DESC LIMIT 50"
        )
    ).fetchall()

    needle = _normalize(name)
    for row in rows:
        if row["sender_name"] and needle in _normalize(row["sender_name"]):
            return row
    return None


async def get_session_by_index(index: int, db: aiosqlite.Connection) -> aiosqlite.Row | None:
    """
    Nth most recent delivery (1-based, matches the list command output).
    Looks at the vault for held messages, not just sessions.
    """
    row = await (
        await db.execute(
            "SELECT * FROM reply_sessions ORDER BY created_at DESC LIMIT 1 OFFSET ?",
            (index - 1,),
        )
    ).fetchone()
    return row


async def mark_used(session_id: int, db: aiosqlite.Connection) -> None:
    await db.execute("UPDATE reply_sessions SET used = 1 WHERE id = ?", (session_id,))
    await db.commit()


def _normalize(s: str) -> str:
    """Lowercase + strip accents for fuzzy matching."""
    nfkd = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))
