from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query, status

from core.db import get_db

router = APIRouter(prefix="/api/vault", tags=["vault"])


@router.get("")
async def list_vault(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    retrieved: bool = Query(False),
):
    offset = (page - 1) * limit
    filter_clause = "" if retrieved else "WHERE retrieved = 0"
    async with get_db() as db:
        total = (await (await db.execute(
            f"SELECT COUNT(*) FROM vault {filter_clause}"
        )).fetchone())[0]

        rows = await (await db.execute(
            f"SELECT id, message_id, message_json, held_at, hold_reason, "
            f"needs_transcription, retrieved, retrieved_at "
            f"FROM vault {filter_clause} ORDER BY held_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )).fetchall()

    items = []
    for r in rows:
        msg = json.loads(r["message_json"])
        items.append({
            "id": r["id"],
            "message_id": r["message_id"],
            "held_at": r["held_at"],
            "hold_reason": r["hold_reason"],
            "needs_transcription": bool(r["needs_transcription"]),
            "retrieved": bool(r["retrieved"]),
            "retrieved_at": r["retrieved_at"],
            "platform": msg["platform"],
            "sender": msg["sender"],
            "content": msg["content"],
            "group": msg.get("group"),
        })

    return {"items": items, "total": total, "page": page, "limit": limit}


@router.post("/{vault_id}/retrieve", status_code=status.HTTP_200_OK)
async def mark_retrieved(vault_id: int):
    """Mark a vault entry as retrieved. Signals the Advisor (false negative check)."""
    async with get_db() as db:
        row = await (await db.execute(
            "SELECT id, retrieved FROM vault WHERE id = ?", (vault_id,)
        )).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        if row["retrieved"]:
            return {"status": "already_retrieved"}
        await db.execute(
            "UPDATE vault SET retrieved = 1, retrieved_at = datetime('now') WHERE id = ?",
            (vault_id,),
        )
        await db.commit()
    return {"status": "retrieved"}
