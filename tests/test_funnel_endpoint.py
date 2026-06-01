"""
Tests for the /stores/{store_id}/funnel endpoint.

# PROMPT: "Generate FastAPI route tests for the funnel endpoint using a fake
# database connection. Cover normal funnel counts, re-entry/session de-duping,
# and database-unavailable graceful degradation."
# CHANGES MADE: Implemented query-pattern fake results to exercise the real
# endpoint and its response model without requiring PostgreSQL.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app import funnel


class FunnelFakeConnection:
    def __init__(self, values: dict[str, int]):
        self.values = values

    async def fetchval(self, query, store_id):
        if "event_type IN ('ENTRY', 'REENTRY')" in query:
            return self.values.get("entry", 0)
        if "zone_id NOT IN ('ENTRY', 'BILLING', 'INTERNAL', 'STORAGE')" in query:
            return self.values.get("zone_visit", 0)
        if "BILLING_QUEUE_JOIN" in query and "JOIN pos_transactions" not in query:
            return self.values.get("billing", 0)
        if "JOIN pos_transactions" in query:
            return self.values.get("purchase", 0)
        raise AssertionError(f"Unexpected funnel query: {query}")


class FunnelFakeDB:
    def __init__(self, values: dict[str, int]):
        self.conn = FunnelFakeConnection(values)

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
async def test_funnel_endpoint_returns_session_based_counts(
    async_client: AsyncClient,
    monkeypatch,
):
    monkeypatch.setattr(
        funnel,
        "db",
        FunnelFakeDB({"entry": 10, "zone_visit": 8, "billing": 4, "purchase": 2}),
    )

    response = await async_client.get("/stores/ST1008/funnel")

    assert response.status_code == 200
    data = response.json()
    assert data["total_sessions"] == 10
    assert [stage["count"] for stage in data["stages"]] == [10, 8, 4, 2]
    assert data["stages"][-1]["percentage"] == 20.0


@pytest.mark.asyncio
async def test_funnel_endpoint_handles_empty_store(async_client: AsyncClient, monkeypatch):
    monkeypatch.setattr(funnel, "db", FunnelFakeDB({}))

    response = await async_client.get("/stores/ST1008/funnel")

    assert response.status_code == 200
    data = response.json()
    assert data["total_sessions"] == 0
    assert all(stage["percentage"] == 0 for stage in data["stages"])


@pytest.mark.asyncio
async def test_funnel_endpoint_returns_503_when_database_unavailable(
    async_client: AsyncClient,
    monkeypatch,
):
    monkeypatch.setattr(funnel, "db", BrokenDB())

    response = await async_client.get("/stores/ST1008/funnel")

    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "service_unavailable"
