# 🏗️ Sprint 1 — Project Scaffold + API Skeleton

## Phase 1: Project Structure & Config
- [x] Create directory structure (pipeline/, app/, dashboard/, tests/, docs/)
- [x] Create requirements.txt
- [x] Create Dockerfile
- [x] Create docker-compose.yml
- [x] Create store_layout.json from available data
- [x] Create .env, .gitignore, README.md

## Phase 2: Database Layer
- [x] Create app/database.py — PostgreSQL connection + schema
- [x] Create app/pos_loader.py — POS CSV ingestion

## Phase 3: FastAPI Core
- [x] Create app/models.py — Pydantic schemas for all events/responses
- [x] Create app/main.py — FastAPI app with middleware, CORS, lifespan
- [x] Create app/middleware.py — Structured logging middleware

## Phase 4: API Endpoints
- [x] Create app/ingestion.py — POST /events/ingest
- [x] Create app/metrics.py — GET /stores/{id}/metrics
- [x] Create app/funnel.py — GET /stores/{id}/funnel
- [x] Create app/heatmap.py — GET /stores/{id}/heatmap
- [x] Create app/anomalies.py — GET /stores/{id}/anomalies
- [x] Create app/health.py — GET /health
- [x] Create app/websocket.py — WebSocket for dashboard

## Phase 5: Verify
- [x] Install dependencies
- [x] Run FastAPI locally and test endpoints
- [x] Verify docker compose builds

---

# 👁️ Sprint 2 — Detection Pipeline

## Phase 1: Core Object Tracking
- [x] Set up YOLOv8 model for person detection in `detect.py`
- [x] Implement ByteTrack in `tracker.py` for MOT (Multi-Object Tracking)

## Phase 2: Spatial & Behavior Logic
- [x] Implement `zone_classifier.py` using polygons from `store_layout.json`
- [x] Implement `staff_detector.py` (uniform detection / movement rules)
- [x] Implement `queue_tracker.py` for billing queue depth logic
- [x] Implement `reid.py` for cross-camera/re-entry tracking

## Phase 3: Integration & Emitter
- [x] Integrate components in `detect.py` main loop
- [x] Implement `emit.py` for strict schema event emission
- [x] Create `run.sh` / `run.ps1` helper scripts
- [ ] Validate on sample video clip

---

# 📊 Sprint 3 — Live Dashboard
- [x] Create `index.html` structure
- [x] Implement premium Glassmorphism UI in `style.css`
- [x] Connect WebSocket for real-time live visitor updates in `app.js`
- [x] Fetch and render Heatmap & Funnel charts (Chart.js)
- [x] Add Anomaly alert toast notifications

---

# 🛡️ Sprint 4 — Robustness & Edge Cases
- [x] Synchronize multi-camera processing in `detect.py` (read frames concurrently)
- [x] Add ghost track & flicker mitigation (confidence threshold, min lifespan)
- [x] Implement cross-camera zone state separation
- [x] Add exponential backoff retry logic to `replay.py`

