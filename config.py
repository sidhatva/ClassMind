"""
Configuration settings for the Multimodal Attendance & Engagement Agent.
All parameters are tuned for offline, privacy-preserving classroom intelligence.
"""

from pathlib import Path
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ROSTER_DIR = DATA_DIR / "rosters"
LOGS_DIR = DATA_DIR / "attendance_logs"
TELEMETRY_DIR = DATA_DIR / "session_telemetry"
DB_PATH = DATA_DIR / "classroom_intelligence.db"

# Ensure all directories exist
for path in [DATA_DIR, ROSTER_DIR, LOGS_DIR, TELEMETRY_DIR]:
    path.mkdir(parents=True, exist_ok=True)


class AttendanceConfig(BaseModel):
    """Scenario 1: Automated Attendance Tracking Configuration"""
    # Time window (seconds) to evaluate sustained presence
    window_duration_seconds: float = Field(default=15.0, description="Window size in seconds")
    # Minimum ratio of active appearances required in window to mark sustained attendance
    sustained_presence_ratio: float = Field(default=0.60, description="Min presence ratio (0.0 - 1.0)")
    # Confidence threshold for face recognition / identity matching
    face_match_threshold: float = Field(default=0.55, description="Cosine distance / similarity threshold")
    # Minimum face bounding box size (pixels) to avoid detecting distant background posters
    min_face_size: int = Field(default=40, description="Minimum face width/height in px")


class EngagementConfig(BaseModel):
    """Scenario 2: Engagement & Session Dynamics Multimodal Weights"""
    # Weights for multimodal fusion (must sum to 1.0)
    weight_head_pose: float = Field(default=0.45, description="Attentive head alignment weight")
    weight_movement: float = Field(default=0.25, description="Active movement/posture dynamic weight")
    weight_audio_activity: float = Field(default=0.30, description="Classroom vocal/interaction weight")
    
    # Head pose threshold angles (degrees)
    yaw_tolerance: float = Field(default=30.0, description="Max deviation from screen before marked looking away")
    pitch_tolerance: float = Field(default=25.0, description="Max downward/upward pitch before marked looking down/up")
    
    # Motion and inactivity
    inactivity_threshold_seconds: float = Field(default=8.0, description="Seconds of zero motion before flagged")
    
    # Audio thresholds
    audio_energy_threshold: float = Field(default=0.03, description="Normalized RMS threshold for speech activity")


class TeachingAgentConfig(BaseModel):
    """Scenario 3: AI-Driven Teaching Suggestions Configuration"""
    attention_drop_threshold: float = Field(default=45.0, description="Engagement index % that triggers alert")
    sustained_drop_duration_sec: float = Field(default=12.0, description="Duration in sec of low engagement")
    disengagement_ratio_threshold: float = Field(default=0.40, description="Fraction of class disengaged to trigger suggestion")
    cooldown_seconds: float = Field(default=20.0, description="Cooldown between identical alerts to avoid spam")


class PrivacyConfig(BaseModel):
    """Privacy-Preserving Offline Rules"""
    anonymize_faces: bool = Field(default=False, description="Blur faces in video feeds")
    store_raw_video: bool = Field(default=False, description="Never store raw frames to disk")
    offline_only: bool = Field(default=True, description="Strict local edge processing")


class AppConfig(BaseModel):
    attendance: AttendanceConfig = Field(default_factory=AttendanceConfig)
    engagement: EngagementConfig = Field(default_factory=EngagementConfig)
    agent: TeachingAgentConfig = Field(default_factory=TeachingAgentConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    
    # Video & UI Settings
    camera_index: int = 0
    video_width: int = 640
    video_height: int = 480
    fps_target: int = 24
    host: str = "127.0.0.1"
    port: int = 8080


# Singleton default configuration
config = AppConfig()

