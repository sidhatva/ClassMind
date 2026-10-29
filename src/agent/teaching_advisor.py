"""
ClassMind AI - AI-Driven Teaching Copilot Agent.
Evaluates multimodal classroom dynamics to generate explainable, assistive,
non-intrusive teaching recommendations for instructors in real-time.
"""

import time
from typing import Dict, List, Optional, Any
from config import config
from src.agent.heuristics import RULES_CATALOG, TeachingRule
from src.database import save_teaching_suggestion, get_latest_suggestions, update_recommendation_feedback


class TeachingAdvisorAgent:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.last_alert_times: Dict[str, float] = {}
        self.cooldown_sec = config.agent.cooldown_seconds
        self.low_engagement_start: Optional[float] = None
        self.low_motion_start: Optional[float] = None

    def evaluate_telemetry(
        self,
        telemetry: Dict[str, Any],
        interaction_state: Dict[str, Any],
        current_time: float
    ) -> Optional[Dict[str, Any]]:
        """
        Processes real-time multimodal telemetry and triggers contextual teaching recommendations.
        Never fires vision-dependent alerts if vision sensors are disconnected.
        """
        overall_eng = telemetry.get("overall_engagement", 70.0)
        total_detected = telemetry.get("total_detected", 0)
        disengaged_ratio = (
            telemetry.get("disengaged_count", 0) / max(1, total_detected)
        )
        silence_sec = interaction_state.get("consecutive_silence_sec", 0.0)
        monologue_sec = interaction_state.get("consecutive_speech_sec", 0.0)
        sensor_coverage = telemetry.get("sensor_coverage", 1.0)
        active_sensors = telemetry.get("active_sensors", ["camera", "audio"])

        # 1. Sensor Quality Check
        if sensor_coverage < 0.60 or len(active_sensors) < 2:
            return self._trigger_rule(
                "SENSOR_QUALITY_ISSUE",
                current_time,
                triggering_signal=f"Active sensors: {', '.join(active_sensors) or 'None'} (Coverage: {int(sensor_coverage*100)}%)"
            )

        # 2. Check Attention Drop Rule (Only valid if camera is active and participants detected)
        if "camera" in active_sensors and total_detected > 0:
            if overall_eng < config.agent.attention_drop_threshold or disengaged_ratio >= config.agent.disengagement_ratio_threshold:
                if self.low_engagement_start is None:
                    self.low_engagement_start = current_time
                elif (current_time - self.low_engagement_start) >= config.agent.sustained_drop_duration_sec:
                    return self._trigger_rule(
                        "ATTENTION_DROP",
                        current_time,
                        triggering_signal=f"Engagement dropped to {overall_eng}% with {int(disengaged_ratio*100)}% diverted visual attention for {int(current_time - self.low_engagement_start)}s"
                    )
            else:
                self.low_engagement_start = None

        # 3. Check Monologue Pacing Rule (>90 seconds uninterrupted speech)
        if monologue_sec >= 90.0:
            return self._trigger_rule(
                "MONOLOGUE_PACING",
                current_time,
                triggering_signal=f"Continuous speech detected for {int(monologue_sec)}s without vocal pause"
            )

        # 4. Check High Discussion Energy
        if overall_eng >= 82.0 and telemetry.get("is_speech", False) and interaction_state.get("talk_ratio", 0) > 0.4:
            return self._trigger_rule(
                "HIGH_INTERACTION",
                current_time,
                triggering_signal=f"Composite engagement {overall_eng}% with synchronized vocal activity"
            )

        # 5. Check Low Activity / Inactivity (>18 seconds low motion and speech)
        motion_score = telemetry.get("movement_score") or 50.0
        if motion_score < 30.0 and silence_sec > 18.0:
            if self.low_motion_start is None:
                self.low_motion_start = current_time
            elif (current_time - self.low_motion_start) >= 15.0:
                return self._trigger_rule(
                    "LOW_ACTIVITY",
                    current_time,
                    triggering_signal=f"Movement score {motion_score}% and silence for {int(silence_sec)}s"
                )
        else:
            self.low_motion_start = None

        return None

    def _trigger_rule(
        self,
        alert_type: str,
        current_time: float,
        triggering_signal: str = "Multimodal threshold breached"
    ) -> Optional[Dict[str, Any]]:
        last_triggered = self.last_alert_times.get(alert_type, 0.0)
        if (current_time - last_triggered) < self.cooldown_sec:
            return None  # Cooldown suppression

        rule = RULES_CATALOG.get(alert_type)
        if not rule:
            return None

        self.last_alert_times[alert_type] = current_time

        suggestion_id = save_teaching_suggestion(
            session_id=self.session_id,
            alert_type=rule.alert_type,
            priority=rule.priority,
            title=rule.title,
            suggestion=rule.suggestion,
            rationale=rule.rationale,
            instructional_purpose=rule.instructional_purpose,
            triggering_signal=triggering_signal
        )

        return {
            "id": suggestion_id,
            "alert_type": rule.alert_type,
            "priority": rule.priority,
            "title": rule.title,
            "suggestion": rule.suggestion,
            "rationale": rule.rationale,
            "instructional_purpose": rule.instructional_purpose,
            "triggering_signal": triggering_signal,
            "timestamp": time.strftime("%H:%M:%S")
        }

    def get_recent_suggestions(self, limit: int = 15) -> List[Dict[str, Any]]:
        return get_latest_suggestions(self.session_id, limit)

    def record_feedback(self, rec_id: int, is_dismissed: Optional[bool] = None, is_helpful: Optional[bool] = None) -> bool:
        return update_recommendation_feedback(rec_id, is_dismissed, is_helpful)
