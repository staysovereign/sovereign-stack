from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from core.db import get_db

router = APIRouter(prefix="/api/council", tags=["council"])

_SOFT_CAP = 10


class MemberIn(BaseModel):
    platform: str
    sender_id: str
    name: str
    quiet_hours_override: bool = False


class MemberUpdate(BaseModel):
    name: str | None = None
    quiet_hours_override: bool | None = None


@router.get("")
async def list_council():
    async with await get_db() as db:
        rows = await (await db.execute(
            "SELECT id, platform, sender_id, name, quiet_hours_override, created_at "
            "FROM council ORDER BY name ASC"
        )).fetchall()
    members = [dict(r) for r in rows]
    for m in members:
        m["quiet_hours_override"] = bool(m["quiet_hours_override"])
    return {"members": members, "count": len(members), "soft_cap": _SOFT_CAP}


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_member(body: MemberIn):
    async with await get_db() as db:
        count = (await (await db.execute("SELECT COUNT(*) FROM council")).fetchone())[0]
        # Soft cap: allow but include a nudge in the response
        over_cap = count >= _SOFT_CAP

        try:
            await db.execute(
                "INSERT INTO council (platform, sender_id, name, quiet_hours_override) "
                "VALUES (?, ?, ?, ?)",
                (body.platform, body.sender_id, body.name, int(body.quiet_hours_override)),
            )
            await db.commit()
            row = await (await db.execute(
                "SELECT id FROM council WHERE platform = ? AND sender_id = ?",
                (body.platform, body.sender_id),
            )).fetchone()
        except Exception:
            raise HTTPException(status_code=409, detail="Member already exists on this platform")

    return {
        "id": row["id"],
        "nudge": "Your Council now has more than 10 members. An unlimited Council is no Council." if over_cap else None,
    }


@router.put("/{member_id}", status_code=status.HTTP_200_OK)
async def update_member(member_id: int, body: MemberUpdate):
    async with await get_db() as db:
        row = await (await db.execute("SELECT id FROM council WHERE id = ?", (member_id,))).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        if body.name is not None:
            await db.execute("UPDATE council SET name = ? WHERE id = ?", (body.name, member_id))
        if body.quiet_hours_override is not None:
            await db.execute(
                "UPDATE council SET quiet_hours_override = ? WHERE id = ?",
                (int(body.quiet_hours_override), member_id),
            )
        await db.commit()
    return {"status": "updated"}


@router.delete("/{member_id}", status_code=status.HTTP_200_OK)
async def remove_member(member_id: int):
    async with await get_db() as db:
        row = await (await db.execute("SELECT id FROM council WHERE id = ?", (member_id,))).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        await db.execute("DELETE FROM council WHERE id = ?", (member_id,))
        await db.commit()
    return {"status": "removed"}
