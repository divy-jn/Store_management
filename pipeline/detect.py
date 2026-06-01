import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

import cv2
import supervision as sv
from emit import EventEmitter
from queue_tracker import QueueTracker
from reid import ReIDManager
from staff_detector import StaffDetector
from tracker import ByteTrackWrapper
from ultralytics import YOLO
from zone_classifier import ZoneClassifier

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
PIPELINE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PIPELINE_DIR.parent

# Periodic dwell emission interval in seconds (spec: every 30s of continuous presence)
DWELL_EMIT_INTERVAL_S = 30.0


class DetectionPipeline:
    def __init__(self, store_id: str, output_dir: str):
        self.store_id = store_id
        self.emitter = EventEmitter(store_id, output_dir)

        logger.info("Loading YOLOv8 model...")
        self.model = YOLO(str(PIPELINE_DIR / "yolov8s.pt"))

        self.zone_classifier = ZoneClassifier(str(PROJECT_ROOT / "store_layout.json"))
        self.staff_detector = StaffDetector()
        self.reid_manager = ReIDManager()
        self.queue_tracker = QueueTracker()

        # Track active visitor IDs assigned by ReID (global across cameras)
        self.track_to_visitor = {}  # {camera_id: {track_id: visitor_id}}

        # State of visitors:
        #   visitor_id -> {
        #       "is_staff": bool,
        #       cam_id: {"zone": str|None, "enter_time": float|None, "last_dwell_emit": float|None}
        #   }
        self.visitor_state = {}

        # Minimum lifespan logic (ghost track filter — based on track duration, NOT confidence)
        self.track_frames = {}  # {camera_id: {track_id: frame_count}}
        self.MIN_FRAMES_VALID = 15

        # Set of visitor_ids that have exited — used for REENTRY detection
        self.exited_visitors = set()

    def process_streams(self, video_paths: dict):
        """
        Process multiple video streams synchronously, frame-by-frame in lockstep.
        video_paths: {camera_id: video_path}
        """
        logger.info(f"Starting synchronized processing of {len(video_paths)} cameras.")

        caps = {}
        trackers = {}
        fps = 15

        for cam_id, path in video_paths.items():
            caps[cam_id] = cv2.VideoCapture(path)
            info = sv.VideoInfo.from_video_path(video_path=str(path))
            fps = min(fps, info.fps)
            trackers[cam_id] = ByteTrackWrapper(fps=fps)
            self.track_to_visitor[cam_id] = {}
            self.track_frames[cam_id] = {}

        clip_start_time = datetime.now(timezone.utc)
        frame_number = 0

        while True:
            frames = {}
            for cam_id, cap in caps.items():
                ret, frame = cap.read()
                if ret:
                    frames[cam_id] = frame

            if not frames:
                break

            frame_number += 1
            timestamp = self.emitter.calculate_timestamp(
                clip_start_time, frame_number, fps
            )

            for cam_id, frame in frames.items():
                # 1. YOLOv8 Inference (person class only)
                result = self.model(frame, classes=[0], verbose=False)[0]
                detections = sv.Detections.from_ultralytics(result)

                # NOTE: Per PDF spec, we do NOT suppress low-confidence detections.
                # The confidence score is passed through in the event payload for
                # downstream consumers to filter if needed.

                # 2. ByteTrack Update
                tracker = trackers[cam_id]
                tracked_detections = tracker.update(detections)

                active_tracks_current_frame = set()

                for i in range(len(tracked_detections)):
                    xyxy = tracked_detections.xyxy[i]
                    track_id = tracked_detections.tracker_id[i]
                    confidence = float(tracked_detections.confidence[i])

                    active_tracks_current_frame.add(track_id)

                    # Ghost track filter: track must exist for MIN_FRAMES_VALID frames
                    self.track_frames[cam_id][track_id] = (
                        self.track_frames[cam_id].get(track_id, 0) + 1
                    )
                    if self.track_frames[cam_id][track_id] < self.MIN_FRAMES_VALID:
                        continue

                    # ReID & Visitor State Initialization
                    if track_id not in self.track_to_visitor[cam_id]:
                        visitor_id = self.reid_manager.identify(frame, tuple(xyxy))
                        self.track_to_visitor[cam_id][track_id] = visitor_id

                        is_staff = self.staff_detector.is_staff(frame, tuple(xyxy))

                        if visitor_id not in self.visitor_state:
                            self.visitor_state[visitor_id] = {"is_staff": is_staff}

                        if cam_id not in self.visitor_state[visitor_id]:
                            self.visitor_state[visitor_id][cam_id] = {
                                "zone": None,
                                "enter_time": None,
                                "last_dwell_emit": None,
                            }

                        # Emit ENTRY or REENTRY only from the entrance camera
                        if cam_id == "CAM_ENTRY_01":
                            if visitor_id in self.exited_visitors:
                                # They've been seen exiting before — this is a re-entry
                                self.exited_visitors.discard(visitor_id)
                                self.emitter.emit(
                                    camera_id=cam_id,
                                    visitor_id=visitor_id,
                                    event_type="REENTRY",
                                    timestamp=timestamp,
                                    confidence=confidence,
                                    is_staff=is_staff,
                                )
                            else:
                                self.emitter.emit(
                                    camera_id=cam_id,
                                    visitor_id=visitor_id,
                                    event_type="ENTRY",
                                    timestamp=timestamp,
                                    confidence=confidence,
                                    is_staff=is_staff,
                                )

                    visitor_id = self.track_to_visitor[cam_id][track_id]
                    v_state = self.visitor_state[visitor_id]
                    cam_state = v_state[cam_id]
                    is_staff = v_state["is_staff"]

                    # 3. Spatial Logic
                    x_center = (xyxy[0] + xyxy[2]) / 2.0
                    y_bottom = xyxy[3]
                    current_zone = self.zone_classifier.get_zone_for_point(
                        cam_id, x_center, y_bottom
                    )

                    # Queue Logic
                    if current_zone == "BILLING" and cam_state["zone"] != "BILLING":
                        self.queue_tracker.update(visitor_id, "BILLING")
                        self.emitter.emit(
                            camera_id=cam_id,
                            visitor_id=visitor_id,
                            event_type="BILLING_QUEUE_JOIN",
                            timestamp=timestamp,
                            confidence=confidence,
                            zone_id="BILLING",
                            is_staff=is_staff,
                            metadata={
                                "queue_depth": self.queue_tracker.get_queue_depth()
                            },
                        )
                    elif cam_state["zone"] == "BILLING" and current_zone != "BILLING":
                        self.queue_tracker.remove(visitor_id)
                        self.emitter.emit(
                            camera_id=cam_id,
                            visitor_id=visitor_id,
                            event_type="BILLING_QUEUE_ABANDON",
                            timestamp=timestamp,
                            confidence=confidence,
                            zone_id="BILLING",
                            is_staff=is_staff,
                        )

                    # Zone Transitions
                    if current_zone != cam_state["zone"]:
                        # Exit previous zone
                        if cam_state["zone"]:
                            dwell = int(
                                (timestamp.timestamp() - cam_state["enter_time"]) * 1000
                            )
                            self.emitter.emit(
                                camera_id=cam_id,
                                visitor_id=visitor_id,
                                event_type="ZONE_DWELL",
                                timestamp=timestamp,
                                confidence=confidence,
                                zone_id=cam_state["zone"],
                                dwell_ms=dwell,
                                is_staff=is_staff,
                            )
                            self.emitter.emit(
                                camera_id=cam_id,
                                visitor_id=visitor_id,
                                event_type="ZONE_EXIT",
                                timestamp=timestamp,
                                confidence=confidence,
                                zone_id=cam_state["zone"],
                                is_staff=is_staff,
                            )

                        # Enter new zone
                        cam_state["zone"] = current_zone
                        cam_state["enter_time"] = (
                            timestamp.timestamp() if current_zone else None
                        )
                        cam_state["last_dwell_emit"] = (
                            timestamp.timestamp() if current_zone else None
                        )

                        if current_zone:
                            self.emitter.emit(
                                camera_id=cam_id,
                                visitor_id=visitor_id,
                                event_type="ZONE_ENTER",
                                timestamp=timestamp,
                                confidence=confidence,
                                zone_id=current_zone,
                                is_staff=is_staff,
                            )
                    else:
                        # Same zone — check if we need to emit a periodic 30s dwell
                        if (
                            cam_state["zone"]
                            and cam_state["last_dwell_emit"] is not None
                            and (timestamp.timestamp() - cam_state["last_dwell_emit"])
                            >= DWELL_EMIT_INTERVAL_S
                        ):
                            dwell = int(
                                (timestamp.timestamp() - cam_state["enter_time"]) * 1000
                            )
                            self.emitter.emit(
                                camera_id=cam_id,
                                visitor_id=visitor_id,
                                event_type="ZONE_DWELL",
                                timestamp=timestamp,
                                confidence=confidence,
                                zone_id=cam_state["zone"],
                                dwell_ms=dwell,
                                is_staff=is_staff,
                            )
                            cam_state["last_dwell_emit"] = timestamp.timestamp()

                # Detect Lost Tracks
                lost_tracks = (
                    set(self.track_to_visitor[cam_id].keys())
                    - active_tracks_current_frame
                )
                for track_id in list(lost_tracks):
                    visitor_id = self.track_to_visitor[cam_id][track_id]
                    v_state = self.visitor_state[visitor_id]
                    cam_state = v_state[cam_id]

                    if cam_state["zone"] == "BILLING":
                        self.queue_tracker.remove(visitor_id)

                    if cam_state["zone"]:
                        dwell = int(
                            (timestamp.timestamp() - cam_state["enter_time"]) * 1000
                        )
                        self.emitter.emit(
                            camera_id=cam_id,
                            visitor_id=visitor_id,
                            event_type="ZONE_DWELL",
                            timestamp=timestamp,
                            confidence=1.0,
                            zone_id=cam_state["zone"],
                            dwell_ms=dwell,
                            is_staff=v_state["is_staff"],
                        )

                    if cam_id == "CAM_ENTRY_01":
                        self.exited_visitors.add(visitor_id)
                        self.emitter.emit(
                            camera_id=cam_id,
                            visitor_id=visitor_id,
                            event_type="EXIT",
                            timestamp=timestamp,
                            confidence=1.0,
                            is_staff=v_state["is_staff"],
                        )

                    del self.track_to_visitor[cam_id][track_id]

        for cap in caps.values():
            cap.release()

        logger.info("Finished processing all streams synchronously.")


