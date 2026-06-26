from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.models.message import NormalizedMessage
from engine.result import EngineResult


@dataclass
class DeliveryItem:
    message: NormalizedMessage
    result: EngineResult


# Urgent messages leave the engine and wait here for the delivery worker to pick up.
delivery_queue: asyncio.Queue[DeliveryItem] = asyncio.Queue()
