# 📝 MCQ Quiz Responses — Project Requirements Gathering

> **Date**: 2026-05-31  
> **Purpose**: Gather user inputs to finalize implementation decisions  

---

## Responses Summary

### Q1: GPU Availability ✅
**Answer**: I have an NVIDIA GPU with CUDA support (e.g., RTX 3060, 4060, etc.)
- ✅ Great — YOLOv8 will run efficiently with CUDA acceleration
- Action: Use `device='cuda'` for detection pipeline

### Q2: Docker ✅
**Answer**: Docker is installed but not running right now
- Action: Start Docker Desktop before running `docker compose up`
- Note: We'll build and test without Docker first, containerize at the end

### Q3: Python Version ✅
**Answer**: Python 3.12
- ✅ Compatible with all planned libraries (FastAPI, Ultralytics, torchreid)
- Action: Use Python 3.12 for development and Docker image

### Q4: Dataset Completeness ⚠️
**Answer**: Organization will provide additional files later. Build with what's available.
- Current files: CCTV footage (5 cameras), POS CSV, Store Layout Excel, Problem Statement
- Missing: store_layout.json, sample_events.jsonl, assertions.py
- **Decision**: We'll create store_layout.json from the Excel file ourselves. We'll write our own assertions based on the problem statement. sample_events.jsonl we'll generate from our detection pipeline.

### Q5: Camera Mapping ✅
**Answer**: User knows the mapping and will share it
- **Action**: User to provide which CAM (1-5) maps to which zone (Entry, Floor, Billing)
- ⏳ Awaiting the specific mapping

### Q6: Store ID ✅
**Answer**: Use ST1008 (match the actual data we have)
- **Decision**: Use `ST1008` as the primary store_id throughout the system
- Note: We can add an alias mapping if needed later

### Q7: Scope ✅
**Answer**: All 5 parts (A+B+C+D+E) for maximum score (100 + 10 bonus)
- **Plan**: Build all parts, prioritizing A → B → C → D → E

### Q8: Detection Approach ✅
**Answer**: YOLOv8 + ByteTrack (proven, fast, well-documented)
- **Decision**: Use YOLOv8s for person detection + ByteTrack for MOT
- Libraries: `ultralytics`, `supervision`

### Q9: Database ✅
**Answer**: Use what's free and efficient
- **Decision**: PostgreSQL (free, open-source, production-grade, runs in Docker)
- Alternative consideration: SQLite for lightweight testing
- Note: PostgreSQL is completely free — community edition is what we'll use

### Q10: Dashboard ✅
**Answer**: Premium Web UI with glassmorphism design, real-time charts (Chart.js), WebSocket updates
- **Decision**: Build a stunning dark-theme glassmorphism dashboard
- Tech: Vanilla HTML/CSS/JS + Chart.js + WebSocket
- Features: Real-time visitor count, conversion funnel, zone heatmap, anomaly alerts

### Q11: Development Approach ✅
**Answer**: Agile method of development
- **Decision**: Iterative development — build MVP sprints, demo, iterate
- Sprint 1: Project scaffold + API skeleton + basic detection
- Sprint 2: Full detection pipeline + API analytics
- Sprint 3: Tests + production readiness + dashboard
- Sprint 4: Documentation + polish + verification

### Q12: AI Documentation ✅
**Answer**: Strategic — highlight where AI helped most, show my own critical thinking
- **Decision**: Document AI usage authentically but strategically
- Highlight: Model selection rationale, schema design iteration, edge case handling
- Show: Personal reasoning, overrides, and critical evaluation of AI suggestions

---

## 🔴 Still Needed Before We Start Building

| # | Item | Status |
|---|---|---|
| 1 | Camera zone mapping (which CAM = which zone) | ⏳ User to provide |
| 2 | Start Docker Desktop | ⏳ When ready to build |
| 3 | Verify NVIDIA GPU/CUDA setup | ⏳ Need to check |

---

## ✅ Decisions Finalized

| Decision | Final Choice |
|---|---|
| GPU | NVIDIA CUDA |
| Python | 3.12 |
| Docker | Installed, will start when needed |
| Store ID | ST1008 |
| Detection | YOLOv8s + ByteTrack |
| Database | PostgreSQL (free) |
| Dashboard | Premium glassmorphism Web UI |
| Scope | All 5 parts (A-E) |
| Approach | Agile sprints |
| AI Docs | Strategic documentation |
| Missing files | Create ourselves from available data |
