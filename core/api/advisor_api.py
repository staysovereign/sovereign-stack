from __future__ import annotations

from fastapi import APIRouter, status

from advisor import maturity
from core.db import get_db

router = APIRouter(prefix="/api/advisor", tags=["advisor"])


@router.get("")
async def get_advisor():
    async with await get_db() as db:
        state = await maturity.describe(db)

        pending_count = (await (await db.execute(
            "SELECT COUNT(*) FROM advisor_pending"
        )).fetchone())[0]

        suggestion = await (await db.execute(
            "SELECT id, type, body, data_json, generated_at FROM advisor_suggestions "
            "WHERE dismissed = 0 ORDER BY generated_at DESC LIMIT 1"
        )).fetchone()

        accuracy = await (await db.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN outcome IN ('correct_pass','correct_hold') THEN 1 ELSE 0 END) AS correct,
                SUM(CASE WHEN outcome = 'false_positive' THEN 1 ELSE 0 END) AS false_positives,
                SUM(CASE WHEN outcome = 'false_negative' THEN 1 ELSE 0 END) AS false_negatives
            FROM advisor_signals WHERE outcome IS NOT NULL
            """
        )).fetchone()

    return {
        "maturity": state,
        "pending_observations": pending_count,
        "accuracy": {
            "total": accuracy["total"],
            "correct": accuracy["correct"],
            "false_positives": accuracy["false_positives"],
            "false_negatives": accuracy["false_negatives"],
            "rate": round(accuracy["correct"] / accuracy["total"], 3) if accuracy["total"] else None,
        },
        "suggestion": dict(suggestion) if suggestion else None,
    }


@router.post("/suggestions/{suggestion_id}/dismiss", status_code=status.HTTP_200_OK)
async def dismiss_suggestion(suggestion_id: int):
    async with await get_db() as db:
        await db.execute(
            "UPDATE advisor_suggestions SET dismissed = 1 WHERE id = ?", (suggestion_id,)
        )
        await db.commit()
    return {"status": "dismissed"}


@router.post("/reset", status_code=status.HTTP_200_OK)
async def reset_advisor():
    """Reset the Advisor to zero. No questions asked. You own the model."""
    async with await get_db() as db:
        await db.execute("DELETE FROM advisor_signals")
        await db.execute("DELETE FROM advisor_pending")
        await db.execute("DELETE FROM advisor_suggestions")
        await db.execute(
            "UPDATE advisor_state SET total_signals = 0, first_signal_at = NULL, maturity_level = 0 WHERE id = 1"
        )
        await db.commit()
    return {"status": "reset"}
