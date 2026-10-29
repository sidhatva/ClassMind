"""
ClassMind AI - Multimodal Signal Fusion & Engagement Analytics Engine.
Fuses visual indicators (head pose orientation, movement dynamics) and acoustic activity
into a real-time Classroom Activity and Attention Indicator (0 - 100).
Includes dynamic weight renormalization for missing sensors, confidence scoring,
and trend analysis.
"""

from collections import deque
from typing import Dict, List, Optional, Any
from config import config
from src.database import save_engagement_telemetry


class MultimodalEngagementEngine:
    """
    Transparent Multimodal Fusion Engine.
    NOTE: Labeled 'Classroom Activity and Attention Indicators'.
    This composite metric is an assistive heuristic estimate for instructional pacing,
    not a validated psychological measurement of student cognitive comprehension.
    """
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.w_head = config.engagement.weight_head_pose
        self.w_motion = config.engagement.weight_movement
        self.w_audio = config.engagement.weight_audio_activity

        # Rolling history for moving average and trend calculations
        self.history = deque(maxlen=150)
        self.last_saved_db_time = 0.0

    def update_weights(self, w_head: float, w_motion: float, w_audio: float):
        total = w_head + w_motion + w_audio
        if total > 0:
            self.w_head = w_head / total
            self.w_motion = w_motion / total
            self.w_audio = w_audio / total

    def compute_engagement(
        self,
        participants_data: List[Dict[str, Any]],
        audio_data: Dict[str, Any],
        current_timestamp: float
    ) -> Dict[str, Any]:
        """
        Calculates composite engagement index with dynamic missing-sensor weight renormalization.
        """
        active_sensors = []
        valid_weights = {}

        # 1. Vision Sensors (Head Pose & Movement)
        num_participants = len(participants_data)
        vision_available = num_participants > 0

        if vision_available:
            active_sensors.append("camera")
            avg_head_score = float(sum(p.get("attentiveness_score", 0.5) for p in participants_data) / num_participants)
            avg_motion_score = float(sum(p.get("motion_score", 0.5) for p in participants_data) / num_participants)
            disengaged_count = sum(1 for p in participants_data if p.get("attentiveness_score", 1.0) < 0.40 or p.get("is_inactive", False))
            active_count = num_participants - disengaged_count
            valid_weights["head"] = (self.w_head, avg_head_score)
            valid_weights["motion"] = (self.w_motion, avg_motion_score)
        else:
            avg_head_score = 0.0
            avg_motion_score = 0.0
            disengaged_count = 0
            active_count = 0

        # 2. Audio Sensor
        audio_sensor_ok = audio_data.get("sensor_available", True)
        if audio_sensor_ok:
            active_sensors.append("audio")
            audio_score = audio_data.get("audio_activity_score", 0.5)
            valid_weights["audio"] = (self.w_audio, audio_score)
        else:
            audio_score = 0.0

        # Dynamic Renormalization
        total_valid_weight = sum(w for w, _ in valid_weights.values())
        if total_valid_weight > 0:
            composite_score = sum((w / total_valid_weight) * val for w, val in valid_weights.values()) * 100.0
            sensor_coverage = round(len(active_sensors) / 2.0, 2)
            confidence = round(0.70 + (sensor_coverage * 0.25), 2)
        else:
            # All sensors missing or unavailable
            composite_score = 50.0
            sensor_coverage = 0.0
            confidence = 0.20

        composite_score = max(5.0, min(100.0, composite_score))

        telemetry_point = {
            "timestamp": current_timestamp,
            "overall_engagement": round(composite_score, 1),
            "head_pose_score": round(avg_head_score * 100, 1) if vision_available else None,
            "movement_score": round(avg_motion_score * 100, 1) if vision_available else None,
            "audio_score": round(audio_score * 100, 1) if audio_sensor_ok else None,
            "active_count": active_count,
            "disengaged_count": disengaged_count,
            "total_detected": num_participants,
            "is_speech": audio_data.get("is_speech", False),
            "rms_energy": audio_data.get("rms_energy", 0.0),
            "sensor_coverage": sensor_coverage,
            "active_sensors": active_sensors,
            "confidence": confidence,
            "formula_contribution": {
                "head_pose": f"{int((self.w_head / max(0.01, total_valid_weight)) * 100)}%" if "head" in valid_weights else "0% (Sensor Inactive)",
                "movement": f"{int((self.w_motion / max(0.01, total_valid_weight)) * 100)}%" if "motion" in valid_weights else "0% (Sensor Inactive)",
                "audio": f"{int((self.w_audio / max(0.01, total_valid_weight)) * 100)}%" if "audio" in valid_weights else "0% (Sensor Inactive)"
            }
        }

        self.history.append(telemetry_point)

        # Periodic DB logging (~every 2.0 seconds)
        if current_timestamp - self.last_saved_db_time >= 2.0:
            save_engagement_telemetry(
                session_id=self.session_id,
                timestamp=current_timestamp,
                overall_engagement=telemetry_point["overall_engagement"],
                head_pose_score=telemetry_point["head_pose_score"] or 0.0,
                movement_score=telemetry_point["movement_score"] or 0.0,
                audio_score=telemetry_point["audio_score"] or 0.0,
                active_count=active_count,
                disengaged_count=disengaged_count,
                total_detected=num_participants,
                trend=self._analyze_trend(),
                is_speech=telemetry_point["is_speech"],
                rms_energy=telemetry_point["rms_energy"],
                sensor_coverage=sensor_coverage,
                active_sensors=active_sensors,
                confidence=confidence
            )
            self.last_saved_db_time = current_timestamp

        telemetry_point["trend"] = self._analyze_trend()
        return telemetry_point

    def _analyze_trend(self) -> str:
        """Determines if engagement is rising, steady, declining, or insufficient data."""
        if len(self.history) < 8:
            return "Insufficient Data"

        recent = [pt["overall_engagement"] for pt in list(self.history)[-8:]]
        older = [pt["overall_engagement"] for pt in list(self.history)[-20:-8]] if len(self.history) >= 20 else recent[:4]

        delta = (sum(recent) / len(recent)) - (sum(older) / len(older))
        if delta > 4.5:
            return "Rising"
        elif delta < -4.5:
            return "Declining"
        return "Steady"

    def get_recent_history(self, count: int = 40) -> List[Dict[str, Any]]:
        return list(self.history)[-count:]
