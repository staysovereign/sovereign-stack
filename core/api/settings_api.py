from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from core.db import get_db

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Keys the engine/delivery actually read (see delivery/quiet_hours.py).
_KNOWN_KEYS = {
    "quiet_hours_enabled",
    "quiet_hours_start",
    "quiet_hours_end",
    "quiet_hours_tz",
    "quiet_hours_threshold_count",
    "quiet_hours_threshold_window_seconds",
}


@router.get("")
async def get_settings():
    async with get_db() as db:
        rows = await (await db.execute("SELECT key, value FROM settings")).fetchall()
    return {r["key"]: r["value"] for r in rows}


class SettingsPatch(BaseModel):
    values: dict[str, str]


@router.put("")
async def update_settings(body: SettingsPatch):
    unknown = set(body.values) - _KNOWN_KEYS
    if unknown:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Unknown settings: {sorted(unknown)}")

    async with get_db() as db:
        for key, value in body.values.items():
            await db.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
        await db.commit()
    return {"status": "updated", "keys": list(body.values)}
