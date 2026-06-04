import json
from pathlib import Path
from typing import Dict, Optional

from shapely.geometry import Point, Polygon


class ZoneClassifier:
    """
    Manages spatial zones within camera views and classifies points (e.g., bottom-center
    of a bounding box) into zones.
    """

    def __init__(self, layout_path: str = "store_layout.json", store_id: str = None):
        self.zones: Dict[str, Dict[str, Polygon]] = {}
        self.zone_types: Dict[str, str] = {}
        self.store_id = store_id
        self._load_layout(layout_path)

    def _load_layout(self, layout_path: str):
        path = Path(layout_path)
        if not path.exists():
            return

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for store in data.get("stores", []):
            if self.store_id and store.get("store_id") != self.store_id:
                continue
            if not self.store_id:
                self.store_id = store.get("store_id")
            for zone in store.get("zones", []):
                z_id = zone.get("zone_id")
                z_type = zone.get("zone_type")
                self.zone_types[z_id] = z_type

                # In a real scenario, polygon coordinates would be in the JSON.
                # Since we lack them, we'll assign full-screen or logical split polygons
                # based on the cameras covering them.
                for cam_id in zone.get("camera_ids", []):
                    if cam_id not in self.zones:
                        self.zones[cam_id] = {}

                    # Create default dummy polygons covering parts of the screen
                    # For a real implementation, we'd read `polygon` from the JSON.
                    # Coordinates are arbitrary [x, y] mapped to 1920x1080 resolution.
                    poly = self._generate_dummy_polygon(cam_id, z_id)
                    self.zones[cam_id][z_id] = poly

    def _generate_dummy_polygon(self, camera_id: str, zone_id: str) -> Polygon:
        """Fallback function to generate dummy polygons if none exist in JSON."""
        # Generic fallback covers entire screen since real coordinates would be provided
        # by a UI or setup tool in `store_layout.json`
        return Polygon([(0, 0), (1920, 0), (1920, 1080), (0, 1080)])

    def get_zone_for_point(self, camera_id: str, x: float, y: float) -> Optional[str]:
        """
        Returns the zone_id that the point (x,y) falls into for a given camera.
        If it falls in multiple (overlapping), returns the first match.
        """
        if camera_id not in self.zones:
            return None

        pt = Point(x, y)
        for zone_id, polygon in self.zones[camera_id].items():
            if polygon.contains(pt):
                return zone_id

        return None
