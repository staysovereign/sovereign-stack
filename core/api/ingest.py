from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from core.models import NormalizedMessage
from core.queue import message_queue

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def ingest(message: NormalizedMessage, background_tasks: BackgroundTasks):
    """
    Receive a normalized message from any connector.
    The connector has already done platform-specific parsing; this endpoint
    validates the schema and hands the message to the urgency engine queue.
    """
    if message.content.body is None and message.content.media_url is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message must have either a text body or a media_url.",
        )

    background_tasks.add_task(message_queue.put_nowait, message)
    return {"status": "accepted", "id": str(message.id)}
