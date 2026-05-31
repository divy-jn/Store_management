# Robustness & Edge Case Handling Plan

This document outlines the architectural changes required to make the Purplle Store Intelligence pipeline fully robust, production-grade, and compliant with all edge cases described in the Tech Challenge problem statement.

## 1. Synchronized Multi-Camera Processing (The Core Fix)
Currently, videos are processed one after another. Because they are processed sequentially, a person who appears in Video 1 and Video 2 concurrently (in real life) will have their timeline distorted.
- **Action**: Refactor `detect.py` to open `cv2.VideoCapture` for all 5 videos simultaneously.
- **Action**: Loop through frames in lockstep (read 1 frame from each camera per iteration).
- **Benefit**: This perfectly mimics a real NVR (Network Video Recorder) and ensures ReID and Zone tracking happen chronologically, which is critical for accurate cross-camera tracking.

## 2. Ghost Track & Flicker Mitigation
YOLO sometimes detects a mannequin or a poster as a person, or a bounding box flickers for a fraction of a second.
- **Action**: Introduce a **Minimum Lifespan Filter**: A track must be seen for at least 15 frames (~1 second) before it is recognized as a valid visitor.
- **Action**: Add a **Minimum Confidence Threshold**: Ignore YOLO detections below 0.5 confidence.
- **Benefit**: Prevents polluting the database with false positives.

## 3. API & Ingestion Resilience
If the FastAPI server blips or Postgres locks, the `replay.py` script will drop data.
- **Action**: Add exponential backoff and retry logic using the `tenacity` library or a custom retry loop to ensure 100% of JSONL events are delivered safely.
- **Benefit**: Guarantees idempotent, reliable ingestion.

## 4. Cross-Camera State Separation
If a visitor is standing in the overlap between `CAM_FLOOR_01` (Skincare) and `CAM_FLOOR_02` (Fragrance), they will emit conflicting zone events.
- **Action**: Track `state["zone"]` separately for each camera inside the visitor's state dictionary to prevent "zone flickering" when they stand in camera overlaps.
- **Benefit**: Ensures clean dwell time analytics without noisy transition spam.
