"""
Head Pose and Visual Attentiveness Estimation.
Estimates yaw, pitch, and roll to quantify classroom visual engagement
(e.g., attentive vs. looking down at phone/desk vs. turned away).
"""

import cv2
import numpy as np
from typing import Dict, Tuple
from config import config


class HeadPoseEstimator:
    def __init__(self):
        # Built-in eye cascade for fine-grained landmark detection inside the face
        eye_cascade_path = cv2.data.haarcascades + "haarcascade_eye.xml"
        self.eye_cascade = cv2.CascadeClassifier(eye_cascade_path)
        self.yaw_tolerance = config.engagement.yaw_tolerance
        self.pitch_tolerance = config.engagement.pitch_tolerance

    def estimate_pose(self, frame: np.ndarray, bbox: Tuple[int, int, int, int]) -> Dict[str, float]:
        """
        Estimates yaw, pitch, and attentive confidence score for a detected face bounding box.
        Returns:
            {
                "yaw": float (-90 to +90 deg, negative=left, positive=right),
                "pitch": float (-90 to +90 deg, negative=down, positive=up),
                "attentiveness_score": float (0.0 to 1.0),
                "state": str ("Attentive", "Looking Down", "Looking Away")
            }
        """
        x, y, w, h = bbox
        face_roi = frame[max(0, y):max(0, y + h), max(0, x):max(0, x + w)]
        
        if face_roi.size == 0 or w < 20 or h < 20:
            return {
                "yaw": 0.0,
                "pitch": 0.0,
                "attentiveness_score": 0.5,
                "state": "Unknown"
            }

        gray_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        
        # Detect eyes in upper 65% of the face region
        upper_half = gray_face[:int(h * 0.65), :]
        eyes = self.eye_cascade.detectMultiScale(upper_half, scaleFactor=1.1, minNeighbors=3, minSize=(int(w*0.12), int(h*0.12)))

        yaw = 0.0
        pitch = 0.0

        if len(eyes) >= 2:
            # Sort eyes from left to right in the image
            eyes = sorted(eyes, key=lambda e: e[0])
            left_eye_center = (eyes[0][0] + eyes[0][2] // 2, eyes[0][1] + eyes[0][3] // 2)
            right_eye_center = (eyes[-1][0] + eyes[-1][2] // 2, eyes[-1][1] + eyes[-1][3] // 2)

            # Yaw: asymmetry of eye distance to facial midline
            face_center_x = w / 2.0
            dist_left = abs(face_center_x - left_eye_center[0])
            dist_right = abs(right_eye_center[0] - face_center_x)
            
            if (dist_left + dist_right) > 0:
                yaw_ratio = (dist_right - dist_left) / (dist_left + dist_right)
                yaw = float(yaw_ratio * 45.0)  # Approximate angle in degrees

            # Pitch: eye vertical position relative to expected eye level (normally ~0.35 - 0.40 h)
            avg_eye_y = (left_eye_center[1] + right_eye_center[1]) / 2.0
            expected_eye_y = h * 0.38
            pitch_offset = (avg_eye_y - expected_eye_y) / h
            pitch = float(pitch_offset * 60.0)
        elif len(eyes) == 1:
            # Single eye visible suggests head turned sideways
            eye_x = eyes[0][0] + eyes[0][2] // 2
            if eye_x < w / 2:
                yaw = -35.0
            else:
                yaw = 35.0
        else:
            # No eyes detected (looking down significantly or occluded)
            pitch = -30.0

        # Calculate attentiveness score
        abs_yaw = abs(yaw)
        abs_pitch = abs(pitch)

        yaw_penalty = min(1.0, abs_yaw / self.yaw_tolerance) if abs_yaw > 12.0 else 0.0
        pitch_penalty = min(1.0, abs_pitch / self.pitch_tolerance) if abs_pitch > 10.0 else 0.0

        attentiveness = max(0.05, 1.0 - (0.6 * yaw_penalty + 0.4 * pitch_penalty))

        # Categorize state
        if abs_yaw > self.yaw_tolerance:
            state = "Looking Away"
        elif pitch < -self.pitch_tolerance or (len(eyes) == 0 and pitch < -15.0):
            state = "Looking Down / Phone"
        elif abs_pitch > self.pitch_tolerance:
            state = "Looking Up / Distracted"
        else:
            state = "Attentive"

        return {
            "yaw": round(yaw, 1),
            "pitch": round(pitch, 1),
            "attentiveness_score": round(attentiveness, 2),
            "state": state
        }
