"""
ClassMind AI - Deterministic Synthetic Classroom Simulator.
Generates photorealistic frames and audio signals with deterministic pedagogical scenarios,
arrival/departure events, trend transitions, and sensor fault simulation.
"""

import math
import random
import cv2
import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from config import config


class SimulatedStudent:
    def __init__(
        self,
        student_id: str,
        name: str,
        roll_no: str,
        center_x: int,
        base_y: int,
        default_behavior: str = "attentive",
        arrival_time_sec: float = 0.0,
        departure_time_sec: float = 9999.0
    ):
        self.student_id = student_id
        self.name = name
        self.roll_no = roll_no
        self.center_x = center_x
        self.base_y = base_y
        self.default_behavior = default_behavior
        self.arrival_time_sec = arrival_time_sec
        self.departure_time_sec = departure_time_sec


class DeterministicClassroomSimulator:
    """
    Simulates a smart classroom environment without requiring any physical camera or microphone.
    Features deterministic pedagogical phases:
    1. Introduction & Normal Lecture
    2. Extended Monologue (>90s speech)
    3. Interactive Discussion / Q&A
    4. Attention Drop & Looking Down
    5. Inactivity & Lethargy
    6. Sensor Glitch / Missing Sensor
    """

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)
        self.sample_rate = 16000
        self.width = config.video_width
        self.height = config.video_height

        # Classroom roster with varied desks and schedules
        self.students = [
            SimulatedStudent("S101", "Alex Johnson", "2024-CS-01", 130, 310, "attentive", arrival_time_sec=0.0),
            SimulatedStudent("S102", "Elena Rodriguez", "2024-CS-02", 320, 305, "notes", arrival_time_sec=0.0),
            SimulatedStudent("S103", "Marcus Chen", "2024-CS-03", 510, 315, "fidget", arrival_time_sec=0.0),
            SimulatedStudent("S104", "Sarah Williams", "2024-CS-04", 220, 370, "attentive", arrival_time_sec=40.0), # Late arrival
            SimulatedStudent("S105", "Rohan Gupta", "2024-CS-05", 420, 370, "notes", arrival_time_sec=0.0, departure_time_sec=120.0), # Early departure
            SimulatedStudent("S106", "Amina Zahra", "2024-CS-06", 0, 0, "absent", arrival_time_sec=9999.0) # Absent student
        ]

        self.scenario_override: Optional[str] = None
        self.sensor_camera_connected: bool = True
        self.sensor_mic_connected: bool = True

    def set_scenario(self, scenario: Optional[str]):
        """Forces a specific scenario: 'attention_drop', 'monologue', 'interactive', 'inactivity', 'sensor_fault'"""
        self.scenario_override = scenario

    def get_current_phase(self, t: float) -> str:
        """Determines active pedagogical scenario phase based on elapsed session seconds."""
        if self.scenario_override:
            return self.scenario_override

        # 180-second repeating cycle of scenarios for thorough demonstrations
        cycle_t = t % 180.0
        if cycle_t < 30.0:
            return "normal_lecture"
        elif cycle_t < 65.0:
            return "extended_monologue"
        elif cycle_t < 100.0:
            return "high_interaction"
        elif cycle_t < 135.0:
            return "attention_drop"
        elif cycle_t < 165.0:
            return "low_activity"
        else:
            return "sensor_glitch"

    def generate_frame(self, t: float, anonymize: bool = False) -> Tuple[np.ndarray, List[Dict[str, Any]], List[str]]:
        """
        Renders synthetic classroom frame with dynamic avatar postures, bounding boxes,
        and returns participants payload and list of active detected student IDs.
        """
        phase = self.get_current_phase(t)

        img = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        # Deep modern classroom background
        img[:] = (28, 24, 34)

        # Classroom blackboard / digital screen in background
        cv2.rectangle(img, (40, 20), (self.width - 40, 150), (38, 48, 44), -1)
        cv2.rectangle(img, (40, 20), (self.width - 40, 150), (60, 85, 75), 2)
        
        phase_label = phase.replace("_", " ").upper()
        cv2.putText(img, "CLASSMIND AI - SIMULATION LAB", (60, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (210, 240, 225), 2)
        cv2.putText(img, f"Active Scenario: {phase_label}", (60, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (120, 215, 175), 1)
        cv2.putText(img, f"Sim Elapsed: {int(t)}s | Seed: {self.seed}", (60, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (160, 185, 175), 1)

        # Simulation watermark banner
        cv2.rectangle(img, (self.width - 190, 28), (self.width - 48, 55), (20, 20, 28), -1)
        cv2.putText(img, "[SIMULATED]", (self.width - 180, 47), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (80, 190, 255), 1)

        participants_data = []
        detected_ids = []

        track_counter = 1
        for s in self.students:
            # Check student arrival and departure schedule
            if t < s.arrival_time_sec or t > s.departure_time_sec or s.center_x == 0:
                continue

            cx = s.center_x
            by = s.base_y

            # Determine behavior based on phase and avatar
            behavior = s.default_behavior
            if phase == "attention_drop":
                behavior = "phone"
            elif phase == "low_activity":
                behavior = "sleepy"
            elif phase == "high_interaction":
                behavior = "speaking" if s.student_id == "S101" else "attentive"

            # Avatar swaying & micro-motion
            if behavior == "sleepy":
                sway_x = 0
                sway_y = 2
                motion_score = 0.08
                is_inactive = True
                inactivity_sec = max(5.0, (t % 30.0))
            elif behavior == "speaking":
                sway_x = int(math.sin(t * 3.5 + cx) * 5)
                sway_y = int(math.cos(t * 3.0 + cx) * 4)
                motion_score = 0.88
                is_inactive = False
                inactivity_sec = 0.0
            else:
                sway_x = int(math.sin(t * 1.2 + cx) * 3)
                sway_y = int(math.cos(t * 1.5 + cx) * 2)
                motion_score = 0.55 if behavior != "fidget" else 0.78
                is_inactive = False
                inactivity_sec = 0.0

            face_cx = cx + sway_x
            face_cy = by + sway_y
            face_r = 38

            # Torso
            cv2.ellipse(img, (face_cx, face_cy + 85), (55, 45), 0, 0, 360, (65, 55, 75), -1)

            # Face head circle
            face_color = (190, 210, 235)
            cv2.circle(img, (face_cx, face_cy), face_r, face_color, -1)
            cv2.circle(img, (face_cx, face_cy), face_r, (140, 160, 190), 2)

            # Hair
            cv2.ellipse(img, (face_cx, face_cy - 16), (face_r, 22), 0, 180, 360, (45, 38, 42), -1)

            # Gaze & Head Pose estimation modeling
            eye_off_x = 0
            eye_off_y = 0
            yaw = 0.0
            pitch = 0.0
            attentive_score = 0.92
            pose_state = "Attentive"

            if behavior == "phone" or (behavior == "notes" and math.sin(t * 0.9) > 0.0):
                eye_off_y = 11
                pitch = -32.0
                attentive_score = 0.28
                pose_state = "Looking Down / Notes"
            elif behavior == "fidget" and math.cos(t * 0.7) > 0.2:
                eye_off_x = 12
                yaw = 35.0
                attentive_score = 0.35
                pose_state = "Turned Away"
            elif behavior == "sleepy":
                eye_off_y = 14
                pitch = -40.0
                attentive_score = 0.15
                pose_state = "Inattentive / Slumber"

            # Draw Eyes
            cv2.circle(img, (face_cx - 12 + eye_off_x, face_cy - 2 + eye_off_y), 4, (35, 35, 45), -1)
            cv2.circle(img, (face_cx + 12 + eye_off_x, face_cy - 2 + eye_off_y), 4, (35, 35, 45), -1)

            # Desk
            cv2.rectangle(img, (cx - 65, by + 90), (cx + 65, by + 135), (42, 38, 52), -1)
            cv2.rectangle(img, (cx - 65, by + 90), (cx + 65, by + 135), (65, 60, 75), 2)

            # Compute bounding box
            bw = face_r * 2 + 10
            bh = face_r * 2 + 16
            bx = face_cx - bw // 2
            by_box = face_cy - face_r - 6
            bbox = (bx, by_box, bw, bh)

            # Privacy Blur if enabled
            if anonymize:
                sub_face = img[max(0, by_box):min(self.height, by_box + bh), max(0, bx):min(self.width, bx + bw)]
                if sub_face.size > 0:
                    blurred = cv2.GaussianBlur(sub_face, (31, 31), 30)
                    img[max(0, by_box):min(self.height, by_box + bh), max(0, bx):min(self.width, bx + bw)] = blurred

            # Color-coded HUD Bounding Box
            if attentive_score >= 0.70:
                badge_col = (70, 215, 120)  # Green
            elif attentive_score >= 0.40:
                badge_col = (45, 185, 245)  # Orange
            else:
                badge_col = (75, 75, 235)   # Red

            cv2.rectangle(img, (bx, by_box), (bx + bw, by_box + bh), badge_col, 2)
            
            # Anonymous Track ID & Name tag
            cv2.rectangle(img, (bx, by_box - 24), (bx + bw + 20, by_box), (20, 20, 26), -1)
            label = f"#{track_counter} {s.name[:10]}"
            cv2.putText(img, label, (bx + 4, by_box - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.42, badge_col, 1)

            participants_data.append({
                "track_id": track_counter,
                "student_id": s.student_id,
                "display_name": s.name,
                "bbox": bbox,
                "state": pose_state,
                "yaw": yaw,
                "pitch": pitch,
                "attentiveness_score": attentive_score,
                "motion_score": motion_score,
                "is_inactive": is_inactive,
                "inactivity_seconds": inactivity_sec,
                "identity_matched": True,
                "attendance_verified": True
            })
            detected_ids.append(s.student_id)
            track_counter += 1

        return img, participants_data, detected_ids

    def generate_audio_chunk(self, t: float) -> Dict[str, Any]:
        """
        Synthesizes realistic classroom acoustics based on the active pedagogical phase.
        """
        phase = self.get_current_phase(t)
        chunk_samples = int(self.sample_rate * 0.5)

        # Background classroom acoustic noise floor
        noise = np.random.normal(0, 0.004, chunk_samples).astype(np.float32)

        if phase == "extended_monologue":
            # Instructor continuous monologue (>90 seconds uninterrupted)
            is_speech = True
            carrier = np.sin(2 * np.pi * 210 * np.linspace(0, 0.5, chunk_samples)) * 0.09
            carrier += np.sin(2 * np.pi * 420 * np.linspace(0, 0.5, chunk_samples)) * 0.05
            audio_wave = (carrier + noise).astype(np.float32)
            rms = float(np.sqrt(np.mean(audio_wave ** 2)))
            activity_score = 0.85
        elif phase == "high_interaction":
            # Active back-and-forth dialogue between instructor and students
            active_burst = (math.sin(t * 3.0) > -0.3)
            is_speech = active_burst
            if active_burst:
                carrier = np.sin(2 * np.pi * 320 * np.linspace(0, 0.5, chunk_samples)) * 0.11
                audio_wave = (carrier + noise).astype(np.float32)
                rms = float(np.sqrt(np.mean(audio_wave ** 2)))
                activity_score = 0.95
            else:
                rms = float(np.sqrt(np.mean(noise ** 2)))
                activity_score = 0.40
        elif phase == "attention_drop" or phase == "low_activity":
            # Low speech, awkward silence or whispered distraction
            is_speech = False
            rms = float(np.sqrt(np.mean(noise ** 2)))
            activity_score = 0.20
        elif phase == "sensor_glitch":
            # Audio sensor fault / disconnection
            return {
                "is_speech": False,
                "rms_energy": 0.0,
                "audio_activity_score": 0.0,
                "silence_seconds": 99.0,
                "speech_ratio": 0.0,
                "sensor_available": False
            }
        else:
            # Normal balanced lecture (speech bursts + natural pauses)
            is_speech = (math.sin(t * 0.8) > 0.1)
            if is_speech:
                carrier = np.sin(2 * np.pi * 230 * np.linspace(0, 0.5, chunk_samples)) * 0.07
                audio_wave = (carrier + noise).astype(np.float32)
                rms = float(np.sqrt(np.mean(audio_wave ** 2)))
                activity_score = 0.70
            else:
                rms = float(np.sqrt(np.mean(noise ** 2)))
                activity_score = 0.45

        return {
            "is_speech": is_speech,
            "rms_energy": round(rms, 4),
            "audio_activity_score": round(activity_score, 2),
            "silence_seconds": 0.0 if is_speech else round((t % 20.0), 1),
            "speech_ratio": 0.62 if is_speech else 0.35,
            "sensor_available": True
        }
