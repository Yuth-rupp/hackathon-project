"""
FloodPulse AI - Real-time event broker

A tiny in-process publish/subscribe hub. Background jobs and API routes call
``broker.publish(...)``; every browser connected to an SSE endpoint
(``GET /hydrology/stream`` or ``GET /community/stream``) receives the event
immediately.

Event types currently published:
    station_reading   a gauge received new readings
    discharge_updated river discharge forecast refreshed
    risk_updated      a flood risk assessment was stored for a location
    alert_created     the system or an officer raised an alert
    alert_changed     an alert was acknowledged or resolved

Note: this broker lives in memory, so it works when the API runs as ONE
process (``uvicorn app.main:app``). If you later run several workers, swap this
for Redis pub/sub - the publish()/subscribe() interface can stay the same.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, Set

from fastapi import Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)


class EventBroker:
    def __init__(self, max_queue: int = 100) -> None:
        self._subscribers: Set[asyncio.Queue] = set()
        self._max_queue = max_queue

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue)
        self._subscribers.add(queue)
        logger.info("SSE client connected (%s total)", len(self._subscribers))
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)
        logger.info("SSE client disconnected (%s total)", len(self._subscribers))

    def publish(self, event_type: str, data: Dict[str, Any] | None = None) -> int:
        """Send an event to every connected client. Never blocks or raises."""
        event = {
            "type": event_type,
            "server_time": datetime.now(timezone.utc).isoformat(),
            **(data or {}),
        }

        delivered = 0
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Slow client: drop its oldest event so it stays current.
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except Exception:
                    continue
            delivered += 1

        return delivered


broker = EventBroker()


# ---------------------------------------------------------------------
# Shared Server-Sent Events response (used by /community/stream)
# ---------------------------------------------------------------------

def sse_message(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _event_generator(request: Request) -> AsyncIterator[str]:
    queue = broker.subscribe()

    try:
        yield "retry: 5000\n\n"
        yield sse_message(
            "hello",
            {
                "server_time": datetime.now(timezone.utc).isoformat(),
                "heartbeat_seconds": 15,
            },
        )

        while True:
            if await request.is_disconnected():
                break

            try:
                event = await asyncio.wait_for(queue.get(), timeout=15)
                yield sse_message(event["type"], event)
            except asyncio.TimeoutError:
                yield sse_message(
                    "heartbeat",
                    {"server_time": datetime.now(timezone.utc).isoformat()},
                )
    finally:
        broker.unsubscribe(queue)


def sse_response(request: Request) -> StreamingResponse:
    return StreamingResponse(
        _event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )