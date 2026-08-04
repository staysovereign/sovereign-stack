import asyncio

# Shared in-process queue between the ingest endpoint and the urgency engine.
# Layer 2 (engine) consumes from this queue.
message_queue: asyncio.Queue = asyncio.Queue()
