import asyncio
import json
import logging

logger = logging.getLogger("notification.sse")

clients = []

async def subscribe():
    q = asyncio.Queue()
    clients.append(q)
    logger.info(f"New SSE client connected. Total clients: {len(clients)}")
    try:
        while True:
            msg = await q.get()
            yield f"data: {json.dumps(msg, default=str)}\n\n"
    except asyncio.CancelledError:
        logger.info("SSE client disconnected.")
    finally:
        if q in clients:
            clients.remove(q)

async def broadcast(message: dict):
    for q in clients:
        await q.put(message)
