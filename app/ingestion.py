"""
POST /events/ingest — Batch event ingestion endpoint.
Accepts up to 500 events, validates, deduplicates, and stores them.
Idempotent by event_id. Supports partial success on malformed events.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from app.database import db
from app.models import Event, EventError, IngestRequest, IngestResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Ingestion"])


@router.post(
    "/events/ingest",
    response_model=IngestResponse,
    summary="Ingest a batch of detection events",
    description=(
        "Accepts batches of up to 500 events. Validates each event against the schema, "
        "deduplicates by event_id, and stores valid events. Returns counts of accepted, "
        "rejected, and duplicate events with error details for failures."
    ),
)
async def ingest_events(request: Request, body: IngestRequest) -> IngestResponse:
    """
    Ingest a batch of detection events.

    - Validates each event against the schema
    - Deduplicates by event_id (idempotent — safe to call twice)
    - Returns partial success: accepted + rejected counts with error details
    """
    events = body.events
    accepted = 0
    rejected = 0
    duplicates = 0
    errors: list[EventError] = []

    # Track event count for logging middleware
    request.state.event_count = len(events)

    if not events:
        return IngestResponse(accepted=0, rejected=0, duplicates=0, errors=[])

    try:
        async with db.acquire() as conn:
            for i, event in enumerate(events):
                try:
                    # Attempt to insert — ON CONFLICT DO NOTHING for idempotency
                    result = await conn.execute(
                        """
                        INSERT INTO events (
                            event_id, store_id, camera_id, visitor_id,
                            event_type, timestamp, zone_id, dwell_ms,
                            is_staff, confidence, metadata
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                        ON CONFLICT (event_id) DO NOTHING
                        """,
                        event.event_id,
                        event.store_id,
                        event.camera_id,
                        event.visitor_id,
                        event.event_type.value,
                        event.timestamp,
                        event.zone_id,
                        event.dwell_ms,
                        event.is_staff,
                        event.confidence,
                        json.dumps(event.metadata.model_dump()),
                    )

                    # Check if insert happened or was a duplicate
                    if result == "INSERT 0 1":
                        accepted += 1
                    else:
                        duplicates += 1

                except Exception as e:
                    rejected += 1
                    errors.append(
                        EventError(
                            event_id=event.event_id,
                            index=i,
                            error=str(e),
                        )
                    )
                    logger.warning(
                        f"Event {event.event_id} rejected: {e}",
                    )

    except RuntimeError:
        # Database not connected — graceful degradation
        raise HTTPException(
            status_code=503,
            detail={
                "error": "service_unavailable",
                "message": "Database is currently unavailable. Please retry later.",
            },
        )

    return IngestResponse(
        accepted=accepted,
        rejected=rejected,
        duplicates=duplicates,
        errors=errors,
    )