def main():
    parser = argparse.ArgumentParser(
        description="Purplle Store Intelligence Detection Pipeline"
    )
    parser.add_argument(
        "--input-dir", required=True, help="Directory containing CCTV video files"
    )
    parser.add_argument(
        "--output-dir", required=True, help="Directory to write JSONL events"
    )
    args = parser.parse_args()

    pipeline = DetectionPipeline(store_id="ST1008", output_dir=args.output_dir)

    input_path = Path(args.input_dir)
    if not input_path.exists():
        logger.error(f"Input directory not found: {input_path}")
        return

    videos = list(input_path.glob("*.mp4"))
    logger.info(f"Found {len(videos)} videos to process")

    cam_mapping = {
        "CAM 1 store inside.mp4": "CAM_FLOOR_01",
        "CAM 2 store inside 2nd angle.mp4": "CAM_FLOOR_02",
        "CAM3 entrance.mp4": "CAM_ENTRY_01",
        "CAM 4 internal area.mp4": "CAM_INTERNAL_01",
        "CAM 5 billing.mp4": "CAM_BILLING_01",
    }

    video_paths = {}
    for video in videos:
        cam_id = cam_mapping.get(video.name, "CAM_UNKNOWN")
        video_paths[cam_id] = str(video)

    if video_paths:
        pipeline.process_streams(video_paths)


if __name__ == "__main__":
    main()
