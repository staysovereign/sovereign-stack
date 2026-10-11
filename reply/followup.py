from __future__ import annotations

import aiosqlite

FOLLOWUP_WINDOW_MINUTES = 5


async def get_followup(command: str, db: aiosqlite.Connection) -> tuple[str, str] | None:
    """
    Last (question, answer) for this command, if it's recent enough to count
    as the same conversation rather than an unrelated new question.
    """
    row = await (
        await db.execute(
            "SELECT question, answer FROM ai_followup "
            "WHERE command = ? AND updated_at > datetime('now', ?)",
            (command, f"-{FOLLOWUP_WINDOW_MINUTES} minutes"),
        )
    ).fetchone()
    return (row["question"], row["answer"]) if row else None


async def save_followup(command: str, question: str, answer: str, db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        INSERT INTO ai_followup (command, question, answer, updated_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(command) DO UPDATE SET
            question = excluded.question,
            answer = excluded.answer,
            updated_at = excluded.updated_at
        """,
        (command, question, answer),
    )
    await db.commit()
