# 🏪 Store Intelligence API

> Real-time analytics for offline retail stores — from CCTV footage to actionable insights.

Built for the **Purplle Tech Challenge 2026 — Round 2**.

---

## 🚀 Quick Start (5 Commands)

```bash
# 1. Clone the repository
git clone <repo-url> && cd store-intelligence

# 2. Start all services (API + PostgreSQL + Dashboard)
docker compose up --build -d

# 3. Verify the API is running
curl http://localhost:8000/health

# 4. Run the detection pipeline on CCTV clips
python pipeline/detect.py --input-dir "./Project details/CCTV Footage-20260529T160731Z-3-00144614ea (1)/CCTV Footage" --output-dir ./output/events

# 5. Feed events into the API
python pipeline/replay.py --events-dir ./output/events --api-url http://localhost:8000
```

---

## 📊 Architecture

```
📹 CCTV Clips (5 cameras)
    → 🔍 Detection Pipeline (YOLOv8 + ByteTrack + Re-ID)
        → ⚡ Structured Events (JSONL)
            → 🧠 Intelligence API (FastAPI + PostgreSQL)
                → 📊 Live Dashboard (WebSocket + Chart.js)
```

## 🔗 API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Service health check |
| `/events/ingest` | POST | Batch event ingestion (up to 500) |
| `/stores/{id}/metrics` | GET | Real-time store metrics |
| `/stores/{id}/funnel` | GET | Conversion funnel |
| `/stores/{id}/heatmap` | GET | Zone heatmap data |
| `/stores/{id}/anomalies` | GET | Active anomalies |
| `/ws/live/{id}` | WebSocket | Real-time dashboard updates |

**Store ID**: `ST1008` (Brigade Road, Bangalore)

## 🔍 Detection Pipeline

The pipeline processes CCTV footage to generate structured behavioral events:

```bash
# Process all clips
./pipeline/run.sh

# Or on Windows
./pipeline/run.ps1
```

**Models Used:**
- **YOLOv8s** — Person detection
- **ByteTrack** — Multi-object tracking
- **OSNet** — Re-identification for re-entry detection

**Edge Cases Handled:**
- Group entry (separate tracks per individual)
- Staff exclusion (uniform-based classification)
- Re-entry detection (same person, new visit)
- Partial occlusion (graceful confidence degradation)
- Queue depth tracking in billing zone
- Cross-camera deduplication

## 🧪 Testing

```bash
# Run all tests with coverage
pytest tests/ -v --cov=app --cov-report=term-missing

# Run specific test file
pytest tests/test_metrics.py -v
```

**Target**: >70% statement coverage

## 📈 Live Dashboard

Access the dashboard at: **http://localhost:3000**

Features:
- Real-time visitor count
- Conversion funnel visualization
- Zone heatmap
- Anomaly alerts
- WebSocket live updates

## 🐳 Docker

```bash
# Start all services
docker compose up --build

# Stop services
docker compose down

# View logs
docker compose logs -f api
```

## 📁 Project Structure

```
├── app/                    # FastAPI application
│   ├── main.py            # Entrypoint
│   ├── models.py          # Pydantic schemas
│   ├── database.py        # PostgreSQL layer
│   ├── ingestion.py       # POST /events/ingest
│   ├── metrics.py         # GET /stores/{id}/metrics
│   ├── funnel.py          # GET /stores/{id}/funnel
│   ├── heatmap.py         # GET /stores/{id}/heatmap
│   ├── anomalies.py       # GET /stores/{id}/anomalies
│   ├── health.py          # GET /health
│   ├── websocket.py       # WebSocket endpoint
│   ├── middleware.py       # Structured logging
│   └── pos_loader.py      # POS data loader
├── pipeline/              # Detection pipeline
├── dashboard/             # Live dashboard (HTML/CSS/JS)
├── tests/                 # Test suite
├── docs/                  # DESIGN.md + CHOICES.md
├── docker-compose.yml     # Single command startup
├── Dockerfile             # Multi-stage build
├── requirements.txt       # Python dependencies
└── store_layout.json      # Zone definitions
```

## 📝 License

Challenge use only. Not for redistribution.
