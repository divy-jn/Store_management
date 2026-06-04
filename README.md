# Purplle Store Intelligence

Real-time offline retail analytics from CCTV footage: detect visitors, emit structured events, ingest them into a production-aware API, and show live store metrics on a dashboard.

Built for the Purplle Tech Challenge 2026 Round 2. The north-star metric is offline store conversion rate:

```text
conversion_rate = visitors with a POS-correlated billing-zone visit / unique non-staff visitors
```

## Why This Submission Scores

This repo is organized around the evaluation framework:

| Rubric area | What is implemented |
|---|---|
| Detection Pipeline, 30 pts | YOLOv8s person detection, ByteTrack tracking, ReID visitor tokens, synchronized multi-camera frame processing, zone classification, staff exclusion, queue depth, re-entry events, JSONL event emission |
| API and Business Logic, 35 pts | FastAPI endpoints for ingest, metrics, funnel, heatmap, anomalies, and health; idempotent partial-success ingestion; session-based funnel; POS time-window conversion correlation |
| Production Readiness, 20 pts | Docker Compose, PostgreSQL, structured JSON request logs, health checks, graceful 503 degradation, retrying event replay, 54 automated tests |
| Engineering Thinking, 15 pts | Non-trivial `DESIGN.md` and `CHOICES.md`, plus AI prompt/change blocks in test files |
| Live Dashboard, +10 bonus | Web dashboard at `http://localhost:3000` with WebSocket live counters, charts, anomaly toasts, and replay demo controls |

## Five-Command Review Path

```bash
# 1. Start API, PostgreSQL, and dashboard
docker compose up --build -d

# 2. Confirm service health
curl http://localhost:8000/health

# 3. Generate structured events from the provided Store 1 footage folder
python pipeline/detect.py --input-dir "./Project details/New folder/Store 1" --output-dir ./output/events --store-id ST1008

# 4. Replay generated events into the API
python pipeline/replay.py --events-dir ./output/events --api-url http://localhost:8000

# 5. Inspect live metrics
curl http://localhost:8000/stores/ST1008/metrics
```

Dashboard: open `http://localhost:3000`.

Windows shortcut: double-click `start.bat` to launch Docker services and the dashboard, then run the pipeline command above when you want fresh events.

## What To Inspect First

For a fast reviewer pass:

1. `GET /health` should return service status, database connectivity, per-store event counts, last event timestamps, and stale-feed warnings.
2. `output/events/*.jsonl` should contain schema-compliant events with unique `event_id`, `visitor_id`, `event_type`, `timestamp`, `is_staff`, `confidence`, and metadata fields.
3. `GET /stores/ST1008/metrics` should show non-staff visitor counts, conversion rate, dwell data, queue depth, and abandonment rate.
4. `GET /stores/ST1008/funnel` should show Entry -> Zone Visit -> Billing Queue -> Purchase with session-based de-duplication.
5. `DESIGN.md` and `CHOICES.md` explain the system and the trade-offs behind the model, event schema, and API design.
6. `events.jsonl` in the project root is the final converted log deliverable matching the requested sample schema format.

## API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | Root service metadata and endpoint links |
| `/health` | GET | Operational health, store freshness, stale-feed signal |
| `/events/ingest` | POST | Ingest up to 500 events with idempotency and partial success |
| `/stores/{store_id}/metrics` | GET | Unique visitors, conversion, dwell, queue, abandonment |
| `/stores/{store_id}/funnel` | GET | Session funnel and drop-off percentages |
| `/stores/{store_id}/heatmap` | GET | Zone visit frequency, dwell, normalized 0-100 heatmap score |
| `/stores/{store_id}/anomalies` | GET | Queue spike, conversion drop, dead zone, stale feed anomalies |
| `/ws/live/{store_id}` | WebSocket | Live dashboard metric updates |
| `/system/demo-replay` | POST | Clear DB and replay generated events for the dashboard demo |
| `/system/demo-skip` | POST | Fast-forward demo replay timing |

Example ingest payload:

```json
{
  "events": [
    {
      "event_id": "0a308a36-8a4f-4a0e-9d3f-3d84a8dd0001",
      "store_id": "ST1008",
      "camera_id": "CAM_ENTRY_01",
      "visitor_id": "VIS_c8a2f1",
      "event_type": "ENTRY",
      "timestamp": "2026-04-10T10:15:00Z",
      "zone_id": null,
      "dwell_ms": 0,
      "is_staff": false,
      "confidence": 0.91,
      "metadata": {
        "queue_depth": null,
        "sku_zone": null,
        "session_seq": 1
      }
    }
  ]
}
```

## Detection Pipeline

