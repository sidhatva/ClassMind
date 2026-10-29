"""
ClassMind AI - Engagement Analytics & Telemetry API Router.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query
from src.dependencies import get_session_manager
from src.services.session_manager import SessionManager
from src.database import get_telemetry_history
from src.schemas import AnalyticsSummaryResponse, TelemetryPoint

router = APIRouter(prefix="/api/analytics", tags=["Engagement Analytics"])


@router.get("/timeseries", response_model=List[TelemetryPoint])
async def get_timeseries(
    session_id: Optional[str] = None,
    limit: int = Query(60, ge=5, le=300),
    mgr: SessionManager = Depends(get_session_manager)
):
    target_id = session_id or mgr.active_session_id
    raw_history = get_telemetry_history(target_id, limit=limit)
    res = []
    for h in raw_history:
        res.append(TelemetryPoint(
            timestamp=h["timestamp"],
            overall_engagement=h["overall_engagement"],
            head_pose_score=h.get("head_pose_score", 0.0),
            movement_score=h.get("movement_score", 0.0),
            audio_score=h.get("audio_score", 0.0),
            active_count=h.get("active_count", 0),
            disengaged_count=h.get("disengaged_count", 0),
            total_detected=h.get("total_detected", 0),
            trend=h.get("trend", "Steady"),
            is_speech=bool(h.get("is_speech", False)),
            rms_energy=h.get("rms_energy", 0.0),
            sensor_coverage=h.get("sensor_coverage", 1.0),
            active_sensors=h.get("active_sensors", ["camera", "audio"]),
            confidence=h.get("confidence", 0.90)
        ))
    return res


@router.get("/summary", response_model=AnalyticsSummaryResponse)
async def get_analytics_summary(
    session_id: Optional[str] = None,
    mgr: SessionManager = Depends(get_session_manager)
):
    target_id = session_id or mgr.active_session_id
    timeseries_data = await get_timeseries(session_id=target_id, limit=60, mgr=mgr)
    
    current_eng = 65.0
    trend = "Steady"
    breakdown = {"head_pose": 65.0, "movement": 60.0, "audio": 55.0}

    if mgr.pipeline and target_id == mgr.active_session_id and mgr.pipeline.latest_telemetry:
        t = mgr.pipeline.latest_telemetry
        current_eng = t.get("overall_engagement", 65.0)
        trend = t.get("trend", "Steady")
        breakdown = {
            "head_pose": t.get("head_pose_score") or 0.0,
            "movement": t.get("movement_score") or 0.0,
            "audio": t.get("audio_score") or 0.0
        }
    elif timeseries_data:
        latest = timeseries_data[-1]
        current_eng = latest.overall_engagement
        trend = latest.trend
        breakdown = {
            "head_pose": latest.head_pose_score,
            "movement": latest.movement_score,
            "audio": latest.audio_score
        }

    hw = mgr.get_hardware_status()
    sensor_health = {
        "camera": hw["camera_available"] or hw["simulated_mode"],
        "microphone": hw["microphone_available"] or hw["simulated_mode"]
    }

    return AnalyticsSummaryResponse(
        session_id=target_id,
        duration_seconds=float(len(timeseries_data) * 2.0),
        current_engagement=current_eng,
        trend=trend,
        breakdown=breakdown,
        sensor_health=sensor_health,
        timeseries=timeseries_data
    )
