"""
Unified Multimodal Pipeline Orchestrator.
Coordinates computer vision, audio processing, sustained presence attendance,
engagement fusion, and the teaching advisor agent.
Supports Live Webcam, Pre-recorded Video, and Synthetic Classroom Simulation.
"""

import time
import math
import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple

from config import config
from src.vision.face_tracker import FaceTracker
from src.vision.head_pose import HeadPoseEstimator
from src.vision.movement_detector import MovementDetector
from src.vision.face_recognizer import OfflineFaceRecognizer
from src.audio.vad_processor import AudioVADProcessor
from src.audio.interaction_tracker import InteractionTracker
from src.attendance.sustained_presence import SustainedPresenceEngine
from src.fusion.engagement_engine import MultimodalEngagementEngine
from src.agent.teaching_advisor import TeachingAdvisorAgent


class ClassroomPipeline:
    def __init__(self, session_id: str = "SESSION-LIVE-01", video_source: any = 0):
        self.session_id = session_id
        self.video_source = video_source
        self.is_running = False
        self.cap: Optional[cv2.VideoCapture] = None
        self.use_simulation = False

        # Core Engines
        self.face_tracker = FaceTracker()
        self.head_pose_estimator = HeadPoseEstimator()
        self.movement_detector = MovementDetector()
        self.face_recognizer = OfflineFaceRecognizer()
        self.audio_processor = AudioVADProcessor()
        self.interaction_tracker = InteractionTracker()
        self.attendance_engine = SustainedPresenceEngine(session_id)
        self.engagement_engine = MultimodalEngagementEngine(session_id)
        self.teaching_advisor = TeachingAdvisorAgent(session_id)

        # State cache
        self.latest_telemetry: Dict[str, any] = {}
        self.latest_interaction: Dict[str, any] = {}
        self.last_frame_time = time.time()
        self.simulation_step = 0.0

        self._init_video_capture()

    def _init_video_capture(self):
        """Initializes OpenCV video capture or switches to simulator if no physical camera found."""
        try:
            self.cap = cv2.VideoCapture(self.video_source)
            if not self.cap.isOpened():
                print("[Pipeline] No physical video feed opened. Activating Classroom Simulator Mode.")
                self.use_simulation = True
            else:
                ret, test_frame = self.cap.read()
                if not ret or test_frame is None:
                    print("[Pipeline] Unable to read from camera. Activating Classroom Simulator Mode.")
                    self.use_simulation = True
                else:
                    print("[Pipeline] Successfully connected to live video capture.")
        except Exception as e:
            print(f"[Pipeline] Video init exception: {e}. Activating Classroom Simulator Mode.")
            self.use_simulation = True

    def set_simulation_mode(self, enabled: bool):
        self.use_simulation = enabled
        if not enabled:
            self._init_video_capture()

    def generate_simulated_frame(self, t: float) -> np.ndarray:
        """
        Generates a photorealistic synthetic classroom scene with 3 dynamic student avatars
        displaying varied head movements, note-taking, and periodic attention shifts.
        Ensures the system can be thoroughly demonstrated without requiring a live camera.
        """
        w, h = 640, 480
        # Dark modern classroom background gradient
        img = np.zeros((h, w, 3), dtype=np.uint8)
        img[:] = (35, 30, 40)
        
        # Classroom blackboard / digital screen in background
        cv2.rectangle(img, (50, 30), (590, 160), (45, 55, 50), -1)
        cv2.rectangle(img, (50, 30), (590, 160), (80, 100, 90), 2)
        cv2.putText(img, "LECTURE: MULTIMODAL INTELLIGENCE", (70, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (200, 230, 210), 2)
        cv2.putText(img, "Topic: Real-Time Signal Fusion & Edge AI", (70, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 190, 170), 1)

        # 3 Student Desks & Avatars
        # Student 1: Alex Johnson (Attentive, occasional nod)
        # Student 2: Elena Rodriguez (Notes / Looking down periodically)
        # Student 3: Marcus Chen (Looking away or transient presence)
        students_sim = [
            {"center_x": 140, "base_y": 320, "name": "Alex Johnson", "behavior": "attentive"},
            {"center_x": 320, "base_y": 310, "name": "Elena Rodriguez", "behavior": "notes"},
            {"center_x": 500, "base_y": 320, "name": "Marcus Chen", "behavior": "fidget"}
        ]

        for s in students_sim:
            cx = s["center_x"]
            by = s["base_y"]
            
            # Subtle natural breathing / movement sway
            sway_x = int(math.sin(t * 1.2 + cx) * 3)
            sway_y = int(math.cos(t * 1.5 + cx) * 2)

            # Torso
            cv2.ellipse(img, (cx + sway_x, by + 90 + sway_y), (60, 50), 0, 0, 360, (70, 60, 80), -1)
            # Head (Face)
            face_cy = by + sway_y
            cv2.circle(img, (cx + sway_x, face_cy), 42, (185, 205, 235), -1)
            cv2.circle(img, (cx + sway_x, face_cy), 42, (140, 160, 190), 2)

            # Hair
            cv2.ellipse(img, (cx + sway_x, face_cy - 18), (42, 26), 0, 180, 360, (50, 40, 45), -1)

            # Dynamic eyes and nose based on simulated behavior
            eye_offset_x = 0
            eye_offset_y = 0
            if s["behavior"] == "notes" and (math.sin(t * 0.8) > 0.1):
                # Looking down at desk
                eye_offset_y = 12
            elif s["behavior"] == "fidget" and (math.cos(t * 0.6) > 0.3):
                # Looking sideways / away
                eye_offset_x = 14

            # Eyes
            cv2.circle(img, (cx + sway_x - 14 + eye_offset_x, face_cy - 2 + eye_offset_y), 5, (40, 40, 50), -1)
            cv2.circle(img, (cx + sway_x + 14 + eye_offset_x, face_cy - 2 + eye_offset_y), 5, (40, 40, 50), -1)
            
            # Desk
            cv2.rectangle(img, (cx - 75, by + 100), (cx + 75, by + 150), (45, 40, 55), -1)
            cv2.rectangle(img, (cx - 75, by + 100), (cx + 75, by + 150), (70, 65, 80), 2)

        return img

    def process_frame(self) -> Tuple[np.ndarray, Dict[str, any]]:
        """
        Core pipeline execution loop for a single frame.
        Processes vision + audio, updates attendance & engagement, generates recommendations.
        """
        now = time.time()
        dt = max(0.01, min(0.5, now - self.last_frame_time))
        self.last_frame_time = now
        self.simulation_step += dt

        # 1. Grab Frame
        frame = None
        if not self.use_simulation and self.cap is not None and self.cap.isOpened():
            ret, captured = self.cap.read()
            if ret and captured is not None:
                frame = cv2.resize(captured, (config.video_width, config.video_height))
            else:
                frame = self.generate_simulated_frame(self.simulation_step)
        else:
            frame = self.generate_simulated_frame(self.simulation_step)

        # 2. Audio Processing & VAD
        audio_data = self.audio_processor.process_chunk(now)
        interaction_data = self.interaction_tracker.update(audio_data["is_speech"], dt)
        self.latest_interaction = interaction_data

        # 3. Vision Detection & Tracking
        tracked_faces = self.face_tracker.detect_and_track(frame, now)
        participants_payload = []
        detected_student_ids = []

        # Annotate & analyze each participant
        for face in tracked_faces:
            x, y, w, h = face.bbox
            
            # Head pose estimation
            pose = self.head_pose_estimator.estimate_pose(frame, face.bbox)
            face.head_pose = pose

            # Motion & inactivity detection
            motion = self.movement_detector.compute_motion(frame, face.track_id, face.bbox, now)
            face.movement_score = motion["motion_score"]

            # Identity match
            face_crop = frame[max(0, y):max(0, y+h), max(0, x):max(0, x+w)]
            s_id, s_name, conf = self.face_recognizer.match_student(face_crop, face.track_id)
            face.assigned_student_id = s_id
            face.assigned_student_name = s_name
            face.confidence = conf
            detected_student_ids.append(s_id)

            participants_payload.append({
                "track_id": face.track_id,
                "student_id": s_id,
                "name": s_name,
                "attentiveness_score": pose["attentiveness_score"],
                "state": pose["state"],
                "motion_score": motion["motion_score"],
                "is_inactive": motion["is_inactive"],
                "inactivity_seconds": motion["inactivity_seconds"]
            })

            # Privacy Anonymization if enabled
            if config.privacy.anonymize_faces:
                frame = self.face_tracker.apply_privacy_blur(frame, face.bbox)

            # Draw HUD Overlays
            # Color code: Green (Attentive), Yellow (Looking Down), Red (Distracted/Away)
            if pose["state"] == "Attentive":
                badge_color = (60, 210, 110)  # Green
            elif pose["state"] == "Looking Down / Phone":
                badge_color = (40, 180, 240)  # Orange/Yellow
            else:
                badge_color = (70, 70, 235)   # Red

            # Bounding box
            cv2.rectangle(frame, (x, y), (x + w, y + h), badge_color, 2)
            
            # Label banner
            label = f"{s_name} [{pose['state']}]"
            score_txt = f"Attn: {int(pose['attentiveness_score'] * 100)}% | Yaw: {pose['yaw']} deg"
            cv2.rectangle(frame, (x, y - 28), (x + len(label) * 9 + 10, y), (20, 20, 25), -1)
            cv2.putText(frame, label, (x + 5, y - 9), cv2.FONT_HERSHEY_SIMPLEX, 0.45, badge_color, 1)
            cv2.putText(frame, score_txt, (x, y + h + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (230, 230, 230), 1)

        # 4. Scenario 1: Sustained Presence Attendance
        self.attendance_engine.process_frame_observations(detected_student_ids, now, dt)
        attendance_summary = self.attendance_engine.get_summary()

        # 5. Scenario 2: Multimodal Signal Fusion
        telemetry = self.engagement_engine.compute_engagement(participants_payload, audio_data, now)
        self.latest_telemetry = telemetry

        # 6. Scenario 3: AI-Driven Teaching Suggestions
        suggestion = self.teaching_advisor.evaluate_telemetry(telemetry, interaction_data, now)

        # Draw Global Dashboard Header Overlays on the live frame
        eng_color = (60, 210, 110) if telemetry["overall_engagement"] >= 65 else (
            (40, 180, 240) if telemetry["overall_engagement"] >= 45 else (70, 70, 235)
        )
        header_text = f"Classroom Engagement: {telemetry['overall_engagement']}% [{telemetry.get('trend', 'Steady')}]"
        cv2.rectangle(frame, (10, 10), (430, 44), (20, 20, 30), -1)
        cv2.putText(frame, header_text, (18, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.58, eng_color, 2)

        # Audio indicator in corner
        audio_txt = "Mic: SPEAKING" if audio_data["is_speech"] else f"Mic: SILENT ({audio_data['silence_seconds']}s)"
        mic_color = (100, 240, 150) if audio_data["is_speech"] else (180, 180, 180)
        cv2.putText(frame, audio_txt, (10, frame.shape[0] - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, mic_color, 1)

        pipeline_output = {
            "telemetry": telemetry,
            "interaction": interaction_data,
            "attendance": attendance_summary,
            "latest_suggestion": suggestion,
            "participants": participants_payload,
            "use_simulation": self.use_simulation
        }

        return frame, pipeline_output

    def get_jpeg_frame(self) -> bytes:
        """Encodes current processed frame as JPEG bytes for browser streaming."""
        frame, _ = self.process_frame()
        ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return buffer.tobytes() if ret else b""
