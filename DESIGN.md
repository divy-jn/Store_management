# Purplle Store Intelligence - System Design

## 1. High-Level Architecture

The Store Intelligence system is composed of three loosely coupled subsystems:
1. **The Edge Detection Pipeline** (Computer Vision)
2. **The Intelligence API & Backend** (FastAPI + PostgreSQL)
3. **The Live Dashboard** (Web UI)

```mermaid
graph TD
    subgraph "Edge Device (Store)"
        CCTV["CCTV Cameras (1-5)"]
        YOLO["YOLOv8 Detection"]
        BT["ByteTrack MOT"]
        ReID["OSNet / ResNet18 ReID"]
        EMIT["JSONL Emitter"]
        
        CCTV --> YOLO
        YOLO --> BT
        BT --> ReID
        ReID --> EMIT
    end

    subgraph "Cloud / Central Server"
        API["FastAPI App (uvicorn)"]
        DB[(PostgreSQL 16)]
        
        EMIT -- "POST /events/ingest" --> API
        API <--> DB
    end

    subgraph "Web Client"
        DASH["Live Dashboard (Vanilla JS/CSS)"]
        
        API -- "WebSocket (Live Updates)" --> DASH
        API -- "REST (Metrics, Heatmap, Funnel)" --> DASH
    end
```

## 2. Component Details

### 2.1 The Edge Detection Pipeline
- **Role**: Process raw RTSP/MP4 streams locally to save bandwidth. Extracts semantic events (ENTRY, EXIT, ZONE_ENTER).
- **YOLOv8s**: Runs at 15 FPS for fast, accurate person detection.
- **ByteTrack**: Links bounding boxes across frames using IoU (Intersection over Union). Handles short-term occlusions efficiently.
- **ReID (ResNet18)**: Extracts a 512-dim embedding from the upper body of detected persons. Maintains a local gallery to match visitors across different cameras (e.g., when a person moves from `CAM_FLOOR_01` to `CAM_FLOOR_02`).
- **Zone Classifier**: Uses `shapely` polygons mapped to the store layout. Checks if the bottom-center of a bounding box (the person's feet) intersects with a zone polygon.
- **Staff Detector**: Crops the upper 50% of the bounding box and calculates HSV color histograms to detect Purplle uniform colors (Black/Purple), filtering staff out of conversion metrics.

### 2.2 The Intelligence API
- **Role**: Ingest, validate, and query store analytics.
- **FastAPI**: Provides asynchronous, non-blocking HTTP handlers.
- **Pydantic**: Enforces strict typing for the incoming JSONL schema. Rejects malformed events automatically, returning `{ "rejected": 1 }`.
- **PostgreSQL**: Stores structured events. Uses constraints (`UNIQUE (event_id)`) for idempotency, ensuring safely retriable event ingestion.
- **WebSockets**: Maintains active connections to connected dashboard clients and pushes aggregated metric updates in real-time.

### 2.3 The Database Schema
```sql
CREATE TABLE IF NOT EXISTS store_events (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(100) UNIQUE NOT NULL,
    store_id VARCHAR(50) NOT NULL,
    camera_id VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    visitor_id VARCHAR(100) NOT NULL,
    zone_id VARCHAR(50),
    dwell_ms INTEGER,
    confidence FLOAT,
    is_staff BOOLEAN DEFAULT FALSE,
    metadata JSONB
);
```
- **Indexes**: Created on `(store_id, timestamp)`, `event_type`, and `visitor_id` to speed up the complex JOINs required for the Funnel and Heatmap APIs.

## 3. Data Flow Example (Visitor Journey)
1. **10:05 AM**: Customer walks into CAM 3. YOLO detects -> ByteTrack assigns ID 1 -> ReID creates `VIS_0001`. Pipeline emits `ENTRY`.
2. **10:06 AM**: Customer walks to Fragrance section (CAM 2). Pipeline emits `ZONE_ENTER` (zone: FRAGRANCE).
3. **10:10 AM**: Customer leaves Fragrance section. Pipeline emits `ZONE_EXIT` and `ZONE_DWELL` (dwell_ms: 240000).
4. **10:15 AM**: Customer queues at Billing. Pipeline emits `BILLING_QUEUE_JOIN`.
5. **10:20 AM**: Customer leaves store (CAM 3). Pipeline emits `EXIT`.
6. API calculates conversion: Funnel updates `[Walk-ins: +1, Zone Visits: +1, Billing: +1]`.
