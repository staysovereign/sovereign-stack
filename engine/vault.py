from __future__ import annotations

import aiosqlite

from core.models.message import ContentType, NormalizedMessage
from engine.result import Decision, EngineResult


async def store(
    message: NormalizedMessage,
    result: EngineResult,
    db: aiosqlite.Connection,
) -> None:
    """
    Every message that is not forwarded to delivery is stored in the Vault.
    Nothing is ever deleted. Nothing is lost.
    """
    needs_transcription = (
        message.content.type == ContentType.VOICE
        and result.decision == Decision.HOLD
    )

    await db.execute(
        """
        INSERT OR IGNORE INTO vault
            (message_id, message_json, hold_reason, needs_transcription)
        VALUES (?, ?, ?, ?)
        """,
        (
            str(message.id),
            message.model_dump_json(),
            result.reason,
            int(needs_transcription),
        ),
    )
    await db.commit()


async def record_chronicle(
    message: NormalizedMessage,
    result: EngineResult,
    db: aiosqlite.Connection,
) -> None:
    """Write one entry to the Chronicle regardless of pass/hold decision."""
    await db.execute(
        """
        INSERT INTO chronicle
            (message_id, platform, sender_id, decision, tier_triggered, decree_id, decree_name)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(message.id),
            message.platform.value,
            message.sender.id,
            result.decision.value,
            result.tier.value,
            result.decree_id,
            result.decree_name,
        ),
    )
    await db.commit()
