# Purplle Store Intelligence - Architectural Choices

This document explains the rationale behind the specific technologies and algorithms chosen for the Store Intelligence system.

## 1. Machine Learning Stack

### 1.1 Detection: YOLOv8s
**Alternatives Considered**: Faster R-CNN, SSD, YOLOv5, YOLOv10.
**Why YOLOv8s?**
- Retail CCTV environments require a balance of speed (to process multiple streams simultaneously) and accuracy (crowded spaces). 
- YOLOv8s (Small) provides excellent mAP on COCO while running at >30 FPS on standard edge GPUs (e.g., RTX 3060).
- It has native integration with `supervision`, reducing boilerplate code.

### 1.2 Tracking: ByteTrack
**Alternatives Considered**: DeepSORT, SORT, BoT-SORT.
**Why ByteTrack?**
- ByteTrack relies entirely on bounding box IoU and confidence scores, making it significantly faster than DeepSORT (which requires running a feature extractor on every frame).
- It handles low-confidence detections better by keeping them in active memory for short-term occlusion (e.g., a customer walking behind a shelf).

### 1.3 Re-Identification: ResNet18 (Proxy for OSNet)
**Alternatives Considered**: Full `torchreid` OSNet, Autoencoders.
**Why ResNet18?**
- While OSNet is the gold standard for Omni-Scale feature learning in ReID, deploying it requires complex C++ dependencies (`torchreid`).
- For the scope of this challenge, a pretrained ResNet18 model stripped of its classification head provides a sufficiently robust 512-dimensional embedding to track customers across cameras using cosine similarity.

## 2. Backend Stack

### 2.1 Web Framework: FastAPI
**Alternatives Considered**: Flask, Django, Express.js (Node).
**Why FastAPI?**
- **Async I/O**: Essential for handling thousands of incoming JSONL events per second and maintaining persistent WebSocket connections.
- **Pydantic**: Deep integration allows automatic, strict validation of the incoming event schema, saving dozens of lines of manual `if event['type'] not in ...` checks.
- **Performance**: Built on Starlette, it is one of the fastest Python frameworks available.

### 2.2 Database: PostgreSQL 16
**Alternatives Considered**: MongoDB, SQLite, TimescaleDB.
**Why PostgreSQL?**
- The project requires relational consistency (joining events by `visitor_id`) but also flexible metadata schemas (e.g., POS basket data, unknown event fields).
- PostgreSQL 16 handles structured relational data exceptionally well while offering `JSONB` columns for unstructured metadata.
- `UNIQUE` constraints guarantee idempotent event ingestion, satisfying the `scoring_harness` reliability requirement.

## 3. UI/UX: Vanilla HTML/JS with Glassmorphism
**Alternatives Considered**: React (Next.js), Vue.js, TailwindCSS.
**Why Vanilla JS/CSS?**
- To reduce build complexity (no `npm install`, no `webpack`) while maintaining a premium look.
- **Glassmorphism**: Provides a modern, premium, "Purplle-branded" aesthetic that wows the user, using pure CSS `backdrop-filter` and animated gradient meshes. 
- Chart.js provides lightweight, highly customizable charting out of the box.

## 4. Scalability & Production Considerations
- **Event Idempotency**: The API handles network retries gracefully. If the pipeline disconnects and resends an event, the API ignores the duplicate via `ON CONFLICT (event_id) DO NOTHING`.
- **Stateless API**: The FastAPI application is completely stateless (aside from the WebSocket pool), meaning we can easily scale horizontally by adding more containers behind an Nginx load balancer.
- **Background Tasks**: Currently, endpoints execute synchronously. In a true production environment, `app.ingestion` would push events to a message queue (e.g., Kafka or RabbitMQ) to be processed by background workers.
