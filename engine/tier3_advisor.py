from __future__ import annotations

import aiosqlite

from core.models.message import NormalizedMessage
from engine.result import EngineResult


async def evaluate(message: NormalizedMessage, db: aiosqlite.Connection) -> EngineResult | None:
    """
    Tier 3: The Advisor.
    Stub — returns None (no opinion) until Layer 5 is built.

    When implemented: loads the per-user behavioral model via Ollama,
    produces a confidence score, and returns a PASS result only if the
    score exceeds the user's configured threshold. Never stores message
    content; learns only from response-time signals.
    """
    return None
