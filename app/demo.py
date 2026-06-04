"""
Demo Replay Endpoint for the Dashboard.
Clears the database and slowly replays events to simulate a live store environment.
Inserts directly into PostgreSQL (no self-HTTP) to avoid async deadlocks.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.database import db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Demo"])

# Global state for fast-forwarding the demo
demo_skip_batches = 0


def _get_ts(ev):
    """Extract the best available timestamp from any event format."""
    return (
        ev.get("timestamp")
        or ev.get("event_timestamp")
        or ev.get("event_time")
        or ev.get("queue_join_ts")
        or ev.get("queue_exit_ts")
        or ""
    )


def _parse_dt(ts_str):
    """Parse an ISO timestamp string into a timezone-aware datetime."""
    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _normalize_event(raw, target_store_id=None):
    """Convert any event format into canonical DB-insertable fields."""
    et = str(raw.get("event_type", "")).upper()

    # Map sample-schema event types to our internal types
    type_map = {
        "ENTRY": "ENTRY",
        "EXIT": "EXIT",
        "ZONE_ENTERED": "ZONE_ENTER",
        "ZONE_EXITED": "ZONE_EXIT",
        "ZONE_ENTER": "ZONE_ENTER",
        "ZONE_EXIT": "ZONE_EXIT",
        "ZONE_DWELL": "ZONE_DWELL",
        "BILLING_QUEUE_JOIN": "BILLING_QUEUE_JOIN",
        "BILLING_QUEUE_ABANDON": "BILLING_QUEUE_ABANDON",
        "QUEUE_COMPLETED": "BILLING_QUEUE_JOIN",
        "QUEUE_ABANDONED": "BILLING_QUEUE_ABANDON",
        "REENTRY": "REENTRY",
    }
    event_type = type_map.get(et, et)
    if not event_type:
        return None

    store_id = target_store_id or raw.get("store_id") or raw.get("store_code") or "UNKNOWN"
    visitor_id = raw.get("visitor_id") or raw.get("id_token") or f"VIS_{raw.get('track_id', 'UNK')}"
    ts_str = _get_ts(raw)
    if not ts_str:
        return None

    metadata = raw.get("metadata", {})
    if isinstance(metadata, dict):
        metadata_json = json.dumps(metadata)
    else:
        metadata_json = json.dumps({})

    return {
        "event_id": raw.get("event_id") or raw.get("queue_event_id") or str(uuid.uuid4()),
        "store_id": store_id,
        "camera_id": raw.get("camera_id", "UNKNOWN"),
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp": _parse_dt(ts_str),
        "zone_id": raw.get("zone_id"),
        "dwell_ms": int(raw.get("dwell_ms", 0)),
        "is_staff": bool(raw.get("is_staff", False)),
        "confidence": float(raw.get("confidence", 0.9)),
        "metadata": metadata_json,
    }


async def _run_demo_replay(target_store_id: str = None):
    """Background task to stream events slowly for demo purposes."""
    global demo_skip_batches
    demo_skip_batches = 0

    await asyncio.sleep(1)

    try:
        # --- Find event files ---
        events_dir = None
        if db.settings.events_jsonl_path:
            events_dir = Path(db.settings.events_jsonl_path)
        else:
            candidate = Path("output/events")
            if candidate.exists() and any(
                f.stat().st_size > 0 for f in candidate.glob("*.jsonl")
            ):
                events_dir = candidate

        root_events = Path("events.jsonl")
        jsonl_files = []

        if events_dir and events_dir.exists():
            jsonl_files = [
                f
                for f in sorted(events_dir.glob("*.jsonl"))
                if f.stat().st_size > 0
            ]

        if not jsonl_files and root_events.exists():
            jsonl_files = [root_events]

        if not jsonl_files:
            logger.error("Demo replay failed: no JSONL files found anywhere")
            return

        # --- Load all events ---
        all_events = []
        for f in jsonl_files:
            with open(f, "r") as fh:
                for line in fh:
                    if line.strip():
                        try:
                            all_events.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue

        if not all_events:
            logger.error("Demo replay failed: loaded 0 events from files")
            return

        # Sort chronologically
        all_events.sort(key=lambda x: _get_ts(x))

        # Rewrite store_id if requested
        if target_store_id:
            for ev in all_events:
                ev["store_id"] = target_store_id

        # Shift timestamps to NOW so they appear as live data
        first_ts_str = _get_ts(all_events[0])
        if first_ts_str:
            first_dt = _parse_dt(first_ts_str)
            now_dt = datetime.now(timezone.utc)
            time_offset = now_dt - first_dt

            for ev in all_events:
                ts_str = _get_ts(ev)
                if ts_str:
                    new_dt = _parse_dt(ts_str) + time_offset
                    new_iso = new_dt.isoformat()
                    if "timestamp" in ev:
                        ev["timestamp"] = new_iso
                    if "event_timestamp" in ev:
                        ev["event_timestamp"] = new_iso
                    if "event_time" in ev:
                        ev["event_time"] = new_iso

        logger.info(f"Demo replay: loaded {len(all_events)} events, inserting directly into DB...")

        # --- Insert directly into DB in batches ---
        batch_size = 20
        accepted = 0
        rejected = 0

        for i in range(0, len(all_events), batch_size):
            batch = all_events[i : i + batch_size]

            try:
                async with db.acquire() as conn:
                    for raw in batch:
                        norm = _normalize_event(raw, target_store_id)
                        if not norm:
                            rejected += 1
                            continue

                        try:
                            result = await conn.execute(
                                """
                                INSERT INTO events (
                                    event_id, store_id, camera_id, visitor_id,
                                    event_type, timestamp, zone_id, dwell_ms,
                                    is_staff, confidence, metadata
                                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                                ON CONFLICT (event_id) DO NOTHING
                                """,
                                norm["event_id"],
                                norm["store_id"],
                                norm["camera_id"],
                                norm["visitor_id"],
                                norm["event_type"],
                                norm["timestamp"],
                                norm["zone_id"],
                                norm["dwell_ms"],
                                norm["is_staff"],
                                norm["confidence"],
                                norm["metadata"],
                            )
                            if result == "INSERT 0 1":
                                accepted += 1
                        except Exception as e:
                            rejected += 1
                            if accepted == 0:
                                logger.error(f"Insert error: {e}")
            except Exception as e:
                logger.error(f"DB connection error during replay: {e}")

            # Pace the replay so the dashboard ticks
            if demo_skip_batches > 0:
                demo_skip_batches -= 1
            else:
                await asyncio.sleep(0.3)

        logger.info(f"Demo replay: inserted {accepted} events, rejected {rejected}")

        # --- Run POS simulation ---
        import subprocess
        import sys

        try:
            subprocess.run([sys.executable, "scripts/simulate_pos.py"], check=True)
            logger.info("Demo replay complete (POS simulation done)")
        except Exception as e:
            logger.warning(f"POS simulation skipped: {e}")

        # --- Broadcast completion to dashboard ---
        from app.websocket import _active_connections

        for ws in list(_active_connections):
            try:
                await ws.send_json({"type": "demo_completed"})
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Demo replay crashed: {e}", exc_info=True)


@router.post("/system/demo-replay")
async def start_demo_replay(background_tasks: BackgroundTasks, store_id: str = None):
    """
    Clears the database and triggers a background replay of all CCTV events.
    """
    try:
        async with db.acquire() as conn:
            await conn.execute("TRUNCATE TABLE events, pos_transactions;")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    background_tasks.add_task(_run_demo_replay, store_id)

    return {"status": "success", "message": "Database cleared. Live replay started."}


@router.post("/system/demo-skip")
async def skip_demo_time():
    """Fast-forwards the background simulation by roughly 10 seconds."""
    global demo_skip_batches
    demo_skip_batches += 33
    return {"status": "success", "message": "Skipped 10 seconds of simulation."}
