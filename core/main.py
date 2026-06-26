from fastapi import FastAPI

from core.api.ingest import router as ingest_router

app = FastAPI(title="Sovereign Core", version="0.1.0")

app.include_router(ingest_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
