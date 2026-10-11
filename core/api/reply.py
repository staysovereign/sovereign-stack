from __future__ import annotations

import logging
import os

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel

from delivery.gateway import send

router = APIRouter(prefix="/reply", tags=["reply"])
log = logging.getLogger("sovereign.api.reply")

DUMB_PHONE = os.environ.get("DUMB_PHONE_NUMBER", "")


class InboundSMS(BaseModel):
    from_number: str
    body: str


async def _process_and_reply(body: str) -> None:
    from reply.router import handle

    try:
        confirmation = await handle(body)
        if confirmation:
            await send(confirmation)
    except Exception:
        log.exception("Failed to process dumb-phone command: %r", body)


@router.post("", status_code=status.HTTP_200_OK)
async def handle_reply(payload: InboundSMS, background_tasks: BackgroundTasks):
    """
    Receive an SMS from the dumb phone and route the reply back
    to its originating platform.

    Processing runs in the background so this endpoint acks the webhook
    immediately: some gateway apps (capcom6) retry the entire webhook
    delivery if they don't get a 2xx within ~30s, and commands that call
    out to an LLM (e.g. 'ask', 'world') can take longer than that.
    """
    if DUMB_PHONE and payload.from_number != DUMB_PHONE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not from dumb phone")

    background_tasks.add_task(_process_and_reply, payload.body)
    return {"status": "ok"}
