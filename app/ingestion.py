"""
POST /events/ingest — Batch event ingestion endpoint.
Accepts up to 500 events, validates each individually, deduplicates, and stores them.
Idempotent by event_id. Supports TRUE partial success on malformed events.

A batch with a mix of valid and invalid events will accept the valid ones
and return error details for the invalid ones — never a blanket 422.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from app.database import db
from app.models import Event, EventError, IngestResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Ingestion"])


@router.post(
    "/events/ingest",
    response_model=IngestResponse,
    summary="Ingest a batch of detection events",
    description=(
        "Accepts batches of up to 500 events. Validates each event individually "
        "against the schema, deduplicates by event_id, and stores valid events. "
        "Returns counts of accepted, rejected, and duplicate events with error details. "
        "Malformed events do NOT cause the entire batch to fail."
    ),
)
async def ingest_events(request: Request) -> IngestResponse:
    """
    Ingest a batch of detection events with TRUE partial success.

    - Parses raw JSON body to avoid Pydantic rejecting the whole batch
    - Validates each event individually
    - Deduplicates by event_id (idempotent — safe to call twice)
    - Returns partial success: accepted + rejected counts with error details
    """
    # Parse raw JSON body so we control validation per-event
    try:
        raw_body = await request.json()
    except Exception:
        return IngestResponse(
            accepted=0,
            rejected=0,
            duplicates=0,
            errors=[EventError(event_id=None, index=0, error="Invalid JSON body")],
        )

    raw_events = raw_body.get("events", [])
    if not isinstance(raw_events, list):
        return IngestResponse(
            accepted=0,
            rejected=1,
            duplicates=0,
            errors=[
                EventError(event_id=None, index=0, error="'events' must be a list")
            ],
        )

    if len(raw_events) > 500:
        return IngestResponse(
            accepted=0,
            rejected=len(raw_events),
            duplicates=0,
            errors=[
                EventError(
                    event_id=None, index=0, error="Batch exceeds 500 event limit"
                )
            ],
        )

    request.state.event_count = len(raw_events)

    accepted = 0
    rejected = 0
    duplicates = 0
    errors: list[EventError] = []

    if not raw_events:
        return IngestResponse(accepted=0, rejected=0, duplicates=0, errors=[])

    try:
        async with db.acquire() as conn:
            for i, raw_event in enumerate(raw_events):
                # Step 1: Validate individually with Pydantic
                try:
                    event = Event.model_validate(raw_event)
                except (ValidationError, Exception) as ve:
                    rejected += 1
                    event_id = (
                        raw_event.get("event_id")
                        if isinstance(raw_event, dict)
                        else None
                    )
                    errors.append(
                        EventError(
                            event_id=event_id,
                            index=i,
                            error=str(ve),
                        )
                    )
                    logger.warning(
                        f"Event at index {i} rejected during validation: {ve}"
                    )
                    continue

                # Step 2: Insert into DB with idempotency
                try:
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
                        f"Event {event.event_id} rejected during insert: {e}"
                    )

    except RuntimeError:
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
