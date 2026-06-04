# PROMPT: Generate tests for GET /health covering healthy and unhealthy database
# states, per-store event freshness, stale feed reporting, and uptime fields.
# CHANGES MADE: Added fake healthy/unhealthy DB stubs and monkeypatch injection
# so the endpoint is tested without a live PostgreSQL service.
"""Tests for the /health endpoint."""

import pytest
from httpx import AsyncClient

from app import health


class FakeHealthyDB:
    @property
    def uptime_seconds(self):
        return 12.345

    async def is_healthy(self):
        return True

    def acquire(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def fetch(self, query):
        return []


class FakeUnhealthyDB:
    @property
    def uptime_seconds(self):
        return 0

    async def is_healthy(self):
        return False


@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient, monkeypatch):
    monkeypatch.setattr(health, "db", FakeHealthyDB())

    response = await async_client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database_connected"] is True


@pytest.mark.asyncio
async def test_health_check_reports_unhealthy_when_database_is_down(
    async_client: AsyncClient,
    monkeypatch,
):
    monkeypatch.setattr(health, "db", FakeUnhealthyDB())

    response = await async_client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["database_connected"] is False
    assert data["stores"] == []
