# 📋 Purplle Tech Challenge 2026 — Project History & Progress Log

> **Project**: Apex Retail — Store Intelligence System  
> **Challenge**: Purplle Engineering Hiring Challenge — Round 2  
> **Started**: 2026-05-29  
> **Last Updated**: 2026-05-31  
> **Status**: 🟡 Planning Phase — Awaiting User Inputs  

---

## 📁 Project Files Inventory

| File / Folder | Type | Description |
|---|---|---|
| `Purplle Tech Challenge 2026 _ Round 2 Problem Statement480e74e.md` | Problem Statement | Full challenge description (359 lines) |
| `Purplle Tech Challenge 2026 _ Round 2 Problem Statement480e74e.pdf` | Problem Statement | PDF version of the same |
| `Assessment Evaluation Frameworkb24a398.pdf` | Evaluation | Scoring/evaluation rubric |
| `Brigade Road - Store layoutc5f5d56.xlsx` | Store Data | Store zone layout for Brigade Road, Bangalore |
| `Brigade_Bangalore_10_April_26 (1)bc6219c.csv` | POS Data | 102 POS transaction records from Brigade Bangalore store (ST1008), dated 10-Apr-2026 |
| `CCTV Footage/CAM 1 store inside.mp4` | Video | **Main Floor** — Store interior angle 1 (~172 MB) |
| `CCTV Footage/CAM 2 store inside 2nd angle.mp4` | Video | **Main Floor** — Store interior angle 2 (~155 MB) |
| `CCTV Footage/CAM3 entrance.mp4` | Video | **Entry/Exit** — Store entrance (~182 MB) |
| `CCTV Footage/CAM 4 internal area.mp4` | Video | **Internal Area** — Back/internal zone (~70 MB) |
| `CCTV Footage/CAM 5 billing.mp4` | Video | **Billing** — Billing counter area (~70 MB) |

---

## 📊 Data Analysis Summary

### POS Transaction Data (`Brigade_Bangalore_10_April_26.csv`)
- **Store**: ST1008 — Brigade_Bangalore
- **City**: Bangalore
- **Date**: 10-Apr-2026
- **Time Range**: 12:15 PM to 9:39 PM (approximately 9.5 hours of data)
- **Total Line Items**: 102 rows
- **Unique Orders**: ~22 distinct order_ids
- **Key Columns**: order_id, coupon_code, offer_name, invoice_number, order_date, order_time, store_id, store_name, city, customer_name, customer_number, sku, product_name, brand_name, dep_name, sub_category, qty, GMV, NMV, coupon_amount, total_amount
- **Brands Present**: Faces Canada, NY Bae, DERMDOC, Alps Goodness, Good Vibes, Carmesi, COSRX, Maybelline, Lakme, Juicy Chemistry, FoxTale, Bare Anatomy, Lotus Herbals, Neutrogena, Round Lab, Swiss Beauty, Renee, GUBB, Garnier, Cuffs N Lashes
- **Departments**: makeup, skin, hair, personal-care, bath-and-body, fragrance
- **Salespersons**: Zufishan Khazra, Shashikala, kasthuri v, Priya v, Naziya Begum

### CCTV Footage
- **5 camera feeds** (CAM 1 through CAM 5)
- Total footage size: ~649 MB
- Video resolution: Expected 1080p, 15fps (per problem statement)
- Duration: Expected 20 minutes per clip

### Store Layout
- Excel file for Brigade Road store — zone definitions and camera coverage

---

## 🗓 Timeline of Actions

### Session 1 — 2026-05-29
- ✅ Read and analyzed the full Purplle Tech Challenge 2026 Round 2 Problem Statement
- ✅ Created a comprehensive implementation plan covering all 5 parts:
  - **Part A**: Detection Pipeline (30 pts) — YOLOv8 + ByteTrack + OSNet Re-ID (Complete)
  - **Part B**: Intelligence API (35 pts) — FastAPI with 6 endpoints (Complete)
  - **Part C**: Production Readiness (20 pts) — Docker, logging, tests (Complete)
  - **Part D**: AI Engineering (15 pts) — DESIGN.md, CHOICES.md (Complete)
  - **Part E**: Live Dashboard (+10 bonus) — Glassmorphism Web UI (Complete)
- ⏳ Raised critical questions about dataset, GPU, Docker, Python version
- ⏳ Awaiting user responses before proceeding to implementation

