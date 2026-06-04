# PROMPT: Generate focused unit tests for database health helpers and POS loader
# edge cases that do not require a live PostgreSQL service.
# CHANGES MADE: Added direct coverage for disconnected database behavior,
# uptime calculation, default POS CSV selection, and missing-file loader fallback.
"""Tests for database and POS loader utility behavior."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.database import Database
from app import pos_loader


def test_database_uptime_defaults_to_zero():
    """A database object that has not connected should report zero uptime."""
    database = Database()

    assert database.uptime_seconds == 0.0


def test_database_uptime_after_start_time():
    """Uptime should be measured from the stored startup timestamp."""
    database = Database()
    database._start_time = time.time() - 5

    assert database.uptime_seconds >= 5


@pytest.mark.asyncio
async def test_database_health_false_without_pool():
    """Disconnected databases should be reported as unhealthy."""
    database = Database()

    assert await database.is_healthy() is False


@pytest.mark.asyncio
async def test_database_acquire_raises_without_pool():
    """Acquiring a connection before startup should fail clearly."""
    database = Database()

    with pytest.raises(RuntimeError, match="Database not connected"):
        async with database.acquire():
            pass


def test_default_pos_csv_path_prefers_first_existing_candidate(monkeypatch):
    """The loader should choose the first configured POS CSV that exists."""
    test_dir = Path(__file__).parent / "_test_tmp_pos"
    test_dir.mkdir(exist_ok=True)
    try:
        preferred = test_dir / "preferred.csv"
        fallback = test_dir / "fallback.csv"
        fallback.write_text("store_id\nST1008\n", encoding="utf-8")
        preferred.write_text("store_id\nST1009\n", encoding="utf-8")
        monkeypatch.setattr(pos_loader, "POS_CSV_CANDIDATES", [preferred, fallback])

        assert pos_loader._default_pos_csv_path() == preferred
    finally:
        import shutil
        shutil.rmtree(test_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_load_pos_data_missing_file_returns_zero():
    """Missing POS files should not crash startup."""
    missing_path = Path(__file__).parent / "_nonexistent_pos_file.csv"

    assert await pos_loader.load_pos_data(missing_path) == 0

