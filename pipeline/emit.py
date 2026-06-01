import json
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class EventEmitter:
    def __init__(self, store_id: str, output_dir: str):
        self.store_id = store_id
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Session state to track sequences
        self._session_seqs: Dict[str, int] = {}

        # We will create a new JSONL file for each run or we can append to a store-specific file
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_file = (
            self.output_dir / f"events_{self.store_id}_{timestamp_str}.jsonl"
        )
        logger.info(f"EventEmitter initialized. Outputting to {self.output_file}")

    def emit(
        self,
        camera_id: str,
        visitor_id: str,
        event_type: str,
        timestamp: datetime,
        confidence: float,
        zone_id: Optional[str] = None,
        dwell_ms: int = 0,
        is_staff: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Emit a structured event matching the required schema."""

        if visitor_id not in self._session_seqs:
            self._session_seqs[visitor_id] = 1
        else:
            self._session_seqs[visitor_id] += 1

        session_seq = self._session_seqs[visitor_id]

        meta = metadata or {}
        meta["session_seq"] = session_seq
        if zone_id:
            meta["sku_zone"] = zone_id

        event = {
            "event_id": str(uuid.uuid4()),
            "store_id": self.store_id,
            "camera_id": camera_id,
            "visitor_id": visitor_id,
            "event_type": event_type,
            "timestamp": timestamp.isoformat(),
            "zone_id": zone_id,
            "dwell_ms": dwell_ms,
            "is_staff": is_staff,
            "confidence": round(confidence, 4),
            "metadata": meta,
        }

        with open(self.output_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

        # Also print critical events for debugging
        if event_type in ["ENTRY", "EXIT", "BILLING_QUEUE_JOIN"]:
            logger.info(f"Emitted {event_type} for {visitor_id} at {camera_id}")

    def calculate_timestamp(
        self, clip_start_time: datetime, frame_number: int, fps: float
    ) -> datetime:
        """Helper to compute timestamp from frame number."""
        offset_seconds = frame_number / fps
        return clip_start_time + timedelta(seconds=offset_seconds)
