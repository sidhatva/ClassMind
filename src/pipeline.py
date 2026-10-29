"""
ClassMind AI - Unified Multimodal Pipeline Orchestrator.
Coordinates computer vision, acoustic processing, temporal attendance verification,
multimodal engagement fusion, and pedagogical decision support.
Supports live hardware devices and deterministic synthetic simulation.
"""

import sys
import time
import math
import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import threading

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
from src.simulation.classroom_simulator import DeterministicClassroomSimulator


class ClassroomPipeline:
    def __init__(self, session_id: str = "SESSION-LIVE-01", video_source: Any = 0, force_simulation: bool = False):
        self.session_id = session_id
        self.video_source = video_source
        self.is_running = True
        self.is_paused = False
        self.cap: Optional[cv2.VideoCapture] = None
        self.use_simulation = force_simulation
        self.camera_error: Optional[str] = None
        self.lock = threading.Lock()

        # Deterministic simulation engine
        self.simulator = DeterministicClassroomSimulator(seed=42)

        # Core Analysis Engines
        self.face_tracker = FaceTracker()
        self.head_pose_estimator = HeadPoseEstimator()
        self.movement_detector = MovementDetector()
        self.face_recognizer = OfflineFaceRecognizer()
        self.audio_processor = AudioVADProcessor()
        self.interaction_tracker = InteractionTracker()
        self.attendance_engine = SustainedPresenceEngine(session_id)
        self.engagement_engine = MultimodalEngagementEngine(session_id)
        self.teaching_advisor = TeachingAdvisorAgent(session_id)

        # Performance & telemetry metrics
        self.latest_telemetry: Dict[str, Any] = {}
        self.latest_interaction: Dict[str, Any] = {}
        self.latest_frame: Optional[np.ndarray] = None
        self.latest_jpeg_bytes: bytes = b""
        self.latest_output: Dict[str, Any] = {}
        self.last_frame_time = time.time()
        self.simulation_step = 0.0
        self.fps = float(config.fps_target or 24.0)
        self.inference_latency_ms = 12.0
        self.frame_count = 0
        self.target_fps = float(config.fps_target or 24.0)

        # Initialize video hardware if not forcing simulation
        if not self.use_simulation:
            self._init_video_capture()

        # Generate initial frame and telemetry immediately
        try:
            self._step_pipeline()
        except Exception as e:
            print(f"[Pipeline] Initial step error: {e}")

        # Start continuous background processing thread (Single Producer)
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="ClassroomPipelineWorker"
        )
        self.worker_thread.start()

    def _release_camera(self):
        """Safely releases active video capture hardware."""
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception as e:
                print(f"[Pipeline] Error releasing camera: {e}")
            self.cap = None

    def _init_video_capture(self):
        """Initializes physical camera capture with graceful fallback to simulator if unavailable."""
        self._release_camera()

        # On Windows, DirectShow (CAP_DSHOW) opens webcams fast and reliably
        backends = []
        if sys.platform.startswith("win"):
            backends = [cv2.CAP_DSHOW, cv2.CAP_ANY]
        else:
            backends = [cv2.CAP_ANY]

        success = False
        last_error = None

        for backend in backends:
            try:
                cap = (
                    cv2.VideoCapture(self.video_source, backend)
                    if backend != cv2.CAP_ANY
                    else cv2.VideoCapture(self.video_source)
                )
                if cap is not None and cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.video_width)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.video_height)
                    ret, test_frame = cap.read()
                    if ret and test_frame is not None:
                        self.cap = cap
                        self.use_simulation = False
                        self.camera_error = None
                        print(f"[Pipeline] Successfully connected to live video capture (source #{self.video_source}, backend: {backend}).")
                        success = True
                        break
                    else:
                        cap.release()
                elif cap is not None:
                    cap.release()
            except Exception as e:
                last_error = str(e)

        if not success:
            self.cap = None
            self.use_simulation = True
            self.camera_error = f"Webcam #{self.video_source} not accessible ({last_error or 'device busy or unavailable'})."
            print(f"[Pipeline] {self.camera_error} Activating Simulation Mode.")

    def set_simulation_mode(self, enabled: bool):
        with self.lock:
            if enabled:
                self.use_simulation = True
                self._release_camera()
                self.camera_error = None
                print("[Pipeline] Switched to Simulation Mode.")
            else:
                self.use_simulation = False
                self._init_video_capture()
        try:
            self._step_pipeline()
        except Exception:
            pass

    def set_paused(self, paused: bool):
        with self.lock:
            self.is_paused = paused
        try:
            self._step_pipeline()
        except Exception:
            pass

    def _worker_loop(self):
        """Continuous background execution loop maintaining target frame rate."""
        interval = 1.0 / max(1.0, self.target_fps)
        while self.is_running:
            t0 = time.perf_counter()
            try:
                self._step_pipeline()
            except Exception as e:
                print(f"[Pipeline] Worker iteration exception: {e}")
            elapsed = time.perf_counter() - t0
            sleep_time = max(0.005, interval - elapsed)
            time.sleep(sleep_time)

    def _step_pipeline(self) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Executes one full pipeline cycle:
        Vision + Audio -> Temporal Attendance -> Engagement Fusion -> Teaching Copilot -> HUD & JPEG.
        Must be thread-safe.
        """
        start_proc = time.perf_counter()
        now = time.time()
        dt = max(0.01, min(0.5, now - self.last_frame_time))
        self.last_frame_time = now
        self.simulation_step += dt

        if self.is_paused:
            pause_frame = np.zeros((config.video_height, config.video_width, 3), dtype=np.uint8)
            pause_frame[:] = (30, 25, 35)
            cv2.putText(pause_frame, "SESSION PAUSED", (config.video_width // 2 - 130, config.video_height // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.85, (100, 200, 255), 2)
            cv2.putText(pause_frame, "Monitoring suspended", (config.video_width // 2 - 95, config.video_height // 2 + 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, (180, 180, 180), 1)
            summary = self.attendance_engine.get_summary()
            pipeline_output = {
                "telemetry": self.latest_telemetry or {},
                "interaction": self.latest_interaction or {},
                "attendance": summary,
                "latest_suggestion": None,
                "participants": [],
                "use_simulation": self.use_simulation,
                "is_paused": True,
                "fps": round(self.fps, 1),
                "latency_ms": round(self.inference_latency_ms, 1),
                "camera_error": self.camera_error
            }
            ret, buf = cv2.imencode(".jpg", pause_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            with self.lock:
                self.latest_frame = pause_frame
                if ret:
                    self.latest_jpeg_bytes = buf.tobytes()
                self.latest_output = pipeline_output
            return pause_frame, pipeline_output

        # 1. Video Capture / Synthetic Frame
        frame = None
        participants_payload = []
        detected_student_ids = []

        if not self.use_simulation and self.cap is not None and self.cap.isOpened():
            ret, captured = self.cap.read()
            if ret and captured is not None:
                frame = cv2.resize(captured, (config.video_width, config.video_height))
                # Real computer vision processing
                tracked_faces = self.face_tracker.detect_and_track(frame, now)
                for face in tracked_faces:
                    x, y, w, h = face.bbox
                    pose = self.head_pose_estimator.estimate_pose(frame, face.bbox)
                    motion = self.movement_detector.compute_motion(frame, face.track_id, face.bbox, now)

                    f_h, f_w = frame.shape[:2]
                    face_crop = frame[max(0, y):min(f_h, y+h), max(0, x):min(f_w, x+w)]
                    s_id, s_name, conf, is_matched = self.face_recognizer.match_student(face_crop, face.track_id)
                    if s_id:
                        detected_student_ids.append(s_id)

                    participants_payload.append({
                        "track_id": face.track_id,
                        "student_id": s_id,
                        "display_name": s_name,
                        "state": pose["state"],
                        "attentiveness_score": pose["attentiveness_score"],
                        "motion_score": motion["motion_score"],
                        "is_inactive": motion["is_inactive"],
                        "inactivity_seconds": motion["inactivity_seconds"],
                        "identity_matched": is_matched,
                        "attendance_verified": is_matched
                    })

                    # Optional Privacy Blur
                    if config.privacy.anonymize_faces:
                        frame = self.face_tracker.apply_privacy_blur(frame, face.bbox)

                    # Annotate HUD Bounding Box
                    col = (70, 215, 120) if pose["attentiveness_score"] >= 0.70 else (
                        (45, 185, 245) if pose["attentiveness_score"] >= 0.40 else (75, 75, 235)
                    )
                    cv2.rectangle(frame, (x, y), (x + w, y + h), col, 2)
                    label = f"#{face.track_id} {s_name} [{pose['state']}]"
                    cv2.rectangle(frame, (x, y - 24), (x + len(label) * 8 + 10, y), (20, 20, 26), -1)
                    cv2.putText(frame, label, (x + 4, y - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.42, col, 1)
            else:
                print("[Pipeline] Hardware camera disconnected or read failed. Falling back to Simulation Mode.")
                self._release_camera()
                self.use_simulation = True
                self.camera_error = "Hardware camera disconnected. Fallback to Simulation Mode."
                frame, participants_payload, detected_student_ids = self.simulator.generate_frame(
                    self.simulation_step, anonymize=config.privacy.anonymize_faces
                )
        else:
            # Deterministic simulation mode
            frame, participants_payload, detected_student_ids = self.simulator.generate_frame(
                self.simulation_step, anonymize=config.privacy.anonymize_faces
            )

        # 2. Audio Processing & VAD
        if self.use_simulation:
            synthetic_audio = self.simulator.generate_audio_chunk(self.simulation_step)
            audio_data = self.audio_processor.process_chunk(now, synthetic_chunk=synthetic_audio)
        else:
            audio_data = self.audio_processor.process_chunk(now)

        interaction_data = self.interaction_tracker.update(audio_data["is_speech"], dt)
        self.latest_interaction = interaction_data

        # 3. Attendance Temporal State Machine
        self.attendance_engine.process_frame(detected_student_ids, now, dt, is_paused=self.is_paused)
        attendance_summary = self.attendance_engine.get_summary()

        # 4. Multimodal Signal Fusion
        telemetry = self.engagement_engine.compute_engagement(participants_payload, audio_data, now)
        self.latest_telemetry = telemetry

        # 5. Teaching Copilot Evaluation
        suggestion = self.teaching_advisor.evaluate_telemetry(telemetry, interaction_data, now)

        # Compute FPS and latency
        proc_time = time.perf_counter() - start_proc
        self.inference_latency_ms = proc_time * 1000.0
        self.fps = 1.0 / max(0.001, dt)

        # Header HUD Overlay on the frame
        hud_col = (70, 215, 120) if telemetry["overall_engagement"] >= 65 else (
            (45, 185, 245) if telemetry["overall_engagement"] >= 45 else (75, 75, 235)
        )
        mode_tag = "SYNTHETIC SIMULATION" if self.use_simulation else "LIVE CAMERA"
        blur_tag = " • PRIVACY BLUR ON" if config.privacy.anonymize_faces else ""
        header_text = f"ClassMind AI [{mode_tag}{blur_tag}] | Activity: {telemetry['overall_engagement']}% ({telemetry.get('trend', 'Steady')})"

        # Dark HUD background banner
        cv2.rectangle(frame, (10, 10), (config.video_width - 10, 42), (20, 20, 28), -1)
        cv2.rectangle(frame, (10, 10), (config.video_width - 10, 42), (60, 60, 80), 1)
        cv2.putText(frame, header_text, (18, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.44, hud_col, 1)

        # If simulated, render corner simulation label
        if self.use_simulation:
            cv2.rectangle(frame, (config.video_width - 230, config.video_height - 30),
                          (config.video_width - 10, config.video_height - 10), (15, 15, 22), -1)
            cv2.putText(frame, "[SYNTHETIC SIMULATION]", (config.video_width - 225, config.video_height - 14),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.40, (120, 180, 255), 1)

        pipeline_output = {
            "telemetry": telemetry,
            "interaction": interaction_data,
            "attendance": attendance_summary,
            "latest_suggestion": suggestion,
            "participants": participants_payload,
            "use_simulation": self.use_simulation,
            "is_paused": self.is_paused,
            "fps": round(self.fps, 1),
            "latency_ms": round(self.inference_latency_ms, 1),
            "camera_error": self.camera_error
        }

        # Encode JPEG frame once for all consumers
        ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        jpeg_bytes = buffer.tobytes() if ret else b""

        with self.lock:
            self.latest_frame = frame
            self.latest_jpeg_bytes = jpeg_bytes
            self.latest_output = pipeline_output
            self.frame_count += 1

        return frame, pipeline_output

    def process_frame(self) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Returns the most recently computed frame & telemetry (thread-safe)."""
        with self.lock:
            if self.latest_frame is not None and self.latest_output:
                return self.latest_frame, self.latest_output
        return self._step_pipeline()

    def get_jpeg_frame(self) -> bytes:
        """Encodes or retrieves current frame as JPEG bytes for video streaming."""
        with self.lock:
            if self.latest_jpeg_bytes:
                return self.latest_jpeg_bytes
        # If not yet generated, compute one step
        _, _ = self._step_pipeline()
        with self.lock:
            return self.latest_jpeg_bytes

    def get_latest_telemetry(self) -> Dict[str, Any]:
        """Retrieves the latest telemetry payload without re-running heavy CV."""
        with self.lock:
            if self.latest_output:
                return self.latest_output
        _, output = self._step_pipeline()
        return output

    def release(self):
        """Releases camera, worker thread, audio, and computational resources."""
        self.is_running = False
        if hasattr(self, 'worker_thread') and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=1.5)
        self._release_camera()
        if self.audio_processor is not None:
            self.audio_processor.close()
        print("[Pipeline] Released all vision and audio hardware resources.")
