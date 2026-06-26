from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from core.db import get_db

router = APIRouter(prefix="/api/decrees", tags=["decrees"])


class DecreeIn(BaseModel):
    name: str
    condition: str
    condition_value: dict = {}
    action: str
    priority: int = 50


class DecreeUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    condition_value: dict | None = None
    priority: int | None = None


@router.get("")
async def list_decrees():
    async with await get_db() as db:
        rows = await (await db.execute(
            "SELECT id, name, condition, condition_value, action, enabled, priority, is_default "
            "FROM decrees ORDER BY priority ASC"
        )).fetchall()
    return {
        "decrees": [
            {
                "id": r["id"],
                "name": r["name"],
                "condition": r["condition"],
                "condition_value": json.loads(r["condition_value"]),
                "action": r["action"],
                "enabled": bool(r["enabled"]),
                "priority": r["priority"],
                "is_default": bool(r["is_default"]),
            }
            for r in rows
        ]
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_decree(body: DecreeIn):
    async with await get_db() as db:
        cur = await db.execute(
            "INSERT INTO decrees (name, condition, condition_value, action, priority) "
            "VALUES (?, ?, ?, ?, ?)",
            (body.name, body.condition, json.dumps(body.condition_value), body.action, body.priority),
        )
        await db.commit()
    return {"id": cur.lastrowid}


@router.put("/{decree_id}", status_code=status.HTTP_200_OK)
async def update_decree(decree_id: int, body: DecreeUpdate):
    async with await get_db() as db:
        row = await (await db.execute("SELECT id FROM decrees WHERE id = ?", (decree_id,))).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        if body.name is not None:
            await db.execute("UPDATE decrees SET name = ? WHERE id = ?", (body.name, decree_id))
        if body.enabled is not None:
            await db.execute("UPDATE decrees SET enabled = ? WHERE id = ?", (int(body.enabled), decree_id))
        if body.condition_value is not None:
            await db.execute(
                "UPDATE decrees SET condition_value = ? WHERE id = ?",
                (json.dumps(body.condition_value), decree_id),
            )
        if body.priority is not None:
            await db.execute("UPDATE decrees SET priority = ? WHERE id = ?", (body.priority, decree_id))
        await db.commit()
    return {"status": "updated"}


@router.delete("/{decree_id}", status_code=status.HTTP_200_OK)
async def delete_decree(decree_id: int):
    async with await get_db() as db:
        row = await (await db.execute(
            "SELECT is_default FROM decrees WHERE id = ?", (decree_id,)
        )).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        if row["is_default"]:
            raise HTTPException(status_code=403, detail="Default decrees cannot be deleted. Disable them instead.")
        await db.execute("DELETE FROM decrees WHERE id = ?", (decree_id,))
        await db.commit()
    return {"status": "deleted"}
