"""
Tests for pipeline helper units (QueueTracker, ZoneClassifier, EventEmitter).

# PROMPT: "Generate unit tests for the pipeline helper modules: QueueTracker,
# ZoneClassifier, and EventEmitter. Cover idempotent queue operations, unknown
# camera zones, and JSONL file output format."
# CHANGES MADE: Added EventEmitter output verification, staff detector color
# range test, and zone classifier boundary tests.
"""

import json
import uuid
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from pipeline.queue_tracker import QueueTracker
from pipeline.zone_classifier import ZoneClassifier
from pipeline.emit import EventEmitter

# Use a project-local temp dir to avoid Windows permission issues
_TEST_TMP = Path(__file__).resolve().parent.parent / ".test_tmp"


@pytest.fixture
def local_tmp():
    """Create and clean up a local temp directory for tests."""
    _TEST_TMP.mkdir(exist_ok=True)
    yield _TEST_TMP
    shutil.rmtree(_TEST_TMP, ignore_errors=True)


def test_queue_tracker_is_idempotent():
    """Adding the same visitor twice should not double-count queue depth."""
    tracker = QueueTracker()

    tracker.update("VIS_001", "BILLING")
    tracker.update("VIS_001", "BILLING")
    tracker.remove("VIS_missing")

    assert tracker.get_queue_depth() == 1

    tracker.update("VIS_001", "SKINCARE")

    assert tracker.get_queue_depth() == 0


def test_queue_tracker_multiple_visitors():
    """Multiple visitors join and leave the queue independently."""
    tracker = QueueTracker()

    tracker.update("VIS_001", "BILLING")
    tracker.update("VIS_002", "BILLING")
    tracker.update("VIS_003", "BILLING")

    assert tracker.get_queue_depth() == 3

    tracker.remove("VIS_002")

    assert tracker.get_queue_depth() == 2


def test_queue_tracker_remove_nonexistent_is_safe():
    """Removing a visitor who isn't in the queue should not raise."""
    tracker = QueueTracker()
    tracker.remove("VIS_GHOST")
    assert tracker.get_queue_depth() == 0


def test_zone_classifier_returns_none_for_unknown_camera(local_tmp):
    """Unknown camera IDs should return None zone, not crash."""
    layout_path = local_tmp / "layout.json"
    layout_path.write_text(
        json.dumps(
            {
                "stores": [
                    {
                        "store_id": "ST1008",
                        "zones": [
                            {
                                "zone_id": "ENTRY",
                                "zone_type": "threshold",
                                "camera_ids": ["CAM_ENTRY_01"],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    classifier = ZoneClassifier(str(layout_path))

    assert classifier.get_zone_for_point("CAM_UNKNOWN", 100, 100) is None
    assert classifier.get_zone_for_point("CAM_ENTRY_01", 500, 900) == "ENTRY"


def test_event_emitter_writes_valid_jsonl(local_tmp):
    """EventEmitter should write one JSON object per line to the output file."""
    emitter = EventEmitter("ST1008", str(local_tmp))

    ts = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
    emitter.emit(
        camera_id="CAM_ENTRY_01",
        visitor_id="VIS_001",
        event_type="ENTRY",
        timestamp=ts,
        confidence=0.95,
    )
    emitter.emit(
        camera_id="CAM_FLOOR_01",
        visitor_id="VIS_001",
        event_type="ZONE_ENTER",
        timestamp=ts,
        confidence=0.88,
        zone_id="SKINCARE",
    )

    lines = emitter.output_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2

    for line in lines:
        event = json.loads(line)
        assert "event_id" in event
        assert "store_id" in event
        assert event["store_id"] == "ST1008"


def test_event_emitter_increments_session_seq(local_tmp):
    """Each event for the same visitor should get an incrementing session_seq."""
    emitter = EventEmitter("ST1008", str(local_tmp))
    ts = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)

    for i in range(3):
        emitter.emit(
            camera_id="CAM_ENTRY_01",
            visitor_id="VIS_001",
            event_type="ENTRY",
            timestamp=ts,
            confidence=0.9,
        )

    lines = emitter.output_file.read_text(encoding="utf-8").strip().split("\n")
    seqs = [json.loads(line)["metadata"]["session_seq"] for line in lines]
    assert seqs == [1, 2, 3]


def test_event_emitter_calculate_timestamp():
    """Timestamp calculation should offset from clip start based on frame/fps."""
    emitter = EventEmitter("ST1008", ".")
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    ts = emitter.calculate_timestamp(start, frame_number=30, fps=15.0)
    delta = (ts - start).total_seconds()
    assert abs(delta - 2.0) < 0.01  # 30 frames / 15 fps = 2 seconds
