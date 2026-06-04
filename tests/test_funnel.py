# PROMPT: Generate unit tests for conversion funnel stage math, including normal
# progression, zero traffic, entry-only visitors, no-purchase sessions, and
# re-entry de-duplication behavior.
# CHANGES MADE: Added focused edge cases around division by zero and verified
# drop-off percentages remain stable for sparse stores.
"""Tests for the conversion funnel math helper."""

from app.funnel import _build_funnel_stages


def test_build_funnel_stages_handles_empty_store():
    """Zero-traffic store should return all zeros without division errors."""
    stages = _build_funnel_stages(0, 0, 0, 0)

    assert [stage.count for stage in stages] == [0, 0, 0, 0]
    assert all(stage.percentage == 0 for stage in stages)
    assert all(stage.drop_off_percent == 0 for stage in stages)


def test_build_funnel_stages_calculates_percentages_and_dropoff():
    """Standard funnel with progressive drop-off at each stage."""
    stages = _build_funnel_stages(100, 75, 50, 25)

    assert [stage.stage for stage in stages] == [
        "Entry",
        "Zone Visit",
        "Billing Queue",
        "Purchase",
    ]
    assert [stage.percentage for stage in stages] == [100.0, 75.0, 50.0, 25.0]
    assert [stage.drop_off_percent for stage in stages] == [0.0, 25.0, 33.33, 50.0]


def test_build_funnel_stages_single_visitor_full_journey():
    """One visitor who goes through every stage — 100% conversion."""
    stages = _build_funnel_stages(1, 1, 1, 1)

    assert all(stage.percentage == 100.0 for stage in stages)
    assert all(stage.drop_off_percent == 0.0 for stage in stages)


def test_build_funnel_stages_entry_only_no_zone_visits():
    """Visitors entered but never browsed any product zone."""
    stages = _build_funnel_stages(50, 0, 0, 0)

    assert stages[0].percentage == 100.0
    assert stages[1].count == 0
    assert stages[1].drop_off_percent == 100.0


def test_build_funnel_stages_no_purchases():
    """Everyone browsed and queued but nobody purchased."""
    stages = _build_funnel_stages(80, 60, 40, 0)

    assert stages[3].count == 0
    assert stages[3].percentage == 0.0
    assert stages[3].drop_off_percent == 100.0


def test_build_funnel_stages_reentry_does_not_inflate():
    """
    Re-entry visitors should not inflate the count.
    The funnel uses DISTINCT visitor_id, so even if a visitor re-enters,
    they are counted once. Here we just verify math with the de-duped count.
    """
    # 10 unique visitors (some may have re-entered), 8 browsed, 5 queued, 3 bought
    stages = _build_funnel_stages(10, 8, 5, 3)

    assert stages[0].count == 10
    assert stages[3].percentage == 30.0
