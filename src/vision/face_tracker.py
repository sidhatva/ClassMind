"""
Multi-target Face Tracker with privacy-preserving anonymization and ID tracking.
Uses OpenCV's built-in cascade/detection with centroid & IoU temporal tracking.
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional
from config import config


class TrackedFace:
    def __init__(self, track_id: int, bbox: Tuple[int, int, int, int], timestamp: float):
        self.track_id = track_id
        self.bbox = bbox  # (x, y, w, h)
        self.first_seen = timestamp
        self.last_seen = timestamp
        self.seen_count = 1
        self.assigned_student_id: Optional[str] = None
        self.assigned_student_name: Optional[str] = None
        self.is_sustained = False
        self.confidence: float = 0.90
        self.movement_score: float = 0.0
        self.head_pose: Dict[str, float] = {"yaw": 0.0, "pitch": 0.0, "attentive": 1.0}


class FaceTracker:
    def __init__(self):
        # Load OpenCV built-in frontal face cascade
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        self.next_track_id = 1
        self.tracked_faces: Dict[int, TrackedFace] = {}
        self.max_disappeared_seconds = 2.5
        self.min_face_size = config.attendance.min_face_size

    def _compute_iou(self, boxA: Tuple[int, int, int, int], boxB: Tuple[int, int, int, int]) -> float:
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[0] + boxA[2], boxB[0] + boxB[2])
        yB = min(boxA[1] + boxA[3], boxB[1] + boxB[3])

        interArea = max(0, xB - xA) * max(0, yB - yA)
        boxAArea = boxA[2] * boxA[3]
        boxBArea = boxB[2] * boxB[3]

        if boxAArea + boxBArea - interArea == 0:
            return 0.0
        return interArea / float(boxAArea + boxBArea - interArea)

    def detect_and_track(self, frame: np.ndarray, timestamp: float) -> List[TrackedFace]:
        """
        Detects faces in frame and updates continuous multi-target tracks.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Fast equalization for robust contrast handling
        gray = cv2.equalizeHist(gray)

        detections = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.15,
            minNeighbors=5,
            minSize=(self.min_face_size, self.min_face_size)
        )

        current_boxes = [tuple(d) for d in detections]
        updated_tracks: List[TrackedFace] = []
        matched_box_indices = set()
        matched_track_ids = set()

        # Match existing tracks using IoU & proximity
        for track_id, track in list(self.tracked_faces.items()):
            best_iou = 0.0
            best_idx = -1
            for idx, box in enumerate(current_boxes):
                if idx in matched_box_indices:
                    continue
                iou = self._compute_iou(track.bbox, box)
                if iou > best_iou:
                    best_iou = iou
                    best_idx = idx

            # If matched with sufficient overlap
            if best_iou > 0.25 and best_idx >= 0:
                track.bbox = current_boxes[best_idx]
                track.last_seen = timestamp
                track.seen_count += 1
                matched_box_indices.add(best_idx)
                matched_track_ids.add(track_id)
                updated_tracks.append(track)
            elif (timestamp - track.last_seen) < self.max_disappeared_seconds:
                # Keep active in track memory even if briefly occluded
                updated_tracks.append(track)
            else:
                # Expire stale track
                del self.tracked_faces[track_id]

        # Register new faces
        for idx, box in enumerate(current_boxes):
            if idx not in matched_box_indices:
                new_track = TrackedFace(self.next_track_id, box, timestamp)
                self.tracked_faces[self.next_track_id] = new_track
                updated_tracks.append(new_track)
                self.next_track_id += 1

        return updated_tracks

    def apply_privacy_blur(self, frame: np.ndarray, bbox: Tuple[int, int, int, int]) -> np.ndarray:
        """Blurs the face area if anonymization is enabled."""
        if frame is None or frame.size == 0:
            return frame
        f_h, f_w = frame.shape[:2]
        x, y, w, h = bbox
        x1, y1 = max(0, int(x)), max(0, int(y))
        x2, y2 = min(f_w, int(x + w)), min(f_h, int(y + h))
        if x2 > x1 and y2 > y1:
            sub_face = frame[y1:y2, x1:x2]
            kw = min(31, (x2 - x1) | 1)
            kh = min(31, (y2 - y1) | 1)
            if kw >= 3 and kh >= 3:
                blurred = cv2.GaussianBlur(sub_face, (kw, kh), 30)
                frame[y1:y2, x1:x2] = blurred
        return frame
