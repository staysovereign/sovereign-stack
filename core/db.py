from __future__ import annotations

import os
from collections import defaultdict, deque
from contextlib import asynccontextmanager

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

# Reply sessions: maps a delivery to its originating conversation (15-min window)
_CREATE_REPLY_SESSIONS = """
CREATE TABLE IF NOT EXISTS reply_sessions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id       TEXT NOT NULL,
    platform         TEXT NOT NULL,
    sender_id        TEXT NOT NULL,
    sender_name      TEXT,
    platform_chat_id TEXT NOT NULL,  -- Telegram chat_id / WhatsApp room_id / email / phone
    sms_body         TEXT NOT NULL,  -- the SMS that was forwarded (for context)
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at       TEXT NOT NULL,  -- created_at + 15 minutes
    used             INTEGER NOT NULL DEFAULT 0
)
"""

# ── Advisor tables ────────────────────────────────────────────────────────────

# Resolved behavioral signals — the only data the Advisor ever stores about messages
_CREATE_ADVISOR_SIGNALS = """
CREATE TABLE IF NOT EXISTS advisor_signals (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_hash              TEXT NOT NULL,   -- SHA-256(platform:sender_id) — never plaintext
    platform                 TEXT NOT NULL,
    sovereign_decision       TEXT NOT NULL,   -- 'pass' or 'hold'
    tier_triggered           TEXT,
    response_time_seconds    INTEGER,         -- NULL until resolved
    outcome                  TEXT,            -- correct_pass | false_positive | false_negative | correct_hold
    hour_of_day              INTEGER,         -- 0-23, for time-of-day patterns
    recorded_at              TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

# Pending observations — awaiting response-time measurement
_CREATE_ADVISOR_PENDING = """
CREATE TABLE IF NOT EXISTS advisor_pending (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id               TEXT NOT NULL UNIQUE,
    sender_hash              TEXT NOT NULL,
    platform                 TEXT NOT NULL,
    decision                 TEXT NOT NULL,   -- 'pass' or 'hold'
    tier_triggered           TEXT,
    hour_of_day              INTEGER,
    decided_at               TEXT NOT NULL DEFAULT (datetime('now')),
    observation_window_secs  INTEGER NOT NULL  -- 600 for pass, 3600 for hold
)
"""

# Suggestions generated from the Advisor's analysis (shown in Interface Layer 6)
_CREATE_ADVISOR_SUGGESTIONS = """
CREATE TABLE IF NOT EXISTS advisor_suggestions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    type            TEXT NOT NULL,    -- 'council_promotion' | 'decree_suggestion' | 'pattern'
    sender_hash     TEXT,
    platform        TEXT,
    body            TEXT NOT NULL,    -- human-readable suggestion
    data_json       TEXT NOT NULL DEFAULT '{}',
    generated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    dismissed       INTEGER NOT NULL DEFAULT 0
)
"""

# Single-row state: maturity level and install timestamp
_CREATE_ADVISOR_STATE = """
CREATE TABLE IF NOT EXISTS advisor_state (
    id              INTEGER PRIMARY KEY DEFAULT 1,
    installed_at    TEXT NOT NULL DEFAULT (datetime('now')),
    first_signal_at TEXT,
    total_signals   INTEGER NOT NULL DEFAULT 0,
    maturity_level  INTEGER NOT NULL DEFAULT 0
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


@asynccontextmanager
async def get_db():
    """Open a configured aiosqlite connection as an async context manager.

    Use as `async with get_db() as db:`. The connection is awaited (and its
    worker thread started) exactly once here. Do not pre-await it at the call
    site (the old `async with await get_db()` form) — that awaits the
    connection twice, restarting the thread, which raises
    "threads can only be started once" on current aiosqlite.
    """
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
    finally:
        await db.close()


async def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with get_db() as db:
        await db.execute(_CREATE_COUNCIL)
        await db.execute(_CREATE_DECREES)
        await db.execute(_CREATE_VAULT)
        await db.execute(_CREATE_CHRONICLE)
        await db.execute(_CREATE_SETTINGS)
        await db.execute(_CREATE_DELIVERY_LOG)
        await db.execute(_CREATE_REPLY_SESSIONS)
        await db.execute(_CREATE_ADVISOR_SIGNALS)
        await db.execute(_CREATE_ADVISOR_PENDING)
        await db.execute(_CREATE_ADVISOR_SUGGESTIONS)
        await db.execute(_CREATE_ADVISOR_STATE)
        await db.execute(_CREATE_DELIVERY_HELD)
        await db.commit()
        await _seed_decrees(db)
        await _seed_settings(db)
        await _seed_advisor_state(db)


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


async def _seed_advisor_state(db: aiosqlite.Connection) -> None:
    await db.execute(
        "INSERT OR IGNORE INTO advisor_state (id) VALUES (1)"
    )
    await db.commit()


async def get_setting(db: aiosqlite.Connection, key: str) -> str | None:
    row = await (await db.execute("SELECT value FROM settings WHERE key = ?", (key,))).fetchone()
    return row["value"] if row else None
