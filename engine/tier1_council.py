from __future__ import annotations

import aiosqlite

from core.models.message import NormalizedMessage
from engine.result import Decision, EngineResult, Tier


async def evaluate(message: NormalizedMessage, db: aiosqlite.Connection) -> EngineResult | None:
    """
    Tier 1: The Council.
    If the sender is on the Council for their platform AND not muted, the message
    passes immediately. A muted member stays on the list but is skipped here, so
    their messages fall through to Tier 2 (the Decrees) like any normal sender —
    a temporary, reversible way to switch someone off without deleting them.

    Members are matched by their platform sender id OR, when available, their phone
    number. The phone match is essential for WhatsApp: there the sender id is a
    Matrix MXID (e.g. @whatsapp_573...:server), but users add Council members by
    phone number — the connector still populates sender.phone, so we match on that.
    Returns an EngineResult if a decision is reached, None to fall through to Tier 2.
    """
    candidates = [message.sender.id]
    if message.sender.phone:
        candidates.append(message.sender.phone)
    placeholders = ", ".join("?" for _ in candidates)

    row = await (
        await db.execute(
            f"SELECT id, name FROM council WHERE platform = ? AND muted = 0 AND sender_id IN ({placeholders})",
            (message.platform.value, *candidates),
        )
    ).fetchone()

    if row is None:
        return None

    return EngineResult(
        decision=Decision.PASS,
        tier=Tier.COUNCIL,
        reason=f"Sender '{row['name']}' is on The Council",
    )
