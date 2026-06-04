# PROMPT: Generate unit tests for the Pydantic Event model and EventType enum.
# Cover valid construction, confidence bounds, required fields, event_id defaults,
# negative dwell rejection, and all event types emitted by the detection pipeline.
# CHANGES MADE: Added boundary tests at 0.0/1.0 confidence, REENTRY coverage,
# metadata default verification, and explicit negative dwell validation.
"""Tests for Pydantic models used across the Store Intelligence API."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.models import Event, EventMetadata, EventType


def test_event_type_enum_contains_all_pipeline_events():
    """All event types emitted by the pipeline must exist in the enum."""
    expected = {
        "ENTRY",
        "EXIT",
        "ZONE_ENTER",
        "ZONE_EXIT",
        "ZONE_DWELL",
        "BILLING_QUEUE_JOIN",
        "BILLING_QUEUE_ABANDON",
        "REENTRY",
    }
    actual = {e.value for e in EventType}
    assert expected == actual


def test_event_valid_construction():
    """A fully-specified event should parse without errors."""
    event = Event(
        event_id=str(uuid.uuid4()),
        store_id="ST1008",
        camera_id="CAM_ENTRY_01",
        visitor_id="VIS_001",
        event_type=EventType.ENTRY,
        timestamp="2026-04-10T12:00:00Z",
        confidence=0.92,
    )
    assert event.store_id == "ST1008"
    assert event.is_staff is False
    assert event.dwell_ms == 0


def test_event_default_event_id_is_uuid():
    """If event_id is omitted, a UUID v4 should be generated automatically."""
    event = Event(
        store_id="ST1008",
        camera_id="CAM_ENTRY_01",
        visitor_id="VIS_001",
        event_type=EventType.ENTRY,
        timestamp="2026-04-10T12:00:00Z",
        confidence=0.5,
    )
    # Should be a valid UUID
    uuid.UUID(event.event_id)


def test_event_confidence_at_boundaries():
    """Confidence of exactly 0.0 and 1.0 should be valid."""
    for conf in [0.0, 1.0]:
        event = Event(
            store_id="ST1008",
            camera_id="CAM_ENTRY_01",
            visitor_id="VIS_001",
            event_type=EventType.ENTRY,
            timestamp="2026-04-10T12:00:00Z",
            confidence=conf,
        )
        assert event.confidence == conf


def test_event_rejects_confidence_above_one():
    """Confidence > 1.0 should fail Pydantic validation."""
    with pytest.raises(ValidationError):
        Event(
            store_id="ST1008",
            camera_id="CAM_ENTRY_01",
            visitor_id="VIS_001",
            event_type=EventType.ENTRY,
            timestamp="2026-04-10T12:00:00Z",
            confidence=1.5,
        )


def test_event_rejects_negative_confidence():
    """Confidence < 0.0 should fail Pydantic validation."""
    with pytest.raises(ValidationError):
        Event(
            store_id="ST1008",
            camera_id="CAM_ENTRY_01",
            visitor_id="VIS_001",
            event_type=EventType.ENTRY,
            timestamp="2026-04-10T12:00:00Z",
            confidence=-0.1,
        )


def test_event_rejects_missing_required_fields():
    """Omitting required fields like store_id or visitor_id should fail."""
    with pytest.raises(ValidationError):
        Event(
            camera_id="CAM_ENTRY_01",
            event_type=EventType.ENTRY,
            timestamp="2026-04-10T12:00:00Z",
            confidence=0.5,
        )


def test_event_metadata_defaults_to_empty():
    """Metadata should default to an EventMetadata with all None fields."""
    event = Event(
        store_id="ST1008",
        camera_id="CAM_ENTRY_01",
        visitor_id="VIS_001",
        event_type=EventType.ENTRY,
        timestamp="2026-04-10T12:00:00Z",
        confidence=0.5,
    )
    assert isinstance(event.metadata, EventMetadata)
    assert event.metadata.queue_depth is None


def test_event_rejects_negative_dwell_ms():
    """dwell_ms must be >= 0."""
    with pytest.raises(ValidationError):
        Event(
            store_id="ST1008",
            camera_id="CAM_ENTRY_01",
            visitor_id="VIS_001",
            event_type=EventType.ZONE_DWELL,
            timestamp="2026-04-10T12:00:00Z",
            confidence=0.5,
            dwell_ms=-100,
        )
