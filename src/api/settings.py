"""
ClassMind AI - Settings, Privacy & Retention API Router.
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from config import config
from src.dependencies import get_session_manager
from src.services.session_manager import SessionManager
from src.database import get_db_setting, set_db_setting, prune_old_sessions, backup_database
from src.schemas import SettingsSchema

router = APIRouter(prefix="/api/settings", tags=["Settings & Privacy"])


@router.get("", response_model=SettingsSchema)
async def get_settings(mgr: SessionManager = Depends(get_session_manager)):
    sim_mode = mgr.pipeline.use_simulation if mgr.pipeline else False
    anonymize = config.privacy.anonymize_faces
    biometric_on = mgr.pipeline.face_recognizer.enabled if mgr.pipeline else False
    retention = get_db_setting("data_retention_days", 30)

    return SettingsSchema(
        use_simulation=sim_mode,
        anonymize_faces=anonymize,
        biometric_matching_enabled=biometric_on,
        data_retention_days=retention,
        window_duration_seconds=config.attendance.window_duration_seconds,
        sustained_presence_ratio=config.attendance.sustained_presence_ratio,
        min_face_size=config.attendance.min_face_size,
        weight_head_pose=config.engagement.weight_head_pose,
        weight_movement=config.engagement.weight_movement,
        weight_audio_activity=config.engagement.weight_audio_activity,
        attention_drop_threshold=config.agent.attention_drop_threshold,
        sustained_drop_duration_sec=config.agent.sustained_drop_duration_sec,
        cooldown_seconds=config.agent.cooldown_seconds,
        selected_camera_index=config.camera_index,
        selected_mic_index=0
    )


@router.post("", response_model=SettingsSchema)
async def update_settings(
    payload: Dict[str, Any],
    mgr: SessionManager = Depends(get_session_manager)
):
    # Simulation mode
    if "use_simulation" in payload and mgr.pipeline:
        sim_val = bool(payload["use_simulation"])
        if sim_val != mgr.pipeline.use_simulation:
            mgr.pipeline.set_simulation_mode(sim_val)

    # Privacy Face Blur
    if "anonymize_faces" in payload:
        config.privacy.anonymize_faces = bool(payload["anonymize_faces"])

    # Biometric matching
    if "biometric_matching_enabled" in payload and mgr.pipeline:
        mgr.pipeline.face_recognizer.set_enabled(bool(payload["biometric_matching_enabled"]))

    # Selected Camera
    if "selected_camera_index" in payload and mgr.pipeline:
        new_cam = int(payload["selected_camera_index"])
        if new_cam != config.camera_index:
            config.camera_index = new_cam
            mgr.pipeline.video_source = new_cam
            if not mgr.pipeline.use_simulation:
                mgr.pipeline._init_video_capture()

    # Attendance thresholds
    if "window_duration_seconds" in payload:
        config.attendance.window_duration_seconds = float(payload["window_duration_seconds"])
        if mgr.pipeline:
            mgr.pipeline.attendance_engine.window_duration = config.attendance.window_duration_seconds

    if "sustained_presence_ratio" in payload:
        config.attendance.sustained_presence_ratio = float(payload["sustained_presence_ratio"])
        if mgr.pipeline:
            mgr.pipeline.attendance_engine.presence_ratio_threshold = config.attendance.sustained_presence_ratio

    if "min_face_size" in payload:
        config.attendance.min_face_size = int(payload["min_face_size"])

    # Engagement Weights
    if any(k in payload for k in ["weight_head_pose", "weight_movement", "weight_audio_activity"]):
        config.engagement.weight_head_pose = float(payload.get("weight_head_pose", config.engagement.weight_head_pose))
        config.engagement.weight_movement = float(payload.get("weight_movement", config.engagement.weight_movement))
        config.engagement.weight_audio_activity = float(payload.get("weight_audio_activity", config.engagement.weight_audio_activity))
        if mgr.pipeline:
            mgr.pipeline.engagement_engine.update_weights(
                config.engagement.weight_head_pose,
                config.engagement.weight_movement,
                config.engagement.weight_audio_activity
            )

    # Teaching Agent
    if "attention_drop_threshold" in payload:
        config.agent.attention_drop_threshold = float(payload["attention_drop_threshold"])
    if "sustained_drop_duration_sec" in payload:
        config.agent.sustained_drop_duration_sec = float(payload["sustained_drop_duration_sec"])
    if "cooldown_seconds" in payload:
        config.agent.cooldown_seconds = float(payload["cooldown_seconds"])
        if mgr.pipeline:
            mgr.pipeline.teaching_advisor.cooldown_sec = config.agent.cooldown_seconds

    # Retention
    if "data_retention_days" in payload:
        set_db_setting("data_retention_days", int(payload["data_retention_days"]))

    return await get_settings(mgr)


@router.post("/retention/prune")
async def prune_retention(days: int = 30):
    if days < 1:
        raise HTTPException(status_code=400, detail="Retention days must be >= 1")
    count = prune_old_sessions(days)
    return {"status": "success", "sessions_pruned": count, "retention_days": days}


@router.post("/backup")
async def trigger_database_backup():
    path = backup_database()
    return {"status": "success", "backup_file": path}
