from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from delivery.gateway import send

router = APIRouter(prefix="/reply", tags=["reply"])

DUMB_PHONE = os.environ.get("DUMB_PHONE_NUMBER", "")


class InboundSMS(BaseModel):
    from_number: str
    body: str


@router.post("", status_code=status.HTTP_200_OK)
async def handle_reply(payload: InboundSMS):
    """
    Receive an SMS from the dumb phone and route the reply back
    to its originating platform.
    """
    if DUMB_PHONE and payload.from_number != DUMB_PHONE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not from dumb phone")

    from reply.router import handle
    confirmation = await handle(payload.body)

    # Send confirmation SMS back to the dumb phone
    if confirmation:
        await send(confirmation)

    return {"status": "ok"}
