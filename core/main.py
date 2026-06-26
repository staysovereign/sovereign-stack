from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.api.ingest import router as ingest_router
from core.api.reply import router as reply_router
from core.db import init_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    from engine.worker import run as engine_run
    from delivery.worker import run as delivery_run

    engine_task = asyncio.create_task(engine_run(), name="engine")
    delivery_task = asyncio.create_task(delivery_run(), name="delivery")

    yield

    for task in (engine_task, delivery_task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Sovereign Core", version="0.1.0", lifespan=lifespan)

app.include_router(ingest_router)
app.include_router(reply_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
