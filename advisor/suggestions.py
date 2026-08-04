from __future__ import annotations

import json
import logging

import aiosqlite

from advisor import ollama
from advisor.maturity import MaturityLevel

log = logging.getLogger("sovereign.advisor.suggestions")

# Minimum signals before we attempt to generate suggestions
_MIN_SIGNALS_FOR_SUGGESTIONS = 20


async def generate_if_ready(level: MaturityLevel, db: aiosqlite.Connection) -> None:
    """
    Generate Ollama-based suggestions when the Advisor has enough data.
    Called periodically by the observer loop (daily, roughly).
    Silently skips if Ollama is unavailable or data is insufficient.
    """
    if level.level < 1:
        return  # Silent phase — no suggestions yet

    stats = await _build_stats(db)
    if stats["total_signals"] < _MIN_SIGNALS_FOR_SUGGESTIONS:
        return

    if not await ollama.available():
        log.debug("Ollama not available — skipping suggestion generation")
        return

    suggestions = await ollama.suggest_decrees(stats)
    for s in suggestions:
        body = s.get("body", "")
        stype = s.get("type", "pattern")
        data = {k: v for k, v in s.items() if k not in ("body", "type")}
        await db.execute(
            "INSERT INTO advisor_suggestions (type, body, data_json) VALUES (?, ?, ?)",
            (stype, body, json.dumps(data)),
        )

    if suggestions:
        await db.commit()
        log.info("Generated %d Advisor suggestions", len(suggestions))


async def _build_stats(db: aiosqlite.Connection) -> dict:
    """
    Aggregate anonymized statistics from advisor_signals.
    No names, no content — only counts, rates, and patterns.
    """
    total_row = await (
        await db.execute("SELECT COUNT(*) FROM advisor_signals WHERE outcome IS NOT NULL")
    ).fetchone()
    total = total_row[0]

    fp_row = await (
        await db.execute(
            "SELECT COUNT(*) FROM advisor_signals WHERE outcome = 'false_positive'"
        )
    ).fetchone()
    fn_row = await (
        await db.execute(
            "SELECT COUNT(*) FROM advisor_signals WHERE outcome = 'false_negative'"
        )
    ).fetchone()

    platform_rows = await (
        await db.execute(
            """
            SELECT platform,
                   COUNT(*) AS total,
                   SUM(CASE WHEN outcome IN ('correct_pass','false_negative') THEN 1 ELSE 0 END) AS urgent,
                   SUM(CASE WHEN outcome = 'false_positive' THEN 1 ELSE 0 END) AS fp,
                   SUM(CASE WHEN outcome = 'false_negative' THEN 1 ELSE 0 END) AS fn
            FROM advisor_signals WHERE outcome IS NOT NULL
            GROUP BY platform
            """
        )
    ).fetchall()

    platforms = {}
    for r in platform_rows:
        platforms[r["platform"]] = {
            "total": r["total"],
            "urgency_rate": r["urgent"] / r["total"] if r["total"] else 0,
            "false_positives": r["fp"],
            "false_negatives": r["fn"],
        }

    # Senders (hashed) with >80% urgency rate and at least 5 signals
    high_urgency = await (
        await db.execute(
            """
            SELECT COUNT(DISTINCT sender_hash) FROM (
                SELECT sender_hash,
                       AVG(CASE WHEN outcome IN ('correct_pass','false_negative') THEN 1.0 ELSE 0.0 END) AS rate,
                       COUNT(*) AS cnt
                FROM advisor_signals WHERE outcome IS NOT NULL
                GROUP BY sender_hash
                HAVING cnt >= 5 AND rate > 0.8
            )
            """
        )
    ).fetchone()

    # Council candidates: senders with >90% urgency and >10 signals
    council_candidates = await (
        await db.execute(
            """
            SELECT COUNT(DISTINCT sender_hash) FROM (
                SELECT sender_hash,
                       AVG(CASE WHEN outcome IN ('correct_pass','false_negative') THEN 1.0 ELSE 0.0 END) AS rate,
                       COUNT(*) AS cnt
                FROM advisor_signals WHERE outcome IS NOT NULL
                GROUP BY sender_hash
                HAVING cnt >= 10 AND rate > 0.9
            )
            """
        )
    ).fetchone()

    return {
        "total_signals": total,
        "platforms": platforms,
        "overall_false_positive_rate": fp_row[0] / total if total else 0,
        "overall_false_negative_rate": fn_row[0] / total if total else 0,
        "high_urgency_senders": high_urgency[0],
        "council_candidates": council_candidates[0],
    }
