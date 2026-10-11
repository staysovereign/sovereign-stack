from __future__ import annotations

import asyncio
import logging

from core.db import get_db
from delivery.gateway import send

log = logging.getLogger("sovereign.reply.reminders")


async def run() -> None:
    """
    Background task: every 30 seconds, send any reminder whose due_at has
    passed (created via the 'world' command's set_reminder tool).
    """
    log.info("Reminders worker started")
    async with get_db() as db:
        while True:
            await asyncio.sleep(30)
            try:
                rows = await (
                    await db.execute(
                        "SELECT id, text FROM reminders WHERE sent = 0 AND due_at <= datetime('now')"
                    )
                ).fetchall()

                for row in rows:
                    result = await send(f"SOVEREIGN reminder: {row['text']}")
                    if result.success:
                        await db.execute("UPDATE reminders SET sent = 1 WHERE id = ?", (row["id"],))
                    else:
                        log.error("Reminder %s send failed: %s", row["id"], result.error)

                if rows:
                    await db.commit()

            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Reminders loop error")
