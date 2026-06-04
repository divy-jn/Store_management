# Purplle Store Intelligence - Architectural Choices

This document explains the rationale behind three core architectural decisions as required by the challenge prompt.

## 1. Detection Model Selection
**Options Considered**: Faster R-CNN, SSD, YOLOv5, YOLOv8, YOLOv10.
**What AI Suggested**: The AI (Claude/GPT-4) suggested using YOLOv8 or YOLOv10, noting that YOLOv8 has the best native integration with the `supervision` library for rapid prototyping, while YOLOv10 offers slight edge-inference speedups.
**What I Chose and Why**: I chose **YOLOv8s** (Small). Retail CCTV environments require a strict balance of speed (processing 3 streams simultaneously) and accuracy (crowded spaces with partial occlusion). I agreed with the AI's suggestion because YOLOv8s provides excellent mAP on COCO while running at >30 FPS on standard edge GPUs. Its seamless integration with ByteTrack via `supervision` allowed me to rapidly build the tracking logic and focus on the business constraints (like re-entry and queue depth) rather than debugging bounding box formats.

## 2. Event Schema Design Rationale
**Options Considered**: Deeply nested JSON (with all metadata in separate tables), Flat wide-column CSV-style schema, or a Hybrid structured/unstructured JSON schema.
**What AI Suggested**: The AI suggested a deeply normalized relational schema where `visitor_id`, `camera_id`, and `zone_id` were all foreign keys to separate SQL tables to maintain strict 3NF (Third Normal Form) database design.
**What I Chose and Why**: I **overrode** the AI and chose a **Hybrid Schema** (flat core fields + unstructured `metadata` JSONB column). In retail analytics, the types of metadata we want to capture evolve rapidly (e.g., today it's `queue_depth`, tomorrow it might be `gaze_direction` or `apparel_color`). By keeping the core fields (`event_type`, `visitor_id`, `timestamp`) strongly typed for fast funnel/heatmap JOINs, but leaving a `metadata` JSONB block for flexible event attributes, the pipeline is far more future-proof. 

## 3. API Architecture Choice (Real-time Metric Transport)
**Options Considered**: Client-side Polling (REST), Server-Sent Events (SSE), WebSockets.
**What AI Suggested**: The AI strongly recommended Server-Sent Events (SSE) for pushing the live dashboard metrics, arguing that since the dashboard only needs to *receive* data (not send it), WebSockets are overkill and SSE is lighter on connection state.
**What I Chose and Why**: I **overrode** the AI's recommendation and chose **WebSockets** (implemented in `app/websocket.py`). While SSE is lighter, the Live Dashboard feature (Part E) required a highly interactive "Live Demo" mode for the judges. By using WebSockets, I was able to implement a bidirectional control flow—allowing the backend to instantly signal `demo_completed` to the frontend, which triggers the UI to stop the stopwatch and fetch the final heavy Funnel/Heatmap data. This would have been significantly harder to coordinate cleanly with one-way SSE.
