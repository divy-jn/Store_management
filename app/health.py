"""
GET /health — Service health check endpoint.

Returns: service status, uptime, DB connection health,
last event timestamp per store, and STALE_FEED warnings.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from app.database import db
from app.models import HealthResponse, StoreHealth

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
    description=(
        "Returns service status, uptime, database connection health, "
        "last event timestamp per store, and STALE_FEED warnings."
    ),
)
async def health_check() -> HealthResponse:
    """Check service health and return status."""
    db_connected = await db.is_healthy()

    if not db_connected:
        return HealthResponse(
            status="unhealthy",
            uptime_seconds=round(db.uptime_seconds, 2),
            database_connected=False,
            stores=[],
            last_event_at=None,
        )

    try:
        async with db.acquire() as conn:
            # Get per-store health info
            store_rows = await conn.fetch("""
                SELECT
                    store_id,
                    MAX(timestamp) as last_event_at,
                    COUNT(*) as event_count
                FROM events
                GROUP BY store_id
                ORDER BY store_id
                """)

            now = datetime.now(timezone.utc)
            stale_threshold = now - timedelta(minutes=10)

            stores = []
            global_last_event = None

            for row in store_rows:
                last_event = row["last_event_at"]
                is_stale = last_event < stale_threshold if last_event else True

                stale_warning = None
                if is_stale and last_event:
                    minutes_ago = int((now - last_event).total_seconds() / 60)
                    stale_warning = (
                        f"STALE_FEED: No events received for {minutes_ago} minutes"
                    )

                stores.append(
                    StoreHealth(
                        store_id=row["store_id"],
                        last_event_at=last_event,
                        event_count=row["event_count"],
                        is_stale=is_stale,
                        stale_warning=stale_warning,
                    )
                )

                # Track global last event
                if last_event and (
                    global_last_event is None or last_event > global_last_event
                ):
                    global_last_event = last_event

        status = "healthy"
        if any(s.is_stale for s in stores):
            status = "degraded"

        return HealthResponse(
            status=status,
            uptime_seconds=round(db.uptime_seconds, 2),
            database_connected=True,
            stores=stores,
            last_event_at=global_last_event,
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="degraded",
            uptime_seconds=round(db.uptime_seconds, 2),
            database_connected=db_connected,
            stores=[],
            last_event_at=None,
        )
