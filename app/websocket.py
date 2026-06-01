"""
WebSocket endpoint for real-time dashboard updates.
Broadcasts updated metrics to connected clients when events are ingested.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.database import db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])

# Connected WebSocket clients
_active_connections: Set[WebSocket] = set()


@router.websocket("/ws/live/{store_id}")
async def websocket_live(websocket: WebSocket, store_id: str):
    """
    WebSocket endpoint for live store metric updates.

    Sends updated metrics every 5 seconds (or on demand) to connected clients.
    """
    await websocket.accept()
    _active_connections.add(websocket)
    logger.info(f"WebSocket client connected for store {store_id}")

    try:
        while True:
            # Send updated metrics periodically
            metrics = await _get_live_metrics(store_id)
            await websocket.send_json(metrics)

            # Wait 5 seconds or until client sends a message (manual refresh)
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
            except asyncio.TimeoutError:
                pass  # Normal — just send next update

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected for store {store_id}")
    except Exception as e:
        logger.error(f"WebSocket error for store {store_id}: {e}")
    finally:
        _active_connections.discard(websocket)


async def broadcast_update(store_id: str):
    """Broadcast an update to all connected clients for a store."""
    if not _active_connections:
        return

    metrics = await _get_live_metrics(store_id)
    disconnected = set()

    for ws in _active_connections:
        try:
            await ws.send_json(metrics)
        except Exception:
            disconnected.add(ws)

    _active_connections -= disconnected


async def _get_live_metrics(store_id: str) -> dict:
    """Fetch current metrics for a store (lightweight query for live updates)."""
    try:
        async with db.acquire() as conn:
            # Quick metrics query
            visitors = await conn.fetchval(
                """
                SELECT COUNT(DISTINCT visitor_id) FROM events
                WHERE store_id = $1 AND event_type = 'ENTRY' AND is_staff = FALSE
                """,
                store_id,
            )

            exits = await conn.fetchval(
                """
                SELECT COUNT(DISTINCT visitor_id) FROM events
                WHERE store_id = $1 AND event_type = 'EXIT' AND is_staff = FALSE
                """,
                store_id,
            )

            current_in_store = (visitors or 0) - (exits or 0)

            queue_depth = await conn.fetchval(
                """
                SELECT COALESCE((metadata->>'queue_depth')::int, 0)
                FROM events
                WHERE store_id = $1 AND event_type = 'BILLING_QUEUE_JOIN'
                ORDER BY timestamp DESC LIMIT 1
                """,
                store_id,
            )

            last_event = await conn.fetchval(
                """
                SELECT MAX(timestamp) FROM events WHERE store_id = $1
                """,
                store_id,
            )

            total_events = await conn.fetchval(
                """
                SELECT COUNT(*) FROM events WHERE store_id = $1
                """,
                store_id,
            )

        return {
            "type": "metrics_update",
            "store_id": store_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "total_visitors": visitors or 0,
                "current_in_store": max(0, current_in_store),
                "total_exits": exits or 0,
                "queue_depth": queue_depth or 0,
                "total_events": total_events or 0,
                "last_event_at": last_event.isoformat() if last_event else None,
            },
        }

    except Exception as e:
        return {
            "type": "error",
            "store_id": store_id,
            "message": str(e),
        }
