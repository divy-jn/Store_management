import supervision as sv


class ByteTrackWrapper:
    """
    Wrapper for ByteTrack (Multi-Object Tracking) using the supervision library.
    It links YOLO bounding boxes across frames to assign consistent track IDs.
    """

    def __init__(self, fps: int = 15):
        # Initialize ByteTrack
        # track_thresh, track_buffer, match_thresh can be tuned for better retail environment tracking
        self.tracker = sv.ByteTrack(
            track_activation_threshold=0.25,
            lost_track_buffer=fps * 5,  # keep track for 5 seconds of occlusion
            minimum_matching_threshold=0.8,
            frame_rate=fps,
        )

    def update(self, detections: sv.Detections) -> sv.Detections:
        """
        Update tracker with current frame detections.
        Returns supervision Detections object augmented with tracker_id.
        """
        tracked_detections = self.tracker.update_with_detections(detections=detections)
        return tracked_detections
