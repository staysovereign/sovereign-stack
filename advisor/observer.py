from __future__ import annotations

import asyncio
import logging

import aiosqlite

from core.db import get_db

log = logging.getLogger("sovereign.advisor.observer")

_POLL_INTERVAL = 60           # seconds — resolution cycle
_SUGGESTION_INTERVAL = 86400  # seconds — daily suggestion generation


async def run() -> None:
    """
    Background task: every minute, resolve pending observations.
    Once per day, triggers Ollama-based suggestion generation.

    PASS observation (10-min window):
      - reply_sessions.used = 1 within window  → correct_pass
      - no reply within window                 → false_positive

    HOLD observation (1-hour window):
      - vault.retrieved = 1 within window      → false_negative
      - not retrieved within window            → correct_hold
    """
    log.info("Advisor observer started")
    cycles_since_suggestions = 0
    suggestion_every_n = _SUGGESTION_INTERVAL // _POLL_INTERVAL

    async with get_db() as db:
        while True:
            await asyncio.sleep(_POLL_INTERVAL)
            try:
                await _resolve_expired(db)
                cycles_since_suggestions += 1
                if cycles_since_suggestions >= suggestion_every_n:
                    cycles_since_suggestions = 0
                    from advisor import maturity, suggestions
                    level = await maturity.get(db)
                    await suggestions.generate_if_ready(level, db)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Observer error during resolution cycle")


async def _resolve_expired(db: aiosqlite.Connection) -> None:
    rows = await (
        await db.execute(
            """
            SELECT id, message_id, sender_hash, platform, decision, tier_triggered,
                   hour_of_day, decided_at, observation_window_secs
            FROM advisor_pending
            WHERE datetime(decided_at, '+' || observation_window_secs || ' seconds') < datetime('now')
            """
        )
    ).fetchall()

    for row in rows:
        outcome = await _determine_outcome(row, db)
        if outcome is None:
            continue  # window not elapsed yet (shouldn't happen given the WHERE, but guard)

        response_time = await _measure_response_time(row, db)

        await db.execute(
            """
            INSERT INTO advisor_signals
                (sender_hash, platform, sovereign_decision, tier_triggered,
                 response_time_seconds, outcome, hour_of_day)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["sender_hash"],
                row["platform"],
                row["decision"],
                row["tier_triggered"],
                response_time,
                outcome,
                row["hour_of_day"],
            ),
        )
        await db.execute("DELETE FROM advisor_pending WHERE id = ?", (row["id"],))

    if rows:
        await db.commit()
        log.debug("Resolved %d pending advisor observations", len(rows))


async def _determine_outcome(row: aiosqlite.Row, db: aiosqlite.Connection) -> str | None:
    message_id = row["message_id"]
    decision = row["decision"]
    window = row["observation_window_secs"]

    if decision == "pass":
        # decided_at belongs to advisor_pending (this row), not reply_sessions —
        # bind it as a parameter. A reply counts if it happened within the window
        # after the decision: created_at < decided_at + window.
        replied = await (
            await db.execute(
                """
                SELECT 1 FROM reply_sessions
                WHERE message_id = ? AND used = 1
                  AND datetime(created_at) < datetime(?, '+' || ? || ' seconds')
                """,
                (message_id, row["decided_at"], window),
            )
        ).fetchone()
        return "correct_pass" if replied else "false_positive"

    if decision == "hold":
        retrieved = await (
            await db.execute(
                """
                SELECT 1 FROM vault
                WHERE message_id = ? AND retrieved = 1
                  AND datetime(retrieved_at) < datetime(?, '+' || ? || ' seconds')
                """,
                (message_id, row["decided_at"], window),
            )
        ).fetchone()
        return "false_negative" if retrieved else "correct_hold"

    return None


async def _measure_response_time(row: aiosqlite.Row, db: aiosqlite.Connection) -> int | None:
    """Seconds between Sovereign's decision and the user's first action."""
    if row["decision"] == "pass":
        r = await (
            await db.execute(
                "SELECT created_at FROM reply_sessions WHERE message_id = ? AND used = 1",
                (row["message_id"],),
            )
        ).fetchone()
        if r:
            decided = _parse_dt(row["decided_at"])
            replied = _parse_dt(r["created_at"])
            return max(0, int((replied - decided).total_seconds()))
    else:
        r = await (
            await db.execute(
                "SELECT retrieved_at FROM vault WHERE message_id = ? AND retrieved = 1",
                (row["message_id"],),
            )
        ).fetchone()
        if r and r["retrieved_at"]:
            decided = _parse_dt(row["decided_at"])
            retrieved = _parse_dt(r["retrieved_at"])
            return max(0, int((retrieved - decided).total_seconds()))
    return None


def _parse_dt(s: str):
    from datetime import datetime
    return datetime.fromisoformat(s.replace("Z", "+00:00"))
