from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from core.db import get_db

router = APIRouter(prefix="/api/settings", tags=["settings"])

_KNOWN_KEYS = {
    "quiet_hours_enabled",
    "quiet_hours_start",
    "quiet_hours_end",
    "quiet_hours_timezone",
    "frequency_threshold",
    "frequency_window_minutes",
}


@router.get("")
async def get_settings():
    async with await get_db() as db:
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

    async with await get_db() as db:
        for key, value in body.values.items():
            await db.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
        await db.commit()
    return {"status": "updated", "keys": list(body.values)}
