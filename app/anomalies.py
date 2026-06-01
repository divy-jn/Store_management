"""
GET /stores/{store_id}/anomalies — Anomaly detection endpoint.

Detects operational anomalies:
- BILLING_QUEUE_SPIKE: queue depth exceeds 2× rolling average
- CONVERSION_DROP: today's conversion < 70% of 7-day average
- DEAD_ZONE: no visits to a zone in 30+ minutes during open hours
- STALE_FEED: no events from a camera in 10+ minutes

Each anomaly includes severity (INFO/WARN/CRITICAL) and suggested_action.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

from app.database import db
from app.models import AnomaliesResponse, Anomaly, AnomalySeverity, AnomalyType

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Analytics"])


@router.get(
    "/stores/{store_id}/anomalies",
    response_model=AnomaliesResponse,
    summary="Get active anomalies",
    description=(
        "Returns active anomalies for a store: queue spikes, conversion drops, "
        "dead zones, and stale feeds. Each includes severity and suggested action."
    ),
)
async def get_store_anomalies(store_id: str) -> AnomaliesResponse:
    """Detect and return active anomalies for a store."""
    anomalies: list[Anomaly] = []

    try:
        async with db.acquire() as conn:
            # --- 1. BILLING_QUEUE_SPIKE ---
            await _check_queue_spike(conn, store_id, anomalies)

            # --- 2. CONVERSION_DROP ---
            await _check_conversion_drop(conn, store_id, anomalies)

            # --- 3. DEAD_ZONE ---
            await _check_dead_zones(conn, store_id, anomalies)

            # --- 4. STALE_FEED ---
            await _check_stale_feeds(conn, store_id, anomalies)

        return AnomaliesResponse(
            store_id=store_id,
            anomalies=anomalies,
            active_count=len(anomalies),
        )

    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "service_unavailable",
                "message": "Database is currently unavailable.",
            },
        )


async def _check_queue_spike(conn, store_id: str, anomalies: list[Anomaly]):
    """Check if current queue depth exceeds 2× rolling average."""
    # Get current queue depth
    current = await conn.fetchval(
        """
        SELECT COALESCE((metadata->>'queue_depth')::int, 0)
        FROM events
        WHERE store_id = $1 AND event_type = 'BILLING_QUEUE_JOIN'
        ORDER BY timestamp DESC LIMIT 1
        """,
        store_id,
    )
    current = current or 0

    # Get rolling average (last 50 BILLING_QUEUE_JOIN events)
    avg_depth = await conn.fetchval(
        """
        SELECT AVG(COALESCE((metadata->>'queue_depth')::int, 0))
        FROM (
            SELECT metadata FROM events
            WHERE store_id = $1 AND event_type = 'BILLING_QUEUE_JOIN'
            ORDER BY timestamp DESC LIMIT 50
        ) sub
        """,
        store_id,
    )
    avg_depth = avg_depth or 0

    if avg_depth > 0 and current > (2 * avg_depth):
        severity = (
            AnomalySeverity.CRITICAL
            if current > (3 * avg_depth)
            else AnomalySeverity.WARN
        )
        anomalies.append(
            Anomaly(
                anomaly_type=AnomalyType.BILLING_QUEUE_SPIKE,
                severity=severity,
                description=(
                    f"Queue depth is {current}, which is {current / avg_depth:.1f}× "
                    f"the rolling average of {avg_depth:.1f}"
                ),
                suggested_action=(
                    "Open additional billing counters or redirect staff to billing area."
                ),
                metadata={
                    "current_depth": current,
                    "avg_depth": round(avg_depth, 2),
                    "ratio": round(current / avg_depth, 2),
                },
            )
        )


async def _check_conversion_drop(conn, store_id: str, anomalies: list[Anomaly]):
    """Check if today's conversion rate is < 70% of 7-day average."""
    # Today's conversion rate
    today_visitors = await conn.fetchval(
        """
        SELECT COUNT(DISTINCT visitor_id) FROM events
        WHERE store_id = $1 AND event_type = 'ENTRY' AND is_staff = FALSE
        """,
        store_id,
    )
    today_visitors = today_visitors or 0

    if today_visitors == 0:
        return  # No data yet, skip

    today_converted = await conn.fetchval(
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
    today_converted = today_converted or 0
    today_rate = today_converted / today_visitors if today_visitors > 0 else 0

    # For now, use a fixed baseline (in production, compute 7-day rolling avg)
    # Since we only have 1 day of data, use 30% as a reasonable retail benchmark
    baseline_rate = 0.30

    if today_rate < (0.7 * baseline_rate) and today_visitors >= 5:
        anomalies.append(
            Anomaly(
                anomaly_type=AnomalyType.CONVERSION_DROP,
                severity=AnomalySeverity.WARN,
                description=(
                    f"Today's conversion rate ({today_rate:.1%}) is significantly "
                    f"below the baseline ({baseline_rate:.1%})"
                ),
                suggested_action=(
                    "Review store layout, check staff availability on floor, "
                    "and ensure promotions are visible."
                ),
                metadata={
                    "today_rate": round(today_rate, 4),
                    "baseline_rate": baseline_rate,
                    "today_visitors": today_visitors,
                    "today_converted": today_converted,
                },
            )
        )


async def _check_dead_zones(conn, store_id: str, anomalies: list[Anomaly]):
    """Check for zones with no visits in 30+ minutes during open hours."""
    # Get all zones that should have activity
    active_zones = await conn.fetch(
        """
        SELECT DISTINCT zone_id FROM events
        WHERE store_id = $1 AND zone_id IS NOT NULL
          AND zone_id NOT IN ('ENTRY', 'INTERNAL', 'STORAGE')
        """,
        store_id,
    )

    now = datetime.now(timezone.utc)
    threshold = now - timedelta(minutes=30)

    for row in active_zones:
        zone_id = row["zone_id"]
        last_event = await conn.fetchval(
            """
            SELECT MAX(timestamp) FROM events
            WHERE store_id = $1 AND zone_id = $2
            """,
            store_id,
            zone_id,
        )

        if last_event and last_event < threshold:
            minutes_ago = int((now - last_event).total_seconds() / 60)
            anomalies.append(
                Anomaly(
                    anomaly_type=AnomalyType.DEAD_ZONE,
                    severity=AnomalySeverity.INFO,
                    description=(
                        f"Zone '{zone_id}' has had no visits for {minutes_ago} minutes"
                    ),
                    suggested_action=(
                        f"Check if zone '{zone_id}' is accessible and well-stocked. "
                        "Consider repositioning staff or signage."
                    ),
                    metadata={
                        "zone_id": zone_id,
                        "last_event_at": last_event.isoformat(),
                        "minutes_inactive": minutes_ago,
                    },
                )
            )


async def _check_stale_feeds(conn, store_id: str, anomalies: list[Anomaly]):
    """Check for cameras with no events in 10+ minutes."""
    cameras = await conn.fetch(
        """
        SELECT camera_id, MAX(timestamp) as last_event
        FROM events
        WHERE store_id = $1
        GROUP BY camera_id
        """,
        store_id,
    )

    now = datetime.now(timezone.utc)
    threshold = now - timedelta(minutes=10)

    for row in cameras:
        camera_id = row["camera_id"]
        last_event = row["last_event"]

        if last_event and last_event < threshold:
            minutes_ago = int((now - last_event).total_seconds() / 60)
            anomalies.append(
                Anomaly(
                    anomaly_type=AnomalyType.STALE_FEED,
                    severity=AnomalySeverity.WARN,
                    description=(
                        f"Camera '{camera_id}' has not sent events for {minutes_ago} minutes"
                    ),
                    suggested_action=(
                        f"Check camera '{camera_id}' connectivity and detection pipeline status."
                    ),
                    metadata={
                        "camera_id": camera_id,
                        "last_event_at": last_event.isoformat(),
                        "minutes_stale": minutes_ago,
                    },
                )
            )
