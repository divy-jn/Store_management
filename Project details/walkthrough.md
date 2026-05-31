# Purplle Store Intelligence - Final Walkthrough

This document summarizes the end-to-end computer vision and analytics pipeline built for the Purplle Tech Challenge 2026.

## The Architecture
The project successfully bridges edge-based computer vision with cloud-based analytics using a three-tier architecture:

1. **Edge Detection Pipeline**: Uses `YOLOv8s` for lightweight person detection and `ByteTrack` for tracking. We utilized a pretrained `ResNet18` model to extract Re-ID features, enabling us to stitch a customer's journey across multiple cameras.
2. **Intelligence API**: A strict, highly-concurrent `FastAPI` application backed by `PostgreSQL 16`. 
3. **Live Dashboard**: A beautiful, dependency-free Glassmorphism dashboard leveraging `WebSockets` to render live store events alongside `Chart.js` analytical graphs.

## Robustness & Edge Cases Handled

During our final iteration, we applied several architectural changes to ensure the pipeline behaves robustly in a real-world store:

> [!TIP]
> **Synchronous Multi-Camera Reading**
> Instead of analyzing recorded videos sequentially (which breaks chronological timelines and ruins cross-camera analytics), `detect.py` now opens `cv2.VideoCapture` objects for all 5 cameras simultaneously. It loops through frames in lockstep, simulating a true Network Video Recorder (NVR).

> [!IMPORTANT]
> **Ghost Track Filtering**
> YOLOv8 can occasionally hallucinate people (e.g., detecting a mannequin or a clothing poster). We implemented a **Minimum Lifespan Filter**: a tracking bounding box must exist for at least 15 frames (~1 second) and exceed a confidence of `0.50` before it is recognized as a valid visitor.

> [!WARNING]
> **API Resiliency**
> If the backend database restarts or the network blips, analytics events cannot be lost. We wrapped the event emitter (`replay.py`) in an exponential backoff loop using the `tenacity` library. If a POST request fails, it will safely wait and retry up to 5 times.

> [!NOTE]
> **Cross-Camera Zone Boundaries**
> When a customer stands in an area covered by two overlapping cameras, they can trigger noisy, flickering zone transitions. By isolating the visitor's zone state (`state["zone"]`) *per camera*, we eliminated this race condition. Additionally, global `ENTRY` and `EXIT` events are strictly tied to the designated entrance gate (`CAM_ENTRY_01`), preventing stray interior detections from skewing the total Walk-In metrics.

## Running the Complete System
To run the fully robust version:
1. Ensure the API is up via `docker-compose up -d`.
2. Run `.\run.ps1` in the `pipeline` directory.
3. Open `http://localhost:3000` to watch the analytics populate in real-time.
