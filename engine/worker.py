from __future__ import annotations

import asyncio
import logging

from advisor.signals import record_pending
from core.db import get_db
from core.models.message import NormalizedMessage
from core.queue import message_queue
from engine import tier1_council, tier2_decrees, tier3_advisor
from engine.result import Decision, EngineResult, Tier
from engine.vault import record_chronicle, store

log = logging.getLogger("sovereign.engine")


async def run() -> None:
    """
    Main engine loop. Runs as a background task for the lifetime of the process.
    Consumes NormalizedMessages from the ingest queue and routes each one:
      - PASS  → drops onto delivery_queue for Layer 3
      - HOLD  → writes to the Vault
    Chronicle entry and Advisor pending signal written for every message.
    """
    from core.delivery_queue import DeliveryItem, delivery_queue

    log.info("Urgency engine started")

    async with get_db() as db:
        while True:
            message: NormalizedMessage = await message_queue.get()
            try:
                result = await _evaluate(message, db)
                await record_chronicle(message, result, db)
                await record_pending(message, result, db)

                if result.decision == Decision.PASS:
                    log.info(
                        "PASS  [%s] %s — %s",
                        message.platform.value,
                        message.sender.id,
                        result.reason,
                    )
                    await delivery_queue.put(DeliveryItem(message=message, result=result))
                else:
                    log.debug(
                        "HOLD  [%s] %s — %s",
                        message.platform.value,
                        message.sender.id,
                        result.reason,
                    )
                    await store(message, result, db)

            except Exception:
                log.exception("Engine error processing message %s", message.id)
                # Core guardrail: never silently drop a message. If evaluation
                # failed, fail safe to HOLD so it lands in the Vault rather than
                # vanishing.
                try:
                    fallback = EngineResult(
                        decision=Decision.HOLD,
                        tier=Tier.DEFAULT,
                        reason="Held after engine error during evaluation",
                    )
                    await store(message, fallback, db)
                except Exception:
                    log.exception(
                        "Failed to hold message %s after engine error", message.id
                    )
            finally:
                message_queue.task_done()


async def _evaluate(message: NormalizedMessage, db) -> EngineResult:
    result = await tier1_council.evaluate(message, db)
    if result:
        return result

    result = await tier2_decrees.evaluate(message, db)
    if result:
        return result

    result = await tier3_advisor.evaluate(message, db)
    if result:
        return result

    return EngineResult(
        decision=Decision.HOLD,
        tier=Tier.DEFAULT,
        reason="No tier claimed urgency",
    )
