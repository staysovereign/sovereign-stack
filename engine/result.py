from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Decision(str, Enum):
    PASS = "pass"   # urgent — forward to delivery layer
    HOLD = "hold"   # not urgent — store in vault


class Tier(str, Enum):
    COUNCIL = "council"
    DECREE = "decree"
    ADVISOR = "advisor"
    DEFAULT = "default"


@dataclass
class EngineResult:
    decision: Decision
    tier: Tier
    # For decree hits: the decree that fired
    decree_id: int | None = None
    decree_name: str | None = None
    # Human-readable note for the Chronicle
    reason: str = ""
