from __future__ import annotations

import logging
from datetime import datetime, timezone

import aiosqlite

from core.db import get_db, get_setting
from reply.parser import CommandType, ParsedCommand, parse
from reply.sender import send_reply
from reply.session import get_active_session, get_session_by_index, get_session_by_name, mark_used

log = logging.getLogger("sovereign.reply")


async def handle(raw_sms: str) -> str:
    """
    Entry point for an inbound SMS from the dumb phone.
    Returns a confirmation SMS body to send back to the dumb phone.
    """
    cmd = parse(raw_sms)
    async with await get_db() as db:
        return await _dispatch(cmd, db)


async def _dispatch(cmd: ParsedCommand, db: aiosqlite.Connection) -> str:
    if cmd.type == CommandType.STATUS:
        return await _cmd_status(db)

    if cmd.type == CommandType.LIST:
        return await _cmd_list(db)

    if cmd.type == CommandType.READ:
        return await _cmd_read(cmd.index, db)

    if cmd.type == CommandType.REPLY_LATEST:
        return await _cmd_reply_session(await get_active_session(db), cmd.text, db)

    if cmd.type == CommandType.REPLY_NAME:
        session = await get_session_by_name(cmd.name, db)
        return await _cmd_reply_session(session, cmd.text, db)

    if cmd.type == CommandType.REPLY_INDEX:
        session = await get_session_by_index(cmd.index, db)
        return await _cmd_reply_session(session, cmd.text, db)

    return "SOVEREIGN: Unknown command. Send 'status' for help."


async def _cmd_reply_session(session, text: str | None, db: aiosqlite.Connection) -> str:
    if session is None:
        return "SOVEREIGN: No recent conversation found. Use 'list' to see held messages."

    if not text:
        return "SOVEREIGN: Empty reply. Try: r Your message here"

    platform = session["platform"]
    chat_id = session["platform_chat_id"]
    name = session["sender_name"] or session["sender_id"]

    try:
        await send_reply(platform, chat_id, text)
        await mark_used(session["id"], db)
        tag = platform[:2].upper()
        return f"SOVEREIGN: Sent to [{tag}] {name}"
    except Exception as exc:
        log.error("Reply failed to [%s] %s: %s", platform, chat_id, exc)
        return f"SOVEREIGN: Send failed — {exc}"


async def _cmd_status(db: aiosqlite.Connection) -> str:
    now_str = datetime.now().strftime("%H:%M")

    held_count = (
        await (await db.execute("SELECT COUNT(*) FROM vault WHERE retrieved = 0")).fetchone()
    )[0]

    urgent_today = (
        await (
            await db.execute(
                "SELECT COUNT(*) FROM chronicle WHERE decision = 'pass' AND date(timestamp) = date('now')"
            )
        ).fetchone()
    )[0]

    last_row = await (
        await db.execute(
            "SELECT platform, sender_id, sender_name, created_at FROM reply_sessions "
            "ORDER BY created_at DESC LIMIT 1"
        )
    ).fetchone()

    if last_row:
        name = last_row["sender_name"] or last_row["sender_id"]
        tag = last_row["platform"][:2].upper()
        ts = last_row["created_at"][11:16]
        last_line = f"Last: {name} ({tag}) {ts}"
    else:
        last_line = "Last: none"

    # Council quiet check: any Council member in reply_sessions in last hour?
    council_recent = await (
        await db.execute(
            """
            SELECT rs.sender_name FROM reply_sessions rs
            JOIN council c ON c.platform = rs.platform AND c.sender_id = rs.sender_id
            WHERE rs.created_at > datetime('now', '-1 hour')
            ORDER BY rs.created_at DESC LIMIT 1
            """
        )
    ).fetchone()
    council_line = f"Council: {council_recent['sender_name']}" if council_recent else "Council: quiet"

    quiet_enabled = (await get_setting(db, "quiet_hours_enabled")) == "true"
    quiet_end = await get_setting(db, "quiet_hours_end") or "07:00"
    next_line = f"Window ends: {quiet_end}" if quiet_enabled else "Quiet hours: off"

    return (
        f"SOVEREIGN {now_str}\n"
        f"Held: {held_count} • Urgent: {urgent_today} today\n"
        f"{last_line}\n"
        f"{council_line}\n"
        f"{next_line}"
    )


async def _cmd_list(db: aiosqlite.Connection) -> str:
    rows = await (
        await db.execute(
            "SELECT message_json FROM vault WHERE retrieved = 0 ORDER BY held_at DESC LIMIT 10"
        )
    ).fetchall()

    if not rows:
        return "SOVEREIGN: Vault is empty."

    import json
    lines = ["SOVEREIGN LIST"]
    for i, row in enumerate(rows, 1):
        msg = json.loads(row["message_json"])
        tag = msg["platform"][:2].upper()
        name = msg["sender"].get("name") or msg["sender"]["id"][:10]
        ts = msg["timestamp"][11:16]
        body = (msg["content"].get("body") or "[media]")[:40]
        lines.append(f"{i}. [{tag}] {name} {ts}: {body}")

    return "\n".join(lines)


async def _cmd_read(index: int | None, db: aiosqlite.Connection) -> str:
    if index is None or index < 1:
        return "SOVEREIGN: Usage: read N (e.g. read 2)"

    import json
    row = await (
        await db.execute(
            "SELECT message_json, held_at FROM vault WHERE retrieved = 0 "
            "ORDER BY held_at DESC LIMIT 1 OFFSET ?",
            (index - 1,),
        )
    ).fetchone()

    if row is None:
        return f"SOVEREIGN: No message at position {index}. Send 'list' to see available messages."

    msg = json.loads(row["message_json"])
    tag = msg["platform"][:2].upper()
    name = msg["sender"].get("name") or msg["sender"]["id"][:10]
    ts = row["held_at"][:16].replace("T", " ")
    body = msg["content"].get("body") or "[media — no text content]"

    return f"[{tag}] {name} • {ts}\n{body}"
