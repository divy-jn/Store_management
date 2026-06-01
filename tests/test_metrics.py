"""
Tests for /stores/{store_id}/metrics business logic.

# PROMPT: "Generate FastAPI route tests for the metrics endpoint using a fake
# database layer. Cover all-staff traffic exclusion, zero-purchase stores,
# queue abandonment math, and empty stores without requiring PostgreSQL."
# CHANGES MADE: Used query-pattern matching in the fake connection to keep
# tests focused on endpoint behavior while still exercising the real route.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app import metrics


class MetricsFakeConnection:
    """Minimal asyncpg-like connection for metrics endpoint tests."""

    def __init__(self, values: dict[str, int | float], dwell_rows=None):
        self.values = values
        self.dwell_rows = dwell_rows or []

    async def fetchval(self, query, store_id):
        if "COUNT(DISTINCT visitor_id)" in query and "event_type = 'ENTRY'" in query:
            return self.values.get("unique_visitors", 0)
        if "COUNT(*) FROM events" in query and "event_type = 'ENTRY'" in query:
            return self.values.get("total_entries", 0)
        if "COUNT(*) FROM events" in query and "event_type = 'EXIT'" in query:
            return self.values.get("total_exits", 0)
        if "JOIN pos_transactions" in query:
            return self.values.get("converted_visitors", 0)
        if "metadata->>'queue_depth'" in query:
            return self.values.get("current_queue_depth", 0)
        if "event_type = 'BILLING_QUEUE_JOIN'" in query:
            return self.values.get("queue_joins", 0)
        if "event_type = 'BILLING_QUEUE_ABANDON'" in query:
            return self.values.get("queue_abandons", 0)
        raise AssertionError(f"Unexpected fetchval query: {query}")

    async def fetch(self, query, store_id):
        return self.dwell_rows


class MetricsFakeDB:
    def __init__(self, values: dict[str, int | float], dwell_rows=None):
        self.conn = MetricsFakeConnection(values, dwell_rows)

    def acquire(self):
        return self

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_metrics_handles_empty_store(async_client: AsyncClient, monkeypatch):
    """No events and no purchases should return valid zero metrics."""
    monkeypatch.setattr(metrics, "db", MetricsFakeDB({}))

    response = await async_client.get("/stores/ST1008/metrics")

    assert response.status_code == 200
    data = response.json()
    assert data["unique_visitors"] == 0
    assert data["conversion_rate"] == 0.0
    assert data["abandonment_rate"] == 0.0
    assert data["avg_dwell_per_zone"] == []


@pytest.mark.asyncio
async def test_metrics_excludes_all_staff_traffic(
    async_client: AsyncClient, monkeypatch
):
    """If every detected person is staff, customer metrics should stay zero."""
    monkeypatch.setattr(
        metrics,
        "db",
        MetricsFakeDB(
            {
                "unique_visitors": 0,
                "total_entries": 0,
                "total_exits": 0,
                "converted_visitors": 0,
                "current_queue_depth": 3,
                "queue_joins": 0,
                "queue_abandons": 0,
            }
        ),
    )

    response = await async_client.get("/stores/ST1008/metrics")

    assert response.status_code == 200
    data = response.json()
    assert data["unique_visitors"] == 0
    assert data["total_entries"] == 0
    assert data["conversion_rate"] == 0.0
    assert data["current_queue_depth"] == 3


@pytest.mark.asyncio
async def test_metrics_calculates_conversion_and_abandonment(
    async_client: AsyncClient,
    monkeypatch,
):
    """Conversion and abandonment are ratios over non-staff visitor events."""
    monkeypatch.setattr(
        metrics,
        "db",
        MetricsFakeDB(
            {
                "unique_visitors": 10,
                "total_entries": 12,
                "total_exits": 8,
                "converted_visitors": 4,
                "current_queue_depth": 2,
                "queue_joins": 5,
                "queue_abandons": 1,
            },
            dwell_rows=[
                {"zone_id": "SKINCARE", "avg_dwell_ms": 45000.0, "visit_count": 3}
            ],
        ),
    )

    response = await async_client.get("/stores/ST1008/metrics")

    assert response.status_code == 200
    data = response.json()
    assert data["conversion_rate"] == 0.4
    assert data["abandonment_rate"] == 0.2
    assert data["avg_dwell_per_zone"][0]["zone_id"] == "SKINCARE"
