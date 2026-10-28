"""
Movement Dynamics and Prolonged Inactivity Detector.
Computes frame differencing and optical motion inside regions of interest to detect
natural engagement, active gestures, or lethargic inactivity / slumber.
"""

import cv2
import numpy as np
from typing import Dict, Tuple
from config import config


class MovementDetector:
    def __init__(self):
        self.prev_rois: Dict[int, np.ndarray] = {}
        self.last_active_time: Dict[int, float] = {}
        self.inactivity_threshold_sec = config.engagement.inactivity_threshold_seconds

    def compute_motion(self, frame: np.ndarray, track_id: int, bbox: Tuple[int, int, int, int], timestamp: float) -> Dict[str, float]:
        """
        Computes motion score (0.0 to 1.0) and inactivity duration for a specific tracked target.
        """
        x, y, w, h = bbox
        # Expand region slightly to capture upper torso and head movement
        pad_x = int(w * 0.2)
        pad_y = int(h * 0.4)
        
        y1 = max(0, y - pad_y)
        y2 = min(frame.shape[0], y + h + pad_y)
        x1 = max(0, x - pad_x)
        x2 = min(frame.shape[1], x + w + pad_x)
        
        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            return {"motion_score": 0.5, "inactivity_seconds": 0.0, "is_inactive": False}

        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        gray_roi = cv2.GaussianBlur(gray_roi, (15, 15), 0)

        # Initialize previous frame reference
        if track_id not in self.prev_rois:
            self.prev_rois[track_id] = cv2.resize(gray_roi, (100, 100))
            self.last_active_time[track_id] = timestamp
            return {"motion_score": 0.6, "inactivity_seconds": 0.0, "is_inactive": False}

        # Compare with previous frame
        curr_resized = cv2.resize(gray_roi, (100, 100))
        diff = cv2.absdiff(self.prev_rois[track_id], curr_resized)
        self.prev_rois[track_id] = curr_resized

        # Mean pixel variation
        mean_diff = float(np.mean(diff))

        # Normalize to 0.0 - 1.0 (mean_diff usually ranges 1.0 to 30.0 for classroom motion)
        # 3.0 to 18.0 is optimal active range (note taking, small shifts)
        # < 1.5 is static/frozen
        # > 35.0 is extreme fidgeting / abrupt change
        if mean_diff < 1.2:
            motion_score = 0.25  # Inactive
        elif mean_diff <= 15.0:
            # Linear scale for natural active listening / writing
            motion_score = 0.5 + min(0.45, (mean_diff / 15.0) * 0.45)
        else:
            # High motion (hand raise, adjustment, or fidget)
            motion_score = max(0.4, 0.95 - ((mean_diff - 15.0) / 40.0) * 0.3)

        # Track inactivity duration
        if mean_diff > 2.0:
            self.last_active_time[track_id] = timestamp
            inactivity_duration = 0.0
        else:
            inactivity_duration = timestamp - self.last_active_time.get(track_id, timestamp)

        is_inactive = inactivity_duration >= self.inactivity_threshold_sec

        return {
            "motion_score": round(float(motion_score), 2),
            "inactivity_seconds": round(float(inactivity_duration), 1),
            "is_inactive": is_inactive
        }