### Session 2 — 2026-05-31
- ✅ Re-read all project files (problem statement, CSV data, folder structure)
- ✅ Created PROJECT_HISTORY.md, IMPLEMENTATION_PLAN.md, MCQ_RESPONSES.md
- ✅ MCQ quiz (12 questions) — all answers received
- ✅ **Finalized decisions**: NVIDIA GPU, Python 3.12, YOLOv8+ByteTrack, PostgreSQL, Premium Dashboard
- ✅ User renamed CCTV files → camera zone mapping resolved
- ✅ **Sprint 1 COMPLETE** — Project scaffold + API skeleton built:
  - Created 13 Python files in `app/` (main, models, database, 7 endpoints, middleware, POS loader)
  - Created Docker setup (Dockerfile + docker-compose.yml + .env)
  - Created store_layout.json, README.md, .gitignore, requirements.txt
  - Created test fixtures (conftest.py)
  - All dependencies installed, imports verified ✅
  - 7 API routes + WebSocket + health check registered ✅
- ✅ **Sprint 2 COMPLETE** — Detection Pipeline (YOLOv8 + ByteTrack):
  - Created `pipeline/emit.py` for structured JSONL event emission.
  - Implemented `pipeline/tracker.py` using `supervision` ByteTrack.
  - Implemented `pipeline/zone_classifier.py` for spatial logic.
  - Implemented `pipeline/staff_detector.py` (uniform color histogram).
  - Implemented `pipeline/queue_tracker.py` for billing queue depth.
  - Implemented `pipeline/reid.py` (ResNet18 embeddings) for cross-camera tracking.
  - Created `pipeline/detect.py` to tie YOLOv8 detections together.
  - Added `pipeline/run.ps1` and `pipeline/replay.py` for execution.
- ✅ **Sprint 3 COMPLETE** — Live Dashboard (Premium UI):
  - Created `dashboard/index.html` structure with Chart.js canvas containers.
  - Added `dashboard/style.css` with dark mode glassmorphism and animated mesh background.
  - Created `dashboard/app.js` to fetch metrics, render charts, and connect to WebSocket for live visitor updates and toasts.

---

## 🎯 What We're Building

### System Architecture
```
📹 Raw CCTV Clips
    → 🔍 Detection Layer (YOLOv8 + ByteTrack + Re-ID)
        → ⚡ Event Stream (structured JSONL events)
            → 🧠 Intelligence API (FastAPI + PostgreSQL)
                → 📊 Live Dashboard (Web UI)
```

### North Star Metric
**Offline Store Conversion Rate** = Visitors who completed a purchase ÷ Total unique visitors

### Key Deliverables
1. **Detection Pipeline** — Process CCTV → structured behavioral events
2. **Intelligence API** — 6 REST endpoints with real-time analytics
3. **Docker Containerization** — `docker compose up` starts everything
4. **Documentation** — DESIGN.md + CHOICES.md + README.md
5. **Live Dashboard** — Real-time metrics visualization

---

## ❓ Outstanding Questions (Blocking Progress)

| # | Question | Status |
|---|---|---|
| 1 | Dataset availability — do we have store_layout.json, sample_events.jsonl, assertions.py? | ❓ Pending |
| 2 | GPU availability — CUDA/GPU for detection pipeline? | ❓ Pending |
| 3 | Python version installed? | ❓ Pending |
| 4 | Docker Desktop installed and running? | ❓ Pending |
| 5 | Scope preference — all parts or focus on A+B+C? | ❓ Pending |
| 6 | Camera mapping — which CAM maps to which zone (Entry, Floor, Billing)? | ✅ Resolved |
| 7 | Development environment preferences? | ❓ Pending |

---

## 📐 Technical Decisions Made So Far

| Decision | Choice | Rationale |
|---|---|---|
| Detection Model | YOLOv8s | Best speed/accuracy trade-off for retail CCTV |
| Tracking | ByteTrack | Handles occlusion well, no appearance model needed |
| Re-ID | OSNet (torchreid) | Lightweight re-entry detection |
| Staff Detection | Color histogram | Uniform-based detection |
| API Framework | FastAPI | Async, auto-docs, Pydantic, scoring harness support |
| Database | PostgreSQL 16 | Robust, JSON support, production-grade |
| Dashboard | Vanilla HTML/CSS/JS | No build step, premium glassmorphism UI |
| Logging | structlog (JSON) | Structured with trace_id, latency_ms |
| Testing | pytest + httpx | Standard FastAPI testing stack |

---

## 📝 Notes

- The problem statement mentions **5 stores × 3 cameras** but we have data for only **1 store (ST1008 — Brigade Bangalore)** with **5 cameras**
- POS data contains customer names and phone numbers — these should not be exposed in the API
- The CSV data uses `store_id: ST1008` while the problem statement examples use `STORE_BLR_002` — need to clarify mapping
- Some files mentioned in the problem statement (store_layout.json, sample_events.jsonl, assertions.py) are not present in the project folder — may need to be created or obtained
