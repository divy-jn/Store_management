import argparse
import json
import logging
from pathlib import Path
import httpx
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def ingest_file(file_path: Path, api_url: str):
    events = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            events.append(json.loads(line))
            
    if not events:
        return
        
    logger.info(f"Ingesting {len(events)} events from {file_path.name}")
    
    # Ingest in batches of 500
    batch_size = 500
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def post_batch(client: httpx.AsyncClient, payload: dict, api_url: str):
        response = await client.post(f"{api_url}/events/ingest", json=payload)
        response.raise_for_status()
        return response

    async with httpx.AsyncClient(timeout=30.0) as client:
        for i in range(0, len(events), batch_size):
            batch = events[i:i + batch_size]
            payload = {"events": batch}
            
            try:
                response = await post_batch(client, payload, api_url)
                data = response.json()
                logger.info(f"Batch {i//batch_size + 1}: Accepted {data['accepted']}, Rejected {data['rejected']}, Duplicates {data['duplicates']}")
            except Exception as e:
                logger.error(f"Failed to ingest batch {i//batch_size + 1} after retries: {e}")

async def main():
    parser = argparse.ArgumentParser(description="Replay JSONL events to Store Intelligence API")
    parser.add_argument("--events-dir", required=True, help="Directory containing JSONL event files")
    parser.add_argument("--api-url", default="http://localhost:8000", help="URL of the Store Intelligence API")
    args = parser.parse_args()
    
    events_dir = Path(args.events_dir)
    if not events_dir.exists():
        logger.error(f"Events directory not found: {events_dir}")
        return
        
    files = list(events_dir.glob("*.jsonl"))
    logger.info(f"Found {len(files)} JSONL files to replay")
    
    for file_path in files:
        await ingest_file(file_path, args.api_url)

if __name__ == "__main__":
    asyncio.run(main())
