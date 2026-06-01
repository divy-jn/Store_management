"""
GET /stores/{store_id}/funnel — Conversion funnel endpoint.

Returns a session-based conversion funnel:
Entry → Zone Visit → Billing Queue → Purchase
with counts and drop-off percentages.

Re-entries do NOT double-count a visitor.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.database import db
from app.models import FunnelResponse, FunnelStage

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Analytics"])


@router.get(
    "/stores/{store_id}/funnel",
    response_model=FunnelResponse,
    summary="Get conversion funnel",
    description=(
        "Returns the conversion funnel: Entry → Zone Visit → Billing Queue → Purchase. "
        "Uses sessions as the unit. Re-entries do not double-count a visitor."
    ),
)
async def get_store_funnel(store_id: str) -> FunnelResponse:
    """Compute the conversion funnel for a store."""
    try:
        async with db.acquire() as conn:
            # Stage 1: Entry — unique visitors who entered (exclude REENTRY duplicates)
            entry_count = await conn.fetchval(
                """
                SELECT COUNT(DISTINCT visitor_id)
                FROM events
                WHERE store_id = $1
                  AND event_type IN ('ENTRY', 'REENTRY')
                  AND is_staff = FALSE
                """,
                store_id,
            )
            entry_count = entry_count or 0

            # Stage 2: Zone Visit — visitors who entered at least one product zone
            zone_visit_count = await conn.fetchval(
                """
                SELECT COUNT(DISTINCT visitor_id)
                FROM events
                WHERE store_id = $1
                  AND event_type IN ('ZONE_ENTER', 'ZONE_DWELL')
                  AND is_staff = FALSE
                  AND zone_id IS NOT NULL
                  AND zone_id NOT IN ('ENTRY', 'BILLING', 'INTERNAL', 'STORAGE')
                """,
                store_id,
            )
            zone_visit_count = zone_visit_count or 0

            # Stage 3: Billing Queue — visitors who entered the billing zone
            billing_count = await conn.fetchval(
                """
                SELECT COUNT(DISTINCT visitor_id)
                FROM events
                WHERE store_id = $1
                  AND is_staff = FALSE
                  AND (
                      (event_type IN ('ZONE_ENTER', 'ZONE_DWELL') AND zone_id = 'BILLING')
                      OR event_type = 'BILLING_QUEUE_JOIN'
                  )
                """,
                store_id,
            )
            billing_count = billing_count or 0

            # Stage 4: Purchase — visitors correlated to a POS transaction
            purchase_count = await conn.fetchval(
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
            purchase_count = purchase_count or 0

        # Build funnel stages with drop-off calculations
        stages = _build_funnel_stages(
            entry_count, zone_visit_count, billing_count, purchase_count
        )

        return FunnelResponse(
            store_id=store_id,
            stages=stages,
            total_sessions=entry_count,
        )

    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "service_unavailable",
                "message": "Database is currently unavailable.",
            },
        )


def _build_funnel_stages(
    entry: int, zone_visit: int, billing: int, purchase: int
) -> list[FunnelStage]:
    """Build funnel stages with percentage and drop-off calculations."""
    stages_data = [
        ("Entry", entry),
        ("Zone Visit", zone_visit),
        ("Billing Queue", billing),
        ("Purchase", purchase),
    ]

    stages = []
    for i, (stage_name, count) in enumerate(stages_data):
        percentage = (count / entry * 100) if entry > 0 else 0.0

        if i == 0:
            drop_off = 0.0
        else:
            prev_count = stages_data[i - 1][1]
            drop_off = (
                ((prev_count - count) / prev_count * 100)
                if prev_count > 0
                else 0.0
            )

        stages.append(
            FunnelStage(
                stage=stage_name,
                count=count,
                percentage=round(percentage, 2),
                drop_off_percent=round(drop_off, 2),
            )
        )

    return stages
