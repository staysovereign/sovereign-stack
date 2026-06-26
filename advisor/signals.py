from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import aiosqlite

from core.models.message import NormalizedMessage
from engine.result import Decision, EngineResult

# Reply window for PASS decisions: if you reply within this many seconds → correct pass
PASS_WINDOW_SECONDS = 600   # 10 minutes

# Vault retrieval window for HOLD decisions: retrieved within this → false negative
HOLD_WINDOW_SECONDS = 3600  # 1 hour


def _hash_sender(platform: str, sender_id: str) -> str:
    """SHA-256 of 'platform:sender_id' — the only identifier the Advisor stores."""
    raw = f"{platform}:{sender_id}".encode()
    return hashlib.sha256(raw).hexdigest()


async def record_pending(
    message: NormalizedMessage,
    result: EngineResult,
    db: aiosqlite.Connection,
) -> None:
    """
    After every engine decision, record a pending observation.
    The observer task will resolve it once the measurement window closes.
    """
    sender_hash = _hash_sender(message.platform.value, message.sender.id)
    hour = datetime.now(timezone.utc).hour
    window = PASS_WINDOW_SECONDS if result.decision == Decision.PASS else HOLD_WINDOW_SECONDS

    await db.execute(
        """
        INSERT OR IGNORE INTO advisor_pending
            (message_id, sender_hash, platform, decision, tier_triggered, hour_of_day, observation_window_secs)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(message.id),
            sender_hash,
            message.platform.value,
            result.decision.value,
            result.tier.value if result.tier else None,
            hour,
            window,
        ),
    )

    # Ensure the state row exists and bump signal counter
    await db.execute(
        "UPDATE advisor_state SET total_signals = total_signals + 1, "
        "first_signal_at = COALESCE(first_signal_at, datetime('now')) WHERE id = 1"
    )
    await db.commit()
