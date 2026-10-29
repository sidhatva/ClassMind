"""
ClassMind AI - Session & Pipeline Lifecycle Manager.
Coordinates active session state, hardware/simulation transitions,
and ensures clean resource release on shutdown.
"""

from typing import Optional, Dict, Any
from config import config
from src.database import (
    create_session, get_session, update_session_state, log_session_event, list_sessions
)
from src.pipeline import ClassroomPipeline


class SessionManager:
    _instance: Optional['SessionManager'] = None

    def __init__(self):
        self.active_session_id: str = "SESSION-LIVE-01"
        self.pipeline: Optional[ClassroomPipeline] = None
        self.is_running: bool = False
        self.is_paused: bool = False

    @classmethod
    def get_instance(cls) -> 'SessionManager':
        if cls._instance is None:
            cls._instance = SessionManager()
        return cls._instance

    def initialize_default_session(self, force_sim: bool = False):
        """Initializes default demonstration session."""
        import os
        force_sim = force_sim or (os.environ.get("FORCE_SIMULATION") == "1")
        session_info = get_session(self.active_session_id)
        if not session_info:
            create_session(
                session_id=self.active_session_id,
                title="Lecture 1: Multimodal Intelligence & Edge AI",
                section="Section A",
                total_enrolled=6
            )
        self.pipeline = ClassroomPipeline(
            session_id=self.active_session_id,
            video_source=config.camera_index,
            force_simulation=force_sim
        )
        self.is_running = True
        self.is_paused = False

    def start_new_session(self, title: str, section: str = "Section A", instructor: str = "Instructor", total_enrolled: int = 6) -> str:
        """Stops any existing session and starts a new session."""
        import time
        if self.pipeline:
            self.stop_current_session()

        new_session_id = f"SESSION-{int(time.time())}"
        create_session(
            session_id=new_session_id,
            title=title,
            section=section,
            instructor_name=instructor,
            total_enrolled=total_enrolled
        )
        self.active_session_id = new_session_id
        self.pipeline = ClassroomPipeline(
            session_id=new_session_id,
            video_source=config.camera_index,
            force_simulation=config.privacy.offline_only
        )
        self.is_running = True
        self.is_paused = False
        return new_session_id

    def pause_session(self) -> bool:
        if self.pipeline:
            self.pipeline.set_paused(True)
            self.is_paused = True
            update_session_state(self.active_session_id, is_paused=True)
            log_session_event(self.active_session_id, "PAUSE", "Instructor paused monitoring.")
            return True
        return False

    def resume_session(self) -> bool:
        if self.pipeline:
            self.pipeline.set_paused(False)
            self.is_paused = False
            update_session_state(self.active_session_id, is_paused=False)
            log_session_event(self.active_session_id, "RESUME", "Instructor resumed monitoring.")
            return True
        return False

    def stop_current_session(self) -> bool:
        from datetime import datetime
        if self.pipeline:
            self.pipeline.release()
            self.pipeline = None
        self.is_running = False
        self.is_paused = False
        update_session_state(
            self.active_session_id,
            is_active=False,
            is_paused=False,
            end_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        log_session_event(self.active_session_id, "STOP", "Session stopped and finalized.")
        return True

    def get_hardware_status(self) -> Dict[str, Any]:
        cam_ok = False
        cam_error = None
        mic_ok = False
        sim = True
        fps = 0.0
        lat = 0.0

        if self.pipeline:
            sim = self.pipeline.use_simulation
            cam_ok = not sim and (self.pipeline.cap is not None and self.pipeline.cap.isOpened())
            cam_error = self.pipeline.camera_error
            mic_ok = self.pipeline.audio_processor.mic_available
            fps = self.pipeline.fps
            lat = self.pipeline.inference_latency_ms

        return {
            "camera_available": cam_ok,
            "camera_device": f"Webcam Device #{config.camera_index}" if cam_ok else "None (Simulated / Detached)",
            "camera_error": cam_error,
            "microphone_available": mic_ok,
            "microphone_device": self.pipeline.audio_processor.device_name if self.pipeline else "None",
            "simulated_mode": sim,
            "processing_fps": round(fps, 1),
            "inference_latency_ms": round(lat, 1)
        }
