"""
Scenario 2: Multimodal Signal Fusion & Engagement Analytics Engine.
Fuses computer vision indicators (head pose, gaze, movement, inactivity) and audio
signal levels (VAD, energy, speech ratio) into a real-time Engagement Index (0 - 100%).
"""

from collections import deque
from datetime import datetime
from typing import Dict, List, Optional
from config import config
from src.database import save_engagement_telemetry


class MultimodalEngagementEngine:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.w_head = config.engagement.weight_head_pose
        self.w_motion = config.engagement.weight_movement
        self.w_audio = config.engagement.weight_audio_activity
        
        # Telemetry rolling history for trend analysis
        self.history = deque(maxlen=120)  # ~2 minutes of high-resolution telemetry
        self.last_saved_db_time = 0.0

    def compute_engagement(
        self,
        participants_data: List[Dict[str, any]],
        audio_data: Dict[str, any],
        current_timestamp: float
    ) -> Dict[str, any]:
        """
        Fuses visual participant signals with acoustic processing.
        Returns aggregate engagement index, breakdown metrics, and trend alerts.
        """
        num_participants = len(participants_data)
        
        if num_participants > 0:
            avg_head_score = float(np_mean := sum(p.get("attentiveness_score", 0.5) for p in participants_data) / num_participants)
            avg_motion_score = float(sum(p.get("motion_score", 0.5) for p in participants_data) / num_participants)
            disengaged_count = sum(1 for p in participants_data if p.get("attentiveness_score", 1.0) < 0.4 or p.get("is_inactive", False))
            active_count = num_participants - disengaged_count
        else:
            avg_head_score = 0.5
            avg_motion_score = 0.5
            disengaged_count = 0
            active_count = 0

        audio_score = audio_data.get("audio_activity_score", 0.5)

        # Multimodal Fusion Formula
        composite_score = (
            (self.w_head * avg_head_score) +
            (self.w_motion * avg_motion_score) +
            (self.w_audio * audio_score)
        ) * 100.0

        composite_score = max(5.0, min(100.0, composite_score))

        telemetry_point = {
            "timestamp": current_timestamp,
            "overall_engagement": round(composite_score, 1),
            "head_pose_score": round(avg_head_score * 100, 1),
            "movement_score": round(avg_motion_score * 100, 1),
            "audio_score": round(audio_score * 100, 1),
            "active_count": active_count,
            "disengaged_count": disengaged_count,
            "total_detected": num_participants,
            "is_speech": audio_data.get("is_speech", False),
            "rms_energy": audio_data.get("rms_energy", 0.0)
        }

        self.history.append(telemetry_point)

        # Save to database periodically (~every 2 seconds)
        if current_timestamp - self.last_saved_db_time >= 2.0:
            save_engagement_telemetry(
                session_id=self.session_id,
                timestamp=current_timestamp,
                overall_engagement=telemetry_point["overall_engagement"],
                head_pose_score=telemetry_point["head_pose_score"],
                movement_score=telemetry_point["movement_score"],
                audio_score=telemetry_point["audio_score"],
                active_count=active_count,
                disengaged_count=disengaged_count
            )
            self.last_saved_db_time = current_timestamp

        # Detect real-time trend
        trend = self._analyze_trend()
        telemetry_point["trend"] = trend

        return telemetry_point

    def _analyze_trend(self) -> str:
        """Determines if engagement is rising, steady, or declining over recent samples."""
        if len(self.history) < 10:
            return "Stabilizing"
        
        recent = [pt["overall_engagement"] for pt in list(self.history)[-10:]]
        older = [pt["overall_engagement"] for pt in list(self.history)[-25:-10]] if len(self.history) >= 25 else recent[:5]
        
        delta = (sum(recent) / len(recent)) - (sum(older) / len(older))
        if delta > 4.0:
            return "Rising"
        elif delta < -4.0:
            return "Declining"
        return "Steady"

    def get_recent_history(self, count: int = 30) -> List[Dict[str, any]]:
        return list(self.history)[-count:]
