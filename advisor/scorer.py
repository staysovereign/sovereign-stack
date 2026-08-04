from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

import aiosqlite

log = logging.getLogger("sovereign.advisor.scorer")

# Minimum resolved signals before the scorer produces non-zero scores
_MIN_SIGNALS = 50

# Weighted components of the confidence score
_W_PLATFORM = 0.25
_W_SENDER   = 0.50
_W_HOUR     = 0.25

# Confidence threshold to recommend a PASS (only used at maturity >= 3)
CONFIDENCE_THRESHOLD = 0.72


async def score(
    platform: str,
    sender_id: str,
    db: aiosqlite.Connection,
) -> float:
    """
    Compute a [0.0, 1.0] urgency confidence score from resolved behavioral signals.
    Returns 0.0 until MIN_SIGNALS resolved outcomes exist.
    Privacy: only hashed sender is used; message content never touches this function.
    """
    total = await _total_resolved(db)
    if total < _MIN_SIGNALS:
        return 0.0

    sender_hash = _hash(platform, sender_id)
    hour = datetime.now(timezone.utc).hour

    platform_score = await _urgency_rate(db, platform=platform)
    sender_score   = await _urgency_rate(db, sender_hash=sender_hash)
    hour_score     = await _urgency_rate(db, hour=hour)

    confidence = (
        _W_PLATFORM * platform_score
        + _W_SENDER  * sender_score
        + _W_HOUR    * hour_score
    )

    log.debug(
        "score platform=%.2f sender=%.2f hour=%.2f → confidence=%.2f",
        platform_score, sender_score, hour_score, confidence,
    )
    return round(confidence, 4)


async def _total_resolved(db: aiosqlite.Connection) -> int:
    row = await (
        await db.execute("SELECT COUNT(*) FROM advisor_signals WHERE outcome IS NOT NULL")
    ).fetchone()
    return row[0]


async def _urgency_rate(
    db: aiosqlite.Connection,
    *,
    platform: str | None = None,
    sender_hash: str | None = None,
    hour: int | None = None,
) -> float:
    """
    Fraction of resolved signals in the given slice that were urgent outcomes
    (correct_pass or false_negative — i.e., the message was genuinely wanted).
    Falls back to 0.5 (neutral) if fewer than 5 signals exist in the slice.
    """
    conditions = ["outcome IS NOT NULL"]
    params: list = []

    if platform:
        conditions.append("platform = ?")
        params.append(platform)
    if sender_hash:
        conditions.append("sender_hash = ?")
        params.append(sender_hash)
    if hour is not None:
        # ±2 hour window for smoother estimates
        conditions.append("ABS(hour_of_day - ?) <= 2")
        params.append(hour)

    where = " AND ".join(conditions)

    total_row = await (
        await db.execute(f"SELECT COUNT(*) FROM advisor_signals WHERE {where}", params)
    ).fetchone()
    total = total_row[0]

    if total < 5:
        return 0.5  # not enough data — neutral

    urgent_row = await (
        await db.execute(
            f"SELECT COUNT(*) FROM advisor_signals WHERE {where} "
            "AND outcome IN ('correct_pass', 'false_negative')",
            params,
        )
    ).fetchone()

    return urgent_row[0] / total


def _hash(platform: str, sender_id: str) -> str:
    return hashlib.sha256(f"{platform}:{sender_id}".encode()).hexdigest()
