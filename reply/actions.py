from __future__ import annotations

import aiosqlite

from reply.session import _normalize, get_session_by_name

# Client-side tool definitions for the 'world' command (reply/claude.py).
# Each must have a matching entry in ACTION_HANDLERS below, keyed by name.
TOOLS = [
    {
        "name": "set_reminder",
        "description": (
            "Schedule a reminder that will be sent back to this phone via SMS "
            "after a delay. Use when the user asks to be reminded of something."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "delay_minutes": {
                    "type": "integer",
                    "description": "Minutes from now to send the reminder",
                },
                "text": {
                    "type": "string",
                    "description": "The reminder text to send back",
                },
            },
            "required": ["delay_minutes", "text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "add_to_council",
        "description": (
            "Mark a contact as VIP (the Council) so their messages always reach "
            "this phone, bypassing quiet hours. Only works for contacts who have "
            "sent at least one urgent message before. Use when the user asks to "
            "add/flag/promote someone as VIP or always-deliver."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The contact's name, as the user refers to them",
                },
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
]


async def set_reminder(input: dict, db: aiosqlite.Connection) -> str:
    delay_minutes = int(input["delay_minutes"])
    text = str(input["text"])[:200]
    await db.execute(
        "INSERT INTO reminders (text, due_at) VALUES (?, datetime('now', ? || ' minutes'))",
        (text, str(delay_minutes)),
    )
    await db.commit()
    return f"Reminder scheduled: '{text}' in {delay_minutes} minute(s)."


async def add_to_council(input: dict, db: aiosqlite.Connection) -> str:
    name = str(input["name"])
    row = await get_session_by_name(name, db)
    if row is None:
        return f"No recent contact matching '{name}' found — can't add to the Council."

    # WhatsApp/Instagram contacts can already be on the Council keyed by phone
    # number rather than the Matrix sender id reply_sessions stores (the engine
    # checks both — see engine/tier1_council.py — but inserting here regardless
    # would create a cosmetic duplicate row). Fuzzy-match by name first.
    existing = await (
        await db.execute("SELECT name FROM council WHERE platform = ?", (row["platform"],))
    ).fetchall()
    needle = _normalize(row["sender_name"] or name)
    for e in existing:
        if needle in _normalize(e["name"]):
            return f"{e['name']} is already on the Council."

    await db.execute(
        "INSERT OR IGNORE INTO council (platform, sender_id, name) VALUES (?, ?, ?)",
        (row["platform"], row["sender_id"], row["sender_name"] or name),
    )
    await db.commit()
    return f"{row['sender_name'] or name} added to the Council (always delivers now)."


ACTION_HANDLERS = {
    "set_reminder": set_reminder,
    "add_to_council": add_to_council,
}
