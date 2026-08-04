from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum


class DecreeCondition(str, Enum):
    GROUP = "group"             # message is a group message
    KEYWORD = "keyword"         # body contains one of a keyword list
    FREQUENCY = "frequency"     # sender sent N+ messages in T seconds
    PLATFORM = "platform"       # message came from a specific platform
    MESSAGE_TYPE = "message_type"  # e.g. voice notes


class DecreeAction(str, Enum):
    PASS_THROUGH = "pass_through"  # mark urgent, forward immediately
    HOLD = "hold"                  # explicitly hold (overrides keywords etc.)


@dataclass
class Decree:
    name: str
    condition: DecreeCondition
    action: DecreeAction
    # JSON-encoded parameters for the condition evaluator
    condition_value: str = "{}"
    enabled: bool = True
    # lower priority number = evaluated first
    priority: int = 50
    id: int | None = None
    is_default: bool = False  # seeded defaults, shown differently in interface

    @property
    def params(self) -> dict:
        return json.loads(self.condition_value)


# ── Default Decrees seeded into every new Realm ──────────────────────────────

DEFAULT_DECREES: list[Decree] = [
    # Groups are never urgent — evaluated first so they can't be overridden
    Decree(
        name="Hold all group messages",
        condition=DecreeCondition.GROUP,
        action=DecreeAction.HOLD,
        condition_value="{}",
        priority=1,
        is_default=True,
    ),
    # Urgency keywords in any language
    Decree(
        name="Urgency keywords",
        condition=DecreeCondition.KEYWORD,
        action=DecreeAction.PASS_THROUGH,
        condition_value=json.dumps({
            "keywords": [
                "emergency", "urgent", "hospital", "accident",
                "llámame", "ayuda", "please call",
                "urgente", "emergencia",
            ],
            "case_sensitive": False,
        }),
        priority=10,
        is_default=True,
    ),
    # Frequency escalation: same sender 3+ times in 10 minutes
    Decree(
        name="Frequency escalation",
        condition=DecreeCondition.FREQUENCY,
        action=DecreeAction.PASS_THROUGH,
        condition_value=json.dumps({"count": 3, "window_seconds": 600}),
        priority=20,
        is_default=True,
    ),
]
