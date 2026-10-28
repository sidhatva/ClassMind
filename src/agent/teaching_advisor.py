"""
Scenario 3: AI-Driven Teaching Suggestions Agent.
Evaluates multimodal classroom dynamics to produce assistive, non-intrusive
teaching recommendations for instructors in real-time.
"""

import time
from typing import Dict, List, Optional
from config import config
from src.agent.heuristics import RULES_CATALOG, TeachingRule
from src.database import save_teaching_suggestion, get_latest_suggestions


class TeachingAdvisorAgent:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.last_alert_times: Dict[str, float] = {}
        self.cooldown_sec = config.agent.cooldown_seconds
        self.low_engagement_start: Optional[float] = None

    def evaluate_telemetry(
        self,
        telemetry: Dict[str, any],
        interaction_state: Dict[str, any],
        current_time: float
    ) -> Optional[Dict[str, any]]:
        """
        Processes real-time telemetry and triggers contextual teaching recommendations.
        """
        overall_eng = telemetry.get("overall_engagement", 70.0)
        disengaged_ratio = (
            telemetry.get("disengaged_count", 0) / max(1, telemetry.get("total_detected", 1))
        )
        silence_sec = interaction_state.get("consecutive_silence_sec", 0.0)
        monologue_sec = interaction_state.get("consecutive_speech_sec", 0.0)

        # 1. Check Attention Drop Rule
        if overall_eng < config.agent.attention_drop_threshold or disengaged_ratio >= config.agent.disengagement_ratio_threshold:
            if self.low_engagement_start is None:
                self.low_engagement_start = current_time
            elif (current_time - self.low_engagement_start) >= config.agent.sustained_drop_duration_sec:
                return self._trigger_rule("ATTENTION_DROP", current_time)
        else:
            self.low_engagement_start = None

        # 2. Check Monologue Pacing Rule
        if monologue_sec > 90.0:
            return self._trigger_rule("MONOLOGUE_PACING", current_time)

        # 3. Check Prolonged Silence Rule
        if silence_sec > 25.0:
            return self._trigger_rule("PROLONGED_SILENCE", current_time)

        # 4. Check High Discussion Energy
        if overall_eng > 85.0 and telemetry.get("is_speech", False):
            return self._trigger_rule("HIGH_INTERACTION", current_time)

        return None

    def _trigger_rule(self, alert_type: str, current_time: float) -> Optional[Dict[str, any]]:
        last_triggered = self.last_alert_times.get(alert_type, 0.0)
        if (current_time - last_triggered) < self.cooldown_sec:
            return None  # Suppress repetitive alerts

        rule = next((r for r in RULES_CATALOG if r.alert_type == alert_type), None)
        if not rule:
            return None

        self.last_alert_times[alert_type] = current_time

        # Save to database
        suggestion_id = save_teaching_suggestion(
            session_id=self.session_id,
            alert_type=rule.alert_type,
            severity=rule.severity,
            title=rule.title,
            suggestion=rule.suggestion,
            rationale=rule.rationale
        )

        return {
            "id": suggestion_id,
            "alert_type": rule.alert_type,
            "severity": rule.severity,
            "title": rule.title,
            "suggestion": rule.suggestion,
            "rationale": rule.rationale,
            "timestamp": time.strftime("%H:%M:%S")
        }

    def get_recent_suggestions(self, limit: int = 6) -> List[Dict[str, any]]:
        return get_latest_suggestions(self.session_id, limit)
