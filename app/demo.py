"""
Demo Replay Endpoint for the Dashboard.
Clears the database and slowly replays events to simulate a live store environment.
"""

import asyncio
import json
import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.database import db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Demo"])

# Global state for fast-forwarding the demo
demo_skip_batches = 0


async def _run_demo_replay():
    """Background task to stream events slowly for demo purposes."""
    global demo_skip_batches
    demo_skip_batches = 0

    await asyncio.sleep(2)  # Give frontend time to reset

    events_dir = Path("output/events")
    fallback_dirs = [
        Path("Project details/New folder"),
        Path("output"),
    ]
    if not events_dir.exists() or not list(events_dir.glob("*.jsonl")):
        for fallback in fallback_dirs:
            if fallback.exists() and list(fallback.glob("*.jsonl")):
                events_dir = fallback
                break

    if not events_dir.exists():
        logger.error("Demo replay failed: no events directory found")
        return

    jsonl_files = sorted(events_dir.glob("*.jsonl"))
    if not jsonl_files:
        logger.error("Demo replay failed: no JSONL files found")
        return

    all_events = []
    for f in jsonl_files:
        with open(f, "r") as file:
            for line in file:
                if line.strip():
                    all_events.append(json.loads(line))

    # Sort events by timestamp so the replay is chronological
    all_events.sort(key=lambda x: x["timestamp"])

    if all_events:
        # Shift all timestamps to truly simulate "Live" right now
        from datetime import datetime, timezone

        def get_ts(ev):
            return ev.get("timestamp") or ev.get("event_timestamp") or ev.get("event_time") or ev.get("queue_join_ts") or ev.get("queue_exit_ts")

        def set_ts(ev, val):
            if "timestamp" in ev: ev["timestamp"] = val
            if "event_timestamp" in ev: ev["event_timestamp"] = val
            if "event_time" in ev: ev["event_time"] = val
            if "queue_join_ts" in ev: ev["queue_join_ts"] = val
            if "queue_served_ts" in ev: ev["queue_served_ts"] = val
            if "queue_exit_ts" in ev: ev["queue_exit_ts"] = val

        def parse_dt(ts_str):
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt

        first_ts_str = get_ts(all_events[0])
        if first_ts_str:
            first_dt = parse_dt(first_ts_str)
            now_dt = datetime.now(timezone.utc)
            time_offset = now_dt - first_dt

            for event in all_events:
                ts_str = get_ts(event)
                if ts_str:
                    dt = parse_dt(ts_str)
                    new_dt = dt + time_offset
                    set_ts(event, new_dt.isoformat())

    logger.info(f"Starting live demo replay of {len(all_events)} events...")

    # Send in small batches to make the dashboard counters tick smoothly
    batch_size = 20
    async with httpx.AsyncClient() as client:
        for i in range(0, len(all_events), batch_size):
            batch = all_events[i : i + batch_size]
            try:
                await client.post(
                    "http://localhost:8000/events/ingest", json={"events": batch}
                )
            except Exception as e:
                logger.error(f"Replay batch failed: {e}")

            # Wait a short duration between batches to simulate real-time
            if demo_skip_batches > 0:
                demo_skip_batches -= 1
            else:
                await asyncio.sleep(0.3)

    logger.info("Live demo replay events finished. Running POS simulation...")

    # Run the POS simulation script automatically at the end to populate the funnel
    import subprocess
    import sys

    try:
        subprocess.run([sys.executable, "scripts/simulate_pos.py"], check=True)
        logger.info("Demo replay complete!")

        # Broadcast completion to frontend
        from app.websocket import _active_connections

        for ws in list(_active_connections):
            try:
                await ws.send_json({"type": "demo_completed"})
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Failed to run simulate_pos.py: {e}")


@router.post("/system/demo-replay")
async def start_demo_replay(background_tasks: BackgroundTasks):
    """
    Clears the database and triggers a background replay of all CCTV events.
    Used exclusively for presentation wow-factor.
    """
    try:
        async with db.acquire() as conn:
            # Clear all data safely
            await conn.execute("TRUNCATE TABLE events, pos_transactions;")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Start the slow streaming background task
    background_tasks.add_task(_run_demo_replay)

    return {"status": "success", "message": "Database cleared. Live replay started."}


@router.post("/system/demo-skip")
async def skip_demo_time():
    """
    Fast-forwards the background simulation by roughly 10 seconds.
    10 seconds / 0.3s sleep per batch = ~33 batches to skip.
    """
    global demo_skip_batches
    demo_skip_batches += 33
    return {"status": "success", "message": "Skipped 10 seconds of simulation."}
