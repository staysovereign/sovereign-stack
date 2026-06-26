from __future__ import annotations

import aiosqlite

from core.models.message import NormalizedMessage
from engine.result import Decision, EngineResult, Tier


async def evaluate(message: NormalizedMessage, db: aiosqlite.Connection) -> EngineResult | None:
    """
    Tier 1: The Council.
    If the sender is on the Council for their platform, the message passes immediately.
    Returns an EngineResult if a decision is reached, None to fall through to Tier 2.
    """
    row = await (
        await db.execute(
            "SELECT id, name FROM council WHERE platform = ? AND sender_id = ?",
            (message.platform.value, message.sender.id),
        )
    ).fetchone()

    if row is None:
        return None

    return EngineResult(
        decision=Decision.PASS,
        tier=Tier.COUNCIL,
        reason=f"Sender '{row['name']}' is on The Council",
    )
