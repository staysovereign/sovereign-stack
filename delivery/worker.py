from __future__ import annotations

import asyncio
import logging

import aiosqlite

from core.db import get_db
from core.delivery_queue import DeliveryItem, delivery_queue
from delivery.formatter import format_sms
from delivery.gateway import send
from delivery.quiet_hours import record_urgent_delivery, should_deliver

log = logging.getLogger("sovereign.delivery")


async def run() -> None:
    """
    Delivery worker. Runs as a background task for the lifetime of the process.
    Consumes DeliveryItems from the engine and either sends an SMS or holds at delivery.
    Also periodically drains messages held during quiet hours once quiet hours end.
    """
    log.info("Delivery worker started")
    async with await get_db() as db:
        drain_task = asyncio.create_task(_drain_loop(db), name="delivery_drain")
        try:
            while True:
                item: DeliveryItem = await delivery_queue.get()
                try:
                    await _process(item, db)
                except Exception:
                    log.exception("Delivery error for message %s", item.message.id)
                finally:
                    delivery_queue.task_done()
        finally:
            drain_task.cancel()


async def _process(item: DeliveryItem, db: aiosqlite.Connection) -> None:
    message = item.message
    result = item.result

    # Look up Council name for this sender (may be None)
    council_row = await (
        await db.execute(
            "SELECT name FROM council WHERE platform = ? AND sender_id = ?",
            (message.platform.value, message.sender.id),
        )
    ).fetchone()
    council_name = council_row["name"] if council_row else None

    if not await should_deliver(message, db):
        log.debug("HELD@delivery (quiet hours) — [%s] %s", message.platform.value, message.sender.id)
        await _hold_at_delivery(item, db)
        return

    sms_body = format_sms(message, result, council_name)
    send_result = await send(sms_body)
    record_urgent_delivery()

    await db.execute(
        "INSERT INTO delivery_log (message_id, sms_to, sms_body, gateway, success, error) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            str(message.id),
            "dumb_phone",  # never log the actual number in plaintext
            sms_body,
            send_result.gateway,
            int(send_result.success),
            send_result.error,
        ),
    )
    await db.commit()

    if send_result.success:
        log.info("SMS sent  [%s] %s", message.platform.value, message.sender.id)
        await _create_reply_session(message, sms_body, council_name, db)
    else:
        log.error("SMS FAILED [%s] %s: %s", message.platform.value, message.sender.id, send_result.error)


async def _create_reply_session(
    message, sms_body: str, council_name: str | None, db: aiosqlite.Connection
) -> None:
    from reply.session import platform_chat_id_for
    chat_id = platform_chat_id_for(message)
    await db.execute(
        """
        INSERT INTO reply_sessions
            (message_id, platform, sender_id, sender_name, platform_chat_id, sms_body, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now', '+15 minutes'))
        """,
        (
            str(message.id),
            message.platform.value,
            message.sender.id,
            council_name or message.sender.name,
            chat_id,
            sms_body,
        ),
    )
    await db.commit()


async def _hold_at_delivery(item: DeliveryItem, db: aiosqlite.Connection) -> None:
    import json
    await db.execute(
        "INSERT OR IGNORE INTO delivery_held (message_id, message_json, result_json) VALUES (?, ?, ?)",
        (
            str(item.message.id),
            item.message.model_dump_json(),
            json.dumps({
                "decision": item.result.decision.value,
                "tier": item.result.tier.value,
                "decree_id": item.result.decree_id,
                "decree_name": item.result.decree_name,
                "reason": item.result.reason,
            }),
        ),
    )
    await db.commit()


async def _drain_loop(db: aiosqlite.Connection) -> None:
    """
    Every 60 seconds: check if quiet hours have ended and release any held messages.
    """
    from core.models.message import NormalizedMessage
    from engine.result import Decision, EngineResult, Tier
    import json

    while True:
        await asyncio.sleep(60)
        try:
            rows = await (
                await db.execute(
                    "SELECT id, message_id, message_json, result_json "
                    "FROM delivery_held WHERE released = 0"
                )
            ).fetchall()

            if not rows:
                continue

            # Re-check quiet hours with a dummy message (just need the time check)
            from core.models.message import NormalizedMessage
            first_msg = NormalizedMessage.model_validate_json(rows[0]["message_json"])
            if not await should_deliver(first_msg, db):
                continue  # still in quiet hours

            for row in rows:
                msg = NormalizedMessage.model_validate_json(row["message_json"])
                raw = json.loads(row["result_json"])
                result = EngineResult(
                    decision=Decision(raw["decision"]),
                    tier=Tier(raw["tier"]),
                    decree_id=raw.get("decree_id"),
                    decree_name=raw.get("decree_name"),
                    reason=raw.get("reason", ""),
                )
                item = DeliveryItem(message=msg, result=result)
                await _process(item, db)

                await db.execute(
                    "UPDATE delivery_held SET released = 1, released_at = datetime('now') WHERE id = ?",
                    (row["id"],),
                )
            await db.commit()

        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Drain loop error")
