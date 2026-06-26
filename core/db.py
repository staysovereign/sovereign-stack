from __future__ import annotations

import os
from collections import defaultdict, deque

import aiosqlite

from core.models.decree import DEFAULT_DECREES

DB_PATH = os.environ.get("SOVEREIGN_DB_PATH", "/data/sovereign.db")

_CREATE_COUNCIL = """
CREATE TABLE IF NOT EXISTS council (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    platform             TEXT NOT NULL,
    sender_id            TEXT NOT NULL,
    name                 TEXT NOT NULL,
    quiet_hours_override INTEGER NOT NULL DEFAULT 0,
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(platform, sender_id)
)
"""

_CREATE_DECREES = """
CREATE TABLE IF NOT EXISTS decrees (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    condition       TEXT NOT NULL,
    condition_value TEXT NOT NULL DEFAULT '{}',
    action          TEXT NOT NULL,
    enabled         INTEGER NOT NULL DEFAULT 1,
    priority        INTEGER NOT NULL DEFAULT 50,
    is_default      INTEGER NOT NULL DEFAULT 0
)
"""

_CREATE_VAULT = """
CREATE TABLE IF NOT EXISTS vault (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id          TEXT NOT NULL UNIQUE,
    message_json        TEXT NOT NULL,
    held_at             TEXT NOT NULL DEFAULT (datetime('now')),
    hold_reason         TEXT,
    needs_transcription INTEGER NOT NULL DEFAULT 0,
    retrieved           INTEGER NOT NULL DEFAULT 0,
    retrieved_at        TEXT
)
"""

_CREATE_CHRONICLE = """
CREATE TABLE IF NOT EXISTS chronicle (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id      TEXT NOT NULL,
    platform        TEXT NOT NULL,
    sender_id       TEXT NOT NULL,
    decision        TEXT NOT NULL,
    tier_triggered  TEXT,
    decree_id       INTEGER,
    decree_name     TEXT,
    timestamp       TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

_CREATE_SETTINGS = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
"""

# Delivery log: every SMS send attempt (success or failure)
_CREATE_DELIVERY_LOG = """
CREATE TABLE IF NOT EXISTS delivery_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id  TEXT NOT NULL,
    sent_at     TEXT NOT NULL DEFAULT (datetime('now')),
    sms_to      TEXT NOT NULL,
    sms_body    TEXT NOT NULL,
    gateway     TEXT NOT NULL,
    success     INTEGER NOT NULL,
    error       TEXT
)
"""

# Messages held at delivery during quiet hours — not dropped, waiting to drain
_CREATE_DELIVERY_HELD = """
CREATE TABLE IF NOT EXISTS delivery_held (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id  TEXT NOT NULL UNIQUE,
    message_json TEXT NOT NULL,
    result_json  TEXT NOT NULL,
    held_at     TEXT NOT NULL DEFAULT (datetime('now')),
    released    INTEGER NOT NULL DEFAULT 0,
    released_at TEXT
)
"""

# ── Default settings ──────────────────────────────────────────────────────────
DEFAULT_SETTINGS = {
    "quiet_hours_enabled": "false",
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "07:00",
    "quiet_hours_tz": "UTC",
    "quiet_hours_threshold_count": "5",
    "quiet_hours_threshold_window_seconds": "1800",
}

# ── Frequency state (in-memory) ───────────────────────────────────────────────
sender_timestamps: dict[str, deque] = defaultdict(lambda: deque(maxlen=50))


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with await get_db() as db:
        await db.execute(_CREATE_COUNCIL)
        await db.execute(_CREATE_DECREES)
        await db.execute(_CREATE_VAULT)
        await db.execute(_CREATE_CHRONICLE)
        await db.execute(_CREATE_SETTINGS)
        await db.execute(_CREATE_DELIVERY_LOG)
        await db.execute(_CREATE_DELIVERY_HELD)
        await db.commit()
        await _seed_decrees(db)
        await _seed_settings(db)


async def _seed_decrees(db: aiosqlite.Connection) -> None:
    row = await (await db.execute("SELECT COUNT(*) FROM decrees WHERE is_default = 1")).fetchone()
    if row[0] > 0:
        return
    for d in DEFAULT_DECREES:
        await db.execute(
            "INSERT INTO decrees (name, condition, condition_value, action, enabled, priority, is_default) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (d.name, d.condition.value, d.condition_value, d.action.value, int(d.enabled), d.priority, 1),
        )
    await db.commit()


async def _seed_settings(db: aiosqlite.Connection) -> None:
    for key, value in DEFAULT_SETTINGS.items():
        await db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
    await db.commit()


async def get_setting(db: aiosqlite.Connection, key: str) -> str | None:
    row = await (await db.execute("SELECT value FROM settings WHERE key = ?", (key,))).fetchone()
    return row["value"] if row else None
