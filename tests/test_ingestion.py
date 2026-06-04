# PROMPT: Generate route tests for POST /events/ingest that prove true partial
# success, event_id idempotency, malformed-event rejection, invalid JSON handling,
# and compatibility with sample event variants from the challenge packet.
# CHANGES MADE: Built a fake async DB layer, added duplicate handling assertions,
# and covered entry, zone, and queue sample normalization paths.
"""Tests for the /events/ingest endpoint with true partial success."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app import ingestion

# ---------------------------------------------------------------------------
# Fake DB layer for unit tests (no Postgres required)
# ---------------------------------------------------------------------------


class FakeConnection:
    """Simulates asyncpg connection with an in-memory event store."""

    def __init__(self):
        self.inserted = {}  # event_id -> event data

    async def execute(self, query, *args):
        event_id = args[0]
        if event_id in self.inserted:
            return "INSERT 0 0"  # duplicate
        self.inserted[event_id] = args
        return "INSERT 0 1"


class FakeDB:
    def __init__(self):
        self.conn = FakeConnection()

    def acquire(self):
        return self

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _make_event(**overrides) -> dict:
    """Helper to create a valid event dict."""
    base = {
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
        "metadata": {"queue_depth": None, "sku_zone": None, "session_seq": 1},
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_accepts_valid_events(async_client: AsyncClient, monkeypatch):
    """A batch of valid events should all be accepted."""
    monkeypatch.setattr(ingestion, "db", FakeDB())

    events = [_make_event() for _ in range(3)]
    response = await async_client.post("/events/ingest", json={"events": events})

    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] == 3
    assert data["rejected"] == 0
    assert data["duplicates"] == 0


@pytest.mark.asyncio
async def test_ingest_partial_success_with_malformed_events(
    async_client: AsyncClient, monkeypatch
):
    """A batch with 2 valid and 1 malformed event should accept 2 and reject 1."""
    monkeypatch.setattr(ingestion, "db", FakeDB())

    valid1 = _make_event()
    valid2 = _make_event()
    malformed = {"event_id": "bad", "store_id": "ST1008"}  # missing required fields

    response = await async_client.post(
        "/events/ingest", json={"events": [valid1, malformed, valid2]}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] == 2
    assert data["rejected"] == 1
    assert len(data["errors"]) == 1
    assert data["errors"][0]["index"] == 1


@pytest.mark.asyncio
async def test_ingest_handles_duplicate_event_ids(
    async_client: AsyncClient, monkeypatch
):
    """Sending the same event_id twice should count as a duplicate, not an error."""
    fake_db = FakeDB()
    monkeypatch.setattr(ingestion, "db", fake_db)

    event = _make_event()
    dup_event = _make_event(event_id=event["event_id"])

    response = await async_client.post(
        "/events/ingest", json={"events": [event, dup_event]}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] == 1
    assert data["duplicates"] == 1
    assert data["rejected"] == 0


@pytest.mark.asyncio
async def test_ingest_empty_batch(async_client: AsyncClient, monkeypatch):
    """An empty batch should return zeros, not an error."""
    monkeypatch.setattr(ingestion, "db", FakeDB())

    response = await async_client.post("/events/ingest", json={"events": []})

    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] == 0
    assert data["rejected"] == 0


@pytest.mark.asyncio
async def test_ingest_rejects_invalid_confidence(
    async_client: AsyncClient, monkeypatch
):
    """Confidence outside [0.0, 1.0] should be rejected by Pydantic validation."""
    monkeypatch.setattr(ingestion, "db", FakeDB())

    bad_event = _make_event(confidence=1.5)

    response = await async_client.post("/events/ingest", json={"events": [bad_event]})

    assert response.status_code == 200
    data = response.json()
    assert data["rejected"] == 1
    assert data["accepted"] == 0


@pytest.mark.asyncio
async def test_ingest_rejects_invalid_event_type(
    async_client: AsyncClient, monkeypatch
):
    """An unknown event_type should be rejected per-event, not crash the batch."""
    monkeypatch.setattr(ingestion, "db", FakeDB())

    bad_event = _make_event(event_type="TELEPORT")

    response = await async_client.post("/events/ingest", json={"events": [bad_event]})

    assert response.status_code == 200
    data = response.json()
    assert data["rejected"] == 1


@pytest.mark.asyncio
async def test_ingest_invalid_json_body(async_client: AsyncClient, monkeypatch):
    """Sending non-JSON body should return a graceful error, not 500."""
    monkeypatch.setattr(ingestion, "db", FakeDB())

    response = await async_client.post(
        "/events/ingest",
        content=b"this is not json",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] == 0
    assert len(data["errors"]) >= 1


@pytest.mark.asyncio
async def test_ingest_accepts_new_sample_entry_schema(
    async_client: AsyncClient, monkeypatch
):
    """New challenge sample entry events should normalize into canonical ENTRY."""
    monkeypatch.setattr(ingestion, "db", FakeDB())

    sample_entry = {
        "event_type": "entry",
        "id_token": "ID_60001",
        "store_code": "store_1076",
        "camera_id": "cam1",
        "event_timestamp": "2026-03-08T18:10:05.120000",
        "is_staff": False,
    }

    response = await async_client.post(
        "/events/ingest", json={"events": [sample_entry]}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] == 1
    assert data["rejected"] == 0


@pytest.mark.asyncio
async def test_ingest_accepts_new_sample_zone_schema(
    async_client: AsyncClient, monkeypatch
):
    """New challenge zone_entered events should normalize into ZONE_ENTER."""
    monkeypatch.setattr(ingestion, "db", FakeDB())

    sample_zone = {
        "event_type": "zone_entered",
        "track_id": 101,
        "store_id": "ST1076",
        "camera_id": "CAM2",
        "zone_id": "PURPLLE_MUM_1076_Z01",
        "zone_name": "Left Shelf",
        "event_time": "2026-03-08T18:10:45.280000",
    }

    response = await async_client.post("/events/ingest", json={"events": [sample_zone]})

    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] == 1
    assert data["rejected"] == 0


@pytest.mark.asyncio
async def test_ingest_accepts_new_sample_queue_schema(
    async_client: AsyncClient, monkeypatch
):
    """New challenge queue_abandoned events should normalize into abandon events."""
    monkeypatch.setattr(ingestion, "db", FakeDB())

    sample_queue = {
        "queue_event_id": str(uuid.uuid4()),
        "event_type": "queue_abandoned",
        "track_id": 101,
        "store_id": "ST1076",
        "camera_id": "PURPLLE_MUM_1076_CAM6",
        "zone_id": "PURPLLE_MUM_1076_Z_BILLING_01",
        "zone_name": "Billing Counter Queue",
        "queue_join_ts": "2026-03-08T18:12:58.240000",
        "queue_exit_ts": "2026-03-08T18:14:02.880000",
        "wait_seconds": 65,
        "queue_position_at_join": 4,
        "abandoned": True,
    }

    response = await async_client.post(
        "/events/ingest", json={"events": [sample_queue]}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] == 1
    assert data["rejected"] == 0
