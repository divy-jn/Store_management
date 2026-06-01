"""
Demo Replay Endpoint for the Dashboard.
Clears the database and slowly replays events to simulate a live store environment.
"""

import asyncio
import glob
import json
import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.database import db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Demo"])


async def _run_demo_replay():
    """Background task to stream events slowly for demo purposes."""
    await asyncio.sleep(2)  # Give frontend time to reset
    
    events_dir = Path("output/events")
    if not events_dir.exists():
        logger.error("Demo replay failed: output/events directory not found")
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
    
    logger.info(f"Starting live demo replay of {len(all_events)} events...")
    
    # Send in small batches to make the dashboard counters tick smoothly
    batch_size = 20
    async with httpx.AsyncClient() as client:
        for i in range(0, len(all_events), batch_size):
            batch = all_events[i : i + batch_size]
            try:
                await client.post(
                    "http://localhost:8000/events/ingest", 
                    json={"events": batch}
                )
            except Exception as e:
                logger.error(f"Replay batch failed: {e}")
            
            # Wait a short duration between batches to simulate real-time
            await asyncio.sleep(0.3)
            
    logger.info("Live demo replay events finished. Running POS simulation...")
    
    # Run the POS simulation script automatically at the end to populate the funnel
    import subprocess
    import sys
    try:
        subprocess.run([sys.executable, "scripts/simulate_pos.py"], check=True)
        logger.info("Demo replay complete!")
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
