from __future__ import annotations

from datetime import datetime, timezone

import aiosqlite

from core.db import sender_timestamps
from core.models.decree import DecreeAction, DecreeCondition
from core.models.message import ContentType, NormalizedMessage
from engine.result import Decision, EngineResult, Tier


async def evaluate(message: NormalizedMessage, db: aiosqlite.Connection) -> EngineResult | None:
    """
    Tier 2: The Decrees.
    Evaluates enabled decrees in priority order (lowest number first).
    First matching decree determines the outcome.
    Returns None to fall through to Tier 3.
    """
    _record_timestamp(message)

    rows = await (
        await db.execute(
            "SELECT id, name, condition, condition_value, action FROM decrees "
            "WHERE enabled = 1 ORDER BY priority ASC"
        )
    ).fetchall()

    for row in rows:
        condition = DecreeCondition(row["condition"])
        action = DecreeAction(row["action"])
        params: dict = __import__("json").loads(row["condition_value"])

        if _matches(message, condition, params):
            decision = Decision.PASS if action == DecreeAction.PASS_THROUGH else Decision.HOLD
            return EngineResult(
                decision=decision,
                tier=Tier.DECREE,
                decree_id=row["id"],
                decree_name=row["name"],
                reason=f"Decree '{row['name']}' matched ({condition.value})",
            )

    return None


def _record_timestamp(message: NormalizedMessage) -> None:
    key = f"{message.platform.value}:{message.sender.id}"
    sender_timestamps[key].append(datetime.now(timezone.utc))


def _matches(message: NormalizedMessage, condition: DecreeCondition, params: dict) -> bool:
    if condition == DecreeCondition.GROUP:
        return message.group is not None

    if condition == DecreeCondition.KEYWORD:
        body = (message.content.body or "").lower()
        keywords: list[str] = params.get("keywords", [])
        if not params.get("case_sensitive", False):
            return any(kw.lower() in body for kw in keywords)
        return any(kw in body for kw in keywords)

    if condition == DecreeCondition.FREQUENCY:
        key = f"{message.platform.value}:{message.sender.id}"
        count: int = params.get("count", 3)
        window: int = params.get("window_seconds", 600)
        now = datetime.now(timezone.utc)
        recent = [
            ts for ts in sender_timestamps[key]
            if (now - ts).total_seconds() <= window
        ]
        return len(recent) >= count

    if condition == DecreeCondition.PLATFORM:
        return message.platform.value == params.get("platform")

    if condition == DecreeCondition.MESSAGE_TYPE:
        return message.content.type.value == params.get("type")

    return False
