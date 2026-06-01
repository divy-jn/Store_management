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
# Process all clips on Windows
./pipeline/run.ps1

# Or run cross-platform commands directly
python pipeline/detect.py --input-dir "<cctv-footage-dir>" --output-dir ./output/events
python pipeline/replay.py --events-dir ./output/events --api-url http://localhost:8000
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

### ✨ The "Live Demo" Feature (Wow Factor)
To experience the dashboard as a store manager would in real-time, click the **▶ Live Demo** button in the top right corner of the dashboard.
1. The database instantly clears.
2. The backend streams the CCTV events back into the API via WebSockets, shifting all timestamps to `datetime.now()` to prevent false anomalies.
3. A stopwatch appears tracking simulation time.
4. Use the **⏭ Skip 10s** button to fast-forward the day.
5. Watch the dashboard metrics, conversion funnel, and heatmaps populate live!

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
