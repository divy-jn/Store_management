"""
GET /stores/{store_id}/heatmap — Zone heatmap endpoint.

Returns zone visit frequency + average dwell time, normalized 0-100.
Includes data_confidence flag if fewer than 20 sessions in window.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.database import db
from app.models import HeatmapResponse, ZoneHeatmapEntry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Analytics"])


@router.get(
    "/stores/{store_id}/heatmap",
    response_model=HeatmapResponse,
    summary="Get zone heatmap data",
    description=(
        "Returns zone visit frequency and average dwell time, "
        "normalized 0-100 for grid heatmap rendering. "
        "Includes data_confidence flag for low-sample zones."
    ),
)
async def get_store_heatmap(store_id: str) -> HeatmapResponse:
    """Compute zone heatmap data for a store."""
    try:
        async with db.acquire() as conn:
            # Get total unique sessions for confidence calculation
            total_sessions = await conn.fetchval(
                """
                SELECT COUNT(DISTINCT visitor_id)
                FROM events
                WHERE store_id = $1
                  AND event_type = 'ENTRY'
                  AND is_staff = FALSE
                """,
                store_id,
            )
            total_sessions = total_sessions or 0

            # Get zone visit data
            zone_rows = await conn.fetch(
                """
                SELECT
                    zone_id,
                    COUNT(DISTINCT visitor_id) as visit_count,
                    AVG(dwell_ms) as avg_dwell_ms
                FROM events
                WHERE store_id = $1
                  AND is_staff = FALSE
                  AND zone_id IS NOT NULL
                  AND zone_id NOT IN ('ENTRY', 'INTERNAL', 'STORAGE')
                  AND event_type IN ('ZONE_ENTER', 'ZONE_DWELL')
                GROUP BY zone_id
                ORDER BY visit_count DESC
                """,
                store_id,
            )

        # Find max visit count for normalization
        max_visits = max((row["visit_count"] for row in zone_rows), default=1)

        zones = []
        for row in zone_rows:
            visit_count = row["visit_count"]
            avg_dwell = row["avg_dwell_ms"] or 0.0

            # Normalize to 0-100 scale
            normalized = (visit_count / max_visits * 100) if max_visits > 0 else 0

            # Data confidence based on session count
            confidence = "high" if visit_count >= 20 else "low"

            zones.append(
                ZoneHeatmapEntry(
                    zone_id=row["zone_id"],
                    zone_name=row["zone_id"].replace("_", " ").title(),
                    visit_count=visit_count,
                    avg_dwell_ms=round(avg_dwell, 2),
                    normalized_score=round(normalized, 2),
                    data_confidence=confidence,
                )
            )

        return HeatmapResponse(
            store_id=store_id,
            zones=zones,
            total_sessions=total_sessions,
        )

    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "service_unavailable",
                "message": "Database is currently unavailable.",
            },
        )
