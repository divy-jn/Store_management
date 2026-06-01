"""
Tests for /stores/{store_id}/heatmap.

# PROMPT: "Generate route tests for the heatmap endpoint with a fake DB. Cover
# normalized zone scores, low/high data confidence, empty stores, and graceful
# 503 behavior when the database is unavailable."
# CHANGES MADE: Used simple async fake rows to validate normalization and
# response-shape requirements from the PDF spec.
"""

from __future__ import annotations

import pytest

from app import heatmap


class HeatmapFakeConnection:
    def __init__(self, total_sessions: int, rows):
        self.total_sessions = total_sessions
        self.rows = rows

    async def fetchval(self, query, store_id):
        return self.total_sessions

    async def fetch(self, query, store_id):
        return self.rows


class HeatmapFakeDB:
    def __init__(self, total_sessions: int = 0, rows=None):
        self.conn = HeatmapFakeConnection(total_sessions, rows or [])

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
async def test_heatmap_normalizes_scores_and_confidence(async_client, monkeypatch):
    monkeypatch.setattr(
        heatmap,
        "db",
        HeatmapFakeDB(
            30,
            [
                {"zone_id": "SKINCARE", "visit_count": 20, "avg_dwell_ms": 30000.0},
                {"zone_id": "MAKEUP", "visit_count": 10, "avg_dwell_ms": None},
            ],
        ),
    )

    response = await async_client.get("/stores/ST1008/heatmap")

    assert response.status_code == 200
    data = response.json()
    assert data["total_sessions"] == 30
    assert data["zones"][0]["normalized_score"] == 100.0
    assert data["zones"][0]["data_confidence"] == "high"
    assert data["zones"][1]["normalized_score"] == 50.0
    assert data["zones"][1]["data_confidence"] == "low"


@pytest.mark.asyncio
async def test_heatmap_empty_store(async_client, monkeypatch):
    monkeypatch.setattr(heatmap, "db", HeatmapFakeDB())

    response = await async_client.get("/stores/ST1008/heatmap")

    assert response.status_code == 200
    assert response.json()["zones"] == []


@pytest.mark.asyncio
async def test_heatmap_returns_503_when_database_unavailable(async_client, monkeypatch):
    monkeypatch.setattr(heatmap, "db", BrokenDB())

    response = await async_client.get("/stores/ST1008/heatmap")

    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "service_unavailable"
