"""
GET /stores/{store_id}/metrics — Real-time store metrics endpoint.

Returns: unique visitors, conversion rate, avg dwell per zone,
queue depth, and abandonment rate. Excludes staff events.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.database import db
from app.models import MetricsResponse, ZoneDwell

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Analytics"])


@router.get(
    "/stores/{store_id}/metrics",
    response_model=MetricsResponse,
    summary="Get real-time store metrics",
    description=(
        "Returns today's metrics: unique visitors, conversion rate, "
        "average dwell per zone, queue depth, and abandonment rate. "
        "Excludes staff (is_staff=true) from all customer metrics."
    ),
)
async def get_store_metrics(
    store_id: str,
    date: str | None = Query(
        None,
        description="Date filter (YYYY-MM-DD). Defaults to today.",
    ),
) -> MetricsResponse:
    """Compute real-time metrics for a store."""
    try:
        async with db.acquire() as conn:
            # --- Unique visitors (non-staff ENTRY events) ---
            unique_visitors = await conn.fetchval(
                """
                SELECT COUNT(DISTINCT visitor_id)
                FROM events
                WHERE store_id = $1
                  AND event_type = 'ENTRY'
                  AND is_staff = FALSE
                """,
                store_id,
            )
            unique_visitors = unique_visitors or 0

            # --- Total entries and exits ---
            total_entries = await conn.fetchval(
                """
                SELECT COUNT(*) FROM events
                WHERE store_id = $1 AND event_type = 'ENTRY' AND is_staff = FALSE
                """,
                store_id,
            )
            total_exits = await conn.fetchval(
                """
                SELECT COUNT(*) FROM events
                WHERE store_id = $1 AND event_type = 'EXIT' AND is_staff = FALSE
                """,
                store_id,
            )

            # --- Conversion rate ---
            # A visitor is "converted" if they were in the billing zone
            # within a 5-minute window before a POS transaction
            converted_visitors = await conn.fetchval(
                """
                SELECT COUNT(DISTINCT e.visitor_id)
                FROM events e
                JOIN pos_transactions p ON e.store_id = p.store_id
                WHERE e.store_id = $1
                  AND e.is_staff = FALSE
                  AND e.zone_id = 'BILLING'
                  AND e.event_type IN ('ZONE_ENTER', 'ZONE_DWELL', 'BILLING_QUEUE_JOIN')
                  AND e.timestamp BETWEEN (p.timestamp - INTERVAL '5 minutes') AND p.timestamp
                """,
                store_id,
            )
            converted_visitors = converted_visitors or 0
            conversion_rate = (
                converted_visitors / unique_visitors
                if unique_visitors > 0
                else 0.0
            )

            # --- Average dwell per zone ---
            zone_dwell_rows = await conn.fetch(
                """
                SELECT zone_id,
                       AVG(dwell_ms) as avg_dwell_ms,
                       COUNT(*) as visit_count
                FROM events
                WHERE store_id = $1
                  AND event_type = 'ZONE_DWELL'
                  AND is_staff = FALSE
                  AND zone_id IS NOT NULL
                GROUP BY zone_id
                ORDER BY avg_dwell_ms DESC
                """,
                store_id,
            )
            avg_dwell_per_zone = [
                ZoneDwell(
                    zone_id=row["zone_id"],
                    zone_name=row["zone_id"].replace("_", " ").title(),
                    avg_dwell_ms=round(row["avg_dwell_ms"], 2),
                    visit_count=row["visit_count"],
                )
                for row in zone_dwell_rows
            ]

            # --- Current queue depth ---
            current_queue_depth = await conn.fetchval(
                """
                SELECT COALESCE(
                    (metadata->>'queue_depth')::int, 0
                )
                FROM events
                WHERE store_id = $1
                  AND event_type = 'BILLING_QUEUE_JOIN'
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                store_id,
            )
            current_queue_depth = current_queue_depth or 0

            # --- Abandonment rate ---
            queue_joins = await conn.fetchval(
                """
                SELECT COUNT(*) FROM events
                WHERE store_id = $1 AND event_type = 'BILLING_QUEUE_JOIN'
                  AND is_staff = FALSE
                """,
                store_id,
            )
            queue_abandons = await conn.fetchval(
                """
                SELECT COUNT(*) FROM events
                WHERE store_id = $1 AND event_type = 'BILLING_QUEUE_ABANDON'
                  AND is_staff = FALSE
                """,
                store_id,
            )
            queue_joins = queue_joins or 0
            queue_abandons = queue_abandons or 0
            abandonment_rate = (
                queue_abandons / queue_joins if queue_joins > 0 else 0.0
            )

        return MetricsResponse(
            store_id=store_id,
            unique_visitors=unique_visitors,
            conversion_rate=round(conversion_rate, 4),
            avg_dwell_per_zone=avg_dwell_per_zone,
            current_queue_depth=current_queue_depth,
            abandonment_rate=round(abandonment_rate, 4),
            total_entries=total_entries or 0,
            total_exits=total_exits or 0,
        )

    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "service_unavailable",
                "message": "Database is currently unavailable.",
            },
        )
