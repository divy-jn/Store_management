# Robustness & Edge Case Handling Plan

To make the system truly robust and handle all production edge cases for the Store Intelligence pipeline, we need to address several critical flaws and edge cases that arise in real-world CCTV environments.

## User Review Required

> [!IMPORTANT]
> The most critical edge case currently is **Time Synchronization**. Right now, the pipeline processes Video 1 entirely, then Video 2 entirely. Because they are processed sequentially, a person who appears in Video 1 and Video 2 concurrently (in real life) will have their timeline distorted.
> 
> **My Proposed Solution**: We will modify the pipeline to process all 5 videos **synchronously**, reading frame 1 from all cameras, then frame 2, etc. This perfectly mimics a real NVR (Network Video Recorder) and ensures ReID and Zone tracking happen chronologically. Please approve this architectural change.

## Proposed Changes

### 1. Synchronized Multi-Camera Processing (The Core Fix)
Currently, videos are processed one after another. 
#### [MODIFY] `pipeline/detect.py`
- Refactor `process_video` into `process_streams`.
- Open `cv2.VideoCapture` for all 5 videos simultaneously.
- Loop through frames in lockstep (read 1 frame from each camera per iteration).
- This ensures timestamps are globally accurate and `visitor_id` state transitions happen in the correct chronological order across the entire store.

### 2. Ghost Track & Flicker Mitigation
YOLO sometimes detects a mannequin or a poster as a person, or a bounding box flickers for a fraction of a second.
#### [MODIFY] `pipeline/detect.py`
- Introduce a **Minimum Lifespan Filter**: A track must be seen for at least `N` frames (e.g., 15 frames / 1 second) before it is recognized as a valid visitor.
- Add a **Minimum Confidence Threshold**: Ignore YOLO detections below 0.5 confidence.

### 3. API & Ingestion Resilience
If the FastAPI server blips or Postgres locks, the `replay.py` script will drop data.
#### [MODIFY] `pipeline/replay.py`
- Add exponential backoff and retry logic using the `tenacity` library or a custom retry loop to ensure 100% of JSONL events are delivered safely.

### 4. Cross-Camera State Separation
If a visitor is standing in the overlap between `CAM_FLOOR_01` (Skincare) and `CAM_FLOOR_02` (Fragrance), they will emit conflicting zone events.
#### [MODIFY] `pipeline/detect.py`
- Track `state["zone"]` separately for each camera inside the visitor's state dictionary to prevent "zone flickering" when they stand in camera overlaps.

## Verification Plan

### Automated Tests
- Run `.\run.ps1` to ensure the multi-camera synchronized loop correctly parses all 5 videos simultaneously without crashing or dropping frames.
- Verify that `replay.py` correctly handles HTTP connection retries if the API is slow.

### Manual Verification
- Review the `events.jsonl` to verify that `ENTRY` and `EXIT` are only fired by `CAM_ENTRY_01`.
- Verify that short-lived ghost tracks (duration < 1s) are not emitted to the JSONL.
