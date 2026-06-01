"""
Tests for anomaly detection helpers and endpoint behavior.

# PROMPT: "Generate tests for anomaly detection: queue spike, conversion drop,
# dead zone, stale feed, empty anomaly list, and 503 graceful degradation. Use
# fake async DB connections instead of PostgreSQL."
# CHANGES MADE: Tested helper functions directly for focused branch coverage
# and added route-level checks for empty responses and database failures.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import anomalies
from app.models import AnomalyType


class AnomalyFakeConnection:
    def __init__(self):
        self.now = datetime.now(timezone.utc)

    async def fetchval(self, query, *args):
        if "ORDER BY timestamp DESC LIMIT 1" in query:
            return 9
        if "AVG(COALESCE" in query:
            return 3
        if "event_type = 'ENTRY'" in query:
            return 10
        if "JOIN pos_transactions" in query:
            return 1
        if "SELECT MAX(timestamp) FROM events" in query and "zone_id = $2" in query:
            return self.now - timedelta(minutes=45)
        return 0

    async def fetch(self, query, *args):
        if "SELECT DISTINCT zone_id" in query:
            return [{"zone_id": "SKINCARE"}]
        if "GROUP BY camera_id" in query:
            return [
                {
                    "camera_id": "CAM_ENTRY_01",
                    "last_event": self.now - timedelta(minutes=20),
                }
            ]
        return []


class EmptyAnomalyConnection:
    async def fetchval(self, query, *args):
        return 0

    async def fetch(self, query, *args):
        return []


class AnomalyFakeDB:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return self

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class BrokenDB:
    def acquire(self):
        raise RuntimeError("Database not connected")


@pytest.mark.asyncio
async def test_anomaly_helpers_detect_expected_cases():
    conn = AnomalyFakeConnection()
    found = []

    await anomalies._check_queue_spike(conn, "ST1008", found)
    await anomalies._check_conversion_drop(conn, "ST1008", found)
    await anomalies._check_dead_zones(conn, "ST1008", found)
    await anomalies._check_stale_feeds(conn, "ST1008", found)

    anomaly_types = {item.anomaly_type for item in found}
    assert AnomalyType.BILLING_QUEUE_SPIKE in anomaly_types
    assert AnomalyType.CONVERSION_DROP in anomaly_types
    assert AnomalyType.DEAD_ZONE in anomaly_types
    assert AnomalyType.STALE_FEED in anomaly_types


@pytest.mark.asyncio
async def test_anomalies_endpoint_empty(async_client, monkeypatch):
    monkeypatch.setattr(anomalies, "db", AnomalyFakeDB(EmptyAnomalyConnection()))

    response = await async_client.get("/stores/ST1008/anomalies")

    assert response.status_code == 200
    data = response.json()
    assert data["active_count"] == 0
    assert data["anomalies"] == []


@pytest.mark.asyncio
async def test_anomalies_returns_503_when_database_unavailable(async_client, monkeypatch):
    monkeypatch.setattr(anomalies, "db", BrokenDB())

    response = await async_client.get("/stores/ST1008/anomalies")

    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "service_unavailable"
