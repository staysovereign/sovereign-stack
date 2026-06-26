from __future__ import annotations

import logging

import aiosqlite

from advisor import maturity, scorer
from core.models.message import NormalizedMessage
from engine.result import Decision, EngineResult, Tier

log = logging.getLogger("sovereign.engine.tier3")


async def evaluate(message: NormalizedMessage, db: aiosqlite.Connection) -> EngineResult | None:
    """
    Tier 3: The Advisor.
    Uses the statistical behavioral model to produce a confidence score.

    Maturity gates:
      Level 0-2 (Silent/Suggesting/Advising): observes only — returns None always.
      Level 3-4 (Refining/Sovereign): can issue a PASS if confidence >= threshold.

    Never reads message content. Only uses platform + hashed sender_id for scoring.
    """
    level = await maturity.get(db)

    if not level.can_decide:
        log.debug("Advisor level %d (%s) — observing only", level.level, level.name)
        return None

    confidence = await scorer.score(message.platform.value, message.sender.id, db)

    if confidence >= scorer.CONFIDENCE_THRESHOLD:
        log.info(
            "Advisor PASS  [%s] %s — confidence=%.2f (level=%s)",
            message.platform.value,
            message.sender.id,
            confidence,
            level.name,
        )
        return EngineResult(
            decision=Decision.PASS,
            tier=Tier.ADVISOR,
            reason=f"Advisor confidence {confidence:.0%} ≥ threshold (level: {level.name})",
        )

    return None
