from __future__ import annotations

from fastapi import APIRouter, Query

from core.db import get_db

router = APIRouter(prefix="/api/chronicle", tags=["chronicle"])


@router.get("")
async def get_chronicle(days: int = Query(30, ge=1, le=365)):
    async with await get_db() as db:
        totals = await (await db.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN decision = 'pass' THEN 1 ELSE 0 END) AS passed,
                SUM(CASE WHEN decision = 'hold' THEN 1 ELSE 0 END) AS held,
                SUM(CASE WHEN tier_triggered = 'council' THEN 1 ELSE 0 END) AS by_council,
                SUM(CASE WHEN tier_triggered = 'decrees' THEN 1 ELSE 0 END) AS by_decrees,
                SUM(CASE WHEN tier_triggered = 'advisor' THEN 1 ELSE 0 END) AS by_advisor
            FROM chronicle
            WHERE evaluated_at >= datetime('now', ? || ' days')
            """,
            (f"-{days}",),
        )).fetchone()

        by_platform = await (await db.execute(
            """
            SELECT platform,
                COUNT(*) AS total,
                SUM(CASE WHEN decision = 'pass' THEN 1 ELSE 0 END) AS passed
            FROM chronicle
            WHERE evaluated_at >= datetime('now', ? || ' days')
            GROUP BY platform ORDER BY total DESC
            """,
            (f"-{days}",),
        )).fetchall()

        recent = await (await db.execute(
            """
            SELECT id, platform, sender_id, sender_name, decision, tier_triggered,
                   reason, evaluated_at
            FROM chronicle
            ORDER BY evaluated_at DESC LIMIT 50
            """
        )).fetchall()

    return {
        "period_days": days,
        "totals": dict(totals),
        "by_platform": [dict(r) for r in by_platform],
        "recent": [dict(r) for r in recent],
    }
