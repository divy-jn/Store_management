"""
Shared test fixtures for the Store Intelligence API test suite.

# PROMPT: "Generate pytest fixtures for a FastAPI app with async PostgreSQL,
# including test client, sample events, and POS data fixtures."
# CHANGES MADE: Added idempotency test data, staff events, edge case fixtures,
# and custom async DB handling for test isolation.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def sample_event() -> dict:
    """A single valid event for testing."""
    return {
        "event_id": str(uuid.uuid4()),
        "store_id": "ST1008",
        "camera_id": "CAM_ENTRY_01",
        "visitor_id": "VIS_test001",
        "event_type": "ENTRY",
        "timestamp": "2026-04-10T12:30:00Z",
        "zone_id": None,
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": 0.92,
        "metadata": {
            "queue_depth": None,
            "sku_zone": None,
            "session_seq": 1,
        },
    }


@pytest.fixture
def sample_staff_event() -> dict:
    """A staff event (should be excluded from customer metrics)."""
    return {
        "event_id": str(uuid.uuid4()),
        "store_id": "ST1008",
        "camera_id": "CAM_FLOOR_01",
        "visitor_id": "VIS_staff001",
        "event_type": "ENTRY",
        "timestamp": "2026-04-10T12:35:00Z",
        "zone_id": None,
        "dwell_ms": 0,
        "is_staff": True,
        "confidence": 0.88,
        "metadata": {
            "queue_depth": None,
            "sku_zone": None,
            "session_seq": 1,
        },
    }


@pytest.fixture
def sample_events_batch() -> list[dict]:
    """A batch of events simulating a customer journey."""
    visitor_id = "VIS_journey001"
    base_events = [
        {
            "event_type": "ENTRY",
            "camera_id": "CAM_ENTRY_01",
            "zone_id": None,
            "timestamp": "2026-04-10T14:00:00Z",
            "dwell_ms": 0,
            "session_seq": 1,
        },
        {
            "event_type": "ZONE_ENTER",
            "camera_id": "CAM_FLOOR_01",
            "zone_id": "SKINCARE",
            "timestamp": "2026-04-10T14:02:00Z",
            "dwell_ms": 0,
            "session_seq": 2,
        },
        {
            "event_type": "ZONE_DWELL",
            "camera_id": "CAM_FLOOR_01",
            "zone_id": "SKINCARE",
            "timestamp": "2026-04-10T14:02:30Z",
            "dwell_ms": 30000,
            "session_seq": 3,
        },
        {
            "event_type": "ZONE_EXIT",
            "camera_id": "CAM_FLOOR_01",
            "zone_id": "SKINCARE",
            "timestamp": "2026-04-10T14:05:00Z",
            "dwell_ms": 0,
            "session_seq": 4,
        },
        {
            "event_type": "ZONE_ENTER",
            "camera_id": "CAM_FLOOR_01",
            "zone_id": "MAKEUP",
            "timestamp": "2026-04-10T14:05:30Z",
            "dwell_ms": 0,
            "session_seq": 5,
        },
        {
            "event_type": "ZONE_DWELL",
            "camera_id": "CAM_FLOOR_01",
            "zone_id": "MAKEUP",
            "timestamp": "2026-04-10T14:06:00Z",
            "dwell_ms": 45000,
            "session_seq": 6,
        },
        {
            "event_type": "BILLING_QUEUE_JOIN",
            "camera_id": "CAM_BILLING_01",
            "zone_id": "BILLING",
            "timestamp": "2026-04-10T14:10:00Z",
            "dwell_ms": 0,
            "session_seq": 7,
            "queue_depth": 2,
        },
        {
            "event_type": "EXIT",
            "camera_id": "CAM_ENTRY_01",
            "zone_id": None,
            "timestamp": "2026-04-10T14:15:00Z",
            "dwell_ms": 0,
            "session_seq": 8,
        },
    ]

    events = []
    for e in base_events:
        events.append(
            {
                "event_id": str(uuid.uuid4()),
                "store_id": "ST1008",
                "camera_id": e["camera_id"],
                "visitor_id": visitor_id,
                "event_type": e["event_type"],
                "timestamp": e["timestamp"],
                "zone_id": e["zone_id"],
                "dwell_ms": e["dwell_ms"],
                "is_staff": False,
                "confidence": 0.90,
                "metadata": {
                    "queue_depth": e.get("queue_depth"),
                    "sku_zone": e.get("zone_id"),
                    "session_seq": e["session_seq"],
                },
            }
        )

    return events


@pytest.fixture
def empty_store_events() -> list[dict]:
    """Empty event list for zero-traffic testing."""
    return []


@pytest_asyncio.fixture(scope="function")
async def async_client():
    """Async test client for route-level tests.

    Lifespan startup opens a real PostgreSQL connection, so unit tests keep it
    disabled and monkeypatch the database layer where needed.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