The pipeline processes CCTV clips into behavioral events:

```bash
python pipeline/detect.py --input-dir "./Project details/New folder/Store 1" --output-dir ./output/events --store-id ST1008
python pipeline/replay.py --events-dir ./output/events --api-url http://localhost:8000
```

PowerShell helper:

```powershell
./pipeline/run.ps1
./pipeline/run.ps1 -InputDir "./Project details/New folder/Store 2" -StoreId ST1009
```

Core pipeline choices:

- `YOLOv8s` detects people from CCTV frames.
- `ByteTrack` links detections into stable per-camera tracks.
- `ReIDManager` assigns reusable visitor tokens for cross-camera continuity and re-entry handling.
- `ZoneClassifier` maps bounding-box foot points into polygons from `store_layout.json`.
- `StaffDetector` flags staff-like uniforms so staff traffic is excluded from customer metrics.
- `QueueTracker` emits billing queue depth and abandonment events.
- `EventEmitter` writes strict JSONL events that match `app.models.Event`.

Known challenge edge cases covered:

- Group entry: each tracked person can emit a separate `ENTRY`.
- Staff movement: `is_staff=true` is preserved and analytics exclude those events.
- Re-entry: previously exited visitors can emit `REENTRY` instead of inflating entry counts.
- Partial occlusion: low-confidence events keep their confidence value instead of being silently suppressed.
- Billing queue buildup: queue joins include `metadata.queue_depth`.
- Empty store periods: endpoints return zero-value responses, not null crashes.
- Camera overlap: per-camera zone state reduces noisy cross-camera zone flicker.

## Live Dashboard

The dashboard is served by the `dashboard` service at `http://localhost:3000`.

Features:

- Live in-store visitor count and queue depth via WebSocket.
- Conversion funnel and zone heatmap via REST.
- Average dwell time by zone.
- Anomaly alert toasts.
- Store selector for multi-store views.
- Live demo mode that clears data, replays events, and signals completion.

## Testing and Verification

```bash
pytest tests/ -v --cov=app --cov-report=term-missing
python -m compileall app pipeline tests -q
node --check dashboard/app.js
```

Current local verification:

- `pytest tests/ -v --cov=app --cov-report=term-missing`: 54 passed, 71% app coverage.
- `python -m compileall app pipeline tests -q`: passed.
- `node --check dashboard/app.js`: passed.
- `git diff --check`: passed.

The tests cover:

- Pydantic event validation and enum compliance.
- Ingest partial success, duplicate events, malformed input, and sample-event normalization.
- Empty store, all-staff traffic, conversion, abandonment, and funnel math.
- Heatmap normalization and low/high confidence flags.
- Anomaly helper behavior and database-unavailable 503 degradation.
- Pipeline helper units: queue tracking, zone lookup, event emission, timestamp calculation, and staff detector bounds.

## Production Behavior

- `docker compose up --build` starts PostgreSQL, FastAPI, and dashboard.
- PostgreSQL schema is initialized on API startup.
- POS data is loaded from the preferred challenge CSV when available, with fallback to the older dataset.
- Request logs include trace ID, method, endpoint, store ID, latency, status code, and ingest event count.
- `/events/ingest` is idempotent by `event_id` through `ON CONFLICT DO NOTHING`.
- API endpoints return structured `503` bodies when the database is unavailable.
- `pipeline/replay.py` retries failed batches with exponential backoff.

## Project Structure

```text
app/                 FastAPI application, schemas, DB, analytics endpoints
pipeline/            Detection, tracking, ReID, zone, queue, replay utilities
dashboard/           Static web dashboard
tests/               Unit and route tests with AI prompt/change headers
DESIGN.md            Architecture and AI-assisted design decisions
CHOICES.md           Model, schema, and API trade-off rationale
events.jsonl         Final event log deliverable matching sample schema
store_layout.json    Store zones and camera coverage
docker-compose.yml   Local reviewer startup
Dockerfile           API image
```

## Follow-Up Question Prep

The most likely reviewer questions and the short answers are:

- Why YOLOv8s? It is the speed/accuracy middle ground for 15fps CCTV and integrates cleanly with ByteTrack.
- Why not suppress low-confidence detections? The problem statement asks confidence to degrade gracefully; downstream analytics can decide thresholds.
- Why PostgreSQL? JSONB metadata plus indexed relational fields fit evolving event attributes without giving up fast grouped queries.
- What breaks first at 40 stores? Analytics queries need rollups/materialized views or streaming aggregates; raw event scans become the bottleneck.
- Why WebSockets over SSE? The dashboard needs live updates and backend-to-frontend demo completion signaling without polling.
