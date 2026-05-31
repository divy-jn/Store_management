import cv2
import numpy as np

class StaffDetector:
    """
    Detects if a person is a staff member based on their uniform color.
    Assumes staff uniform is predominantly black/dark or purple based on Purplle branding.
    """
    def __init__(self):
        # HSV color ranges for staff uniform (e.g. Black / Dark Gray and Purple)
        # Purplle brand purple is roughly H: 270-300
        self.purple_lower = np.array([125, 50, 50])
        self.purple_upper = np.array([155, 255, 255])
        
        # Black / dark color
        self.black_lower = np.array([0, 0, 0])
        self.black_upper = np.array([180, 255, 50])

    def is_staff(self, frame: np.ndarray, bbox: tuple[int, int, int, int]) -> bool:
        """
        Crop the person from the frame, convert to HSV, and check for staff colors.
        Returns True if staff uniform is detected.
        """
        x1, y1, x2, y2 = map(int, bbox)
        
        # Add safety checks for bounds
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        
        if x2 <= x1 or y2 <= y1:
            return False
            
        crop = frame[y1:y2, x1:x2]
        
        # Focus on upper body (top 50% of the bounding box)
        crop_h = crop.shape[0]
        upper_body = crop[0:int(crop_h * 0.5), :]
        
        if upper_body.size == 0:
            return False
            
        hsv = cv2.cvtColor(upper_body, cv2.COLOR_BGR2HSV)
        
        # Check purple mask
        mask_purple = cv2.inRange(hsv, self.purple_lower, self.purple_upper)
        # Check black mask
        mask_black = cv2.inRange(hsv, self.black_lower, self.black_upper)
        
        # Combine masks
        mask = cv2.bitwise_or(mask_purple, mask_black)
        
        # Calculate percentage of staff color in upper body
        total_pixels = upper_body.shape[0] * upper_body.shape[1]
        staff_pixels = cv2.countNonZero(mask)
        
        ratio = staff_pixels / total_pixels if total_pixels > 0 else 0
        
        # If > 30% of upper body is uniform color, classify as staff
        return ratio > 0.30
