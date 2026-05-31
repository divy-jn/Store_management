import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from shapely.geometry import Point, Polygon

class ZoneClassifier:
    """
    Manages spatial zones within camera views and classifies points (e.g., bottom-center 
    of a bounding box) into zones.
    """
    def __init__(self, layout_path: str = "store_layout.json"):
        self.zones: Dict[str, Dict[str, Polygon]] = {}  # camera_id -> {zone_id: Polygon}
        self.zone_types: Dict[str, str] = {}  # zone_id -> zone_type
        self.store_id = "ST1008"
        self._load_layout(layout_path)

    def _load_layout(self, layout_path: str):
        path = Path(layout_path)
        if not path.exists():
            return
            
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        for store in data.get("stores", []):
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
        # Simple splits for 1920x1080
        if zone_id == "ENTRY":
            return Polygon([(400, 800), (1500, 800), (1500, 1080), (400, 1080)])
        elif zone_id == "BILLING":
            return Polygon([(0, 200), (800, 200), (800, 800), (0, 800)])
        elif zone_id == "SKINCARE":
            return Polygon([(0, 0), (960, 0), (960, 1080), (0, 1080)])
        elif zone_id == "MAKEUP":
            return Polygon([(960, 0), (1920, 0), (1920, 1080), (960, 1080)])
        else:
            # Default fallback covers entire screen
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
