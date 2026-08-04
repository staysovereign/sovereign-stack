from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import aiosqlite


@dataclass(frozen=True)
class MaturityLevel:
    level: int
    name: str
    description: str
    # Whether this level allows the Advisor to make automatic decisions in Tier 3
    can_decide: bool


LEVELS = [
    MaturityLevel(0, "Silent",     "Observing only. No interventions.",                         False),
    MaturityLevel(1, "Suggesting", "Surfacing first patterns. Your decision always.",            False),
    MaturityLevel(2, "Advising",   "Regular recommendations with full data shown.",              False),
    MaturityLevel(3, "Refining",   "Auto-weight adjustment (opt-in only).",                      True),
    MaturityLevel(4, "Sovereign",  "Filter fully personalized. Near-zero false signals.",        True),
]


async def get(db: aiosqlite.Connection) -> MaturityLevel:
    row = await (
        await db.execute(
            "SELECT maturity_level, installed_at, total_signals FROM advisor_state WHERE id = 1"
        )
    ).fetchone()

    if row is None:
        return LEVELS[0]

    computed = _compute_level(row["installed_at"], row["total_signals"])

    # Persist if it changed
    if computed != row["maturity_level"]:
        await db.execute(
            "UPDATE advisor_state SET maturity_level = ? WHERE id = 1",
            (computed,),
        )
        await db.commit()

    return LEVELS[computed]


def _compute_level(installed_at: str, total_signals: int) -> int:
    if not installed_at:
        return 0

    try:
        installed = datetime.fromisoformat(installed_at.replace("Z", "+00:00"))
    except ValueError:
        return 0

    # SQLite's datetime('now') yields a naive UTC string (no offset); treat any
    # naive timestamp as UTC so it can be subtracted from an aware now().
    if installed.tzinfo is None:
        installed = installed.replace(tzinfo=timezone.utc)

    days = (datetime.now(timezone.utc) - installed).days

    if days < 14:
        return 0   # Silent: weeks 1-2
    if days < 28:
        return 1   # Suggesting: weeks 3-4
    if days < 60:
        return 2   # Advising: month 2
    if days < 120:
        return 3   # Refining: month 4+ (opt-in auto-adjust)
    return 4       # Sovereign: month 6+


async def describe(db: aiosqlite.Connection) -> dict:
    """Summary dict for the Interface."""
    level = await get(db)
    row = await (
        await db.execute(
            "SELECT installed_at, total_signals, first_signal_at FROM advisor_state WHERE id = 1"
        )
    ).fetchone()

    return {
        "level": level.level,
        "name": level.name,
        "description": level.description,
        "can_decide": level.can_decide,
        "total_signals": row["total_signals"] if row else 0,
        "installed_at": row["installed_at"] if row else None,
        "first_signal_at": row["first_signal_at"] if row else None,
    }
