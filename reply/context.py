from __future__ import annotations

import json

import aiosqlite


async def recent_activity_summary(db: aiosqlite.Connection, limit: int = 8) -> str:
    """
    Compact text summary of recent Sovereign activity (delivered urgent
    messages + currently-held Vault items), for grounding 'ask' answers in
    the user's own data. Local-only by design — never pass this to 'world'
    (reply/claude.py), which leaves the machine for Anthropic's cloud.
    """
    sessions = await (
        await db.execute(
            "SELECT platform, sender_name, sender_id, created_at, sms_body "
            "FROM reply_sessions ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
    ).fetchall()

    held = await (
        await db.execute(
            "SELECT message_json, held_at FROM vault WHERE retrieved = 0 "
            "ORDER BY held_at DESC LIMIT ?",
            (limit,),
        )
    ).fetchall()

    lines: list[str] = []

    if sessions:
        lines.append("Recent delivered (urgent) messages:")
        for r in sessions:
            name = r["sender_name"] or r["sender_id"]
            lines.append(f"- {name} [{r['platform']}] {r['created_at'][:16]}: {r['sms_body'][:60]}")

    if held:
        lines.append("Currently held in the Vault (not yet seen by the user):")
        for r in held:
            msg = json.loads(r["message_json"])
            name = msg["sender"].get("name") or msg["sender"]["id"][:10]
            body = (msg["content"].get("body") or "[media]")[:60]
            lines.append(f"- {name} [{msg['platform']}] {r['held_at'][:16]}: {body}")

    return "\n".join(lines) if lines else "(no recent activity)"
