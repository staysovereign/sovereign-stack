from __future__ import annotations

from collections import deque
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import aiosqlite

from core.db import get_setting
from core.models.message import NormalizedMessage

# In-memory tracker for the threshold override (5+ urgent in 30 min)
_urgent_timestamps: deque[datetime] = deque(maxlen=200)


def record_urgent_delivery() -> None:
    _urgent_timestamps.append(datetime.now(timezone.utc))


async def should_deliver(
    message: NormalizedMessage, db: aiosqlite.Connection
) -> bool:
    """
    Returns True if the message should be delivered now.
    Returns False if it should be held at delivery (quiet hours, no override).

    Decision tree:
      1. Quiet hours disabled → always deliver
      2. Not currently in quiet hours → deliver
      3. Sender is Council member with quiet_hours_override → deliver
      4. Threshold override: 5+ urgent in 30 min → deliver
      5. Otherwise → hold at delivery
    """
    enabled = (await get_setting(db, "quiet_hours_enabled")) == "true"
    if not enabled:
        return True

    if not await _in_quiet_hours(db):
        return True

    if await _has_council_override(message, db):
        return True

    if await _threshold_override(db):
        return True

    return False


async def _in_quiet_hours(db: aiosqlite.Connection) -> bool:
    start_str = await get_setting(db, "quiet_hours_start") or "22:00"
    end_str = await get_setting(db, "quiet_hours_end") or "07:00"
    tz_str = await get_setting(db, "quiet_hours_tz") or "UTC"

    try:
        tz = ZoneInfo(tz_str)
    except ZoneInfoNotFoundError:
        tz = timezone.utc

    now = datetime.now(tz).time().replace(second=0, microsecond=0)
    start = _parse_time(start_str)
    end = _parse_time(end_str)

    if start <= end:
        # Same-day window: 09:00 – 18:00
        return start <= now < end
    else:
        # Overnight window: 22:00 – 07:00
        return now >= start or now < end


async def _has_council_override(
    message: NormalizedMessage, db: aiosqlite.Connection
) -> bool:
    row = await (
        await db.execute(
            "SELECT quiet_hours_override FROM council WHERE platform = ? AND sender_id = ?",
            (message.platform.value, message.sender.id),
        )
    ).fetchone()
    return bool(row and row["quiet_hours_override"])


async def _threshold_override(db: aiosqlite.Connection) -> bool:
    count_str = await get_setting(db, "quiet_hours_threshold_count") or "5"
    window_str = await get_setting(db, "quiet_hours_threshold_window_seconds") or "1800"
    count = int(count_str)
    window = int(window_str)

    now = datetime.now(timezone.utc)
    recent = [ts for ts in _urgent_timestamps if (now - ts).total_seconds() <= window]
    return len(recent) >= count


def _parse_time(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))
