import asyncio

# Urgent messages leave the engine and wait here for Layer 3 (delivery) to pick up.
delivery_queue: asyncio.Queue = asyncio.Queue()
