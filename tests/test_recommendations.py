"""
ClassMind AI - Teaching Copilot & Recommendations Agent Tests.
Validates explainable pedagogical rules, cooldown deduplication,
sensor quality guards, and feedback states.
"""

import unittest
from src.database import init_database, create_session, get_latest_suggestions
from src.agent.teaching_advisor import TeachingAdvisorAgent


class TestRecommendationsAdvisor(unittest.TestCase):
    def setUp(self):
        init_database()
        self.session_id = "TEST-REC-SESSION-01"
        create_session(self.session_id, "Test Rec Session", "Section A", total_enrolled=6)
        self.agent = TeachingAdvisorAgent(self.session_id)

    def test_monologue_pacing_rule(self):
        """Uninterrupted instructor monologue exceeding 90 seconds triggers pacing suggestion."""
        telemetry = {
            "overall_engagement": 75.0,
            "total_detected": 4,
            "sensor_coverage": 1.0,
            "active_sensors": ["camera", "audio"]
        }
        interaction = {
            "consecutive_speech_sec": 95.0,
            "consecutive_silence_sec": 0.0,
            "talk_ratio": 0.85
        }

        rec = self.agent.evaluate_telemetry(telemetry, interaction, current_time=100.0)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["alert_type"], "MONOLOGUE_PACING")
        self.assertIn("Monologue", rec["title"])
        self.assertIn("instructional_purpose", rec)

    def test_cooldown_suppression(self):
        """Immediate subsequent triggers within the cooldown period must be suppressed."""
        telemetry = {
            "overall_engagement": 75.0,
            "total_detected": 4,
            "sensor_coverage": 1.0,
            "active_sensors": ["camera", "audio"]
        }
        interaction = {
            "consecutive_speech_sec": 95.0,
            "consecutive_silence_sec": 0.0
        }

        # First trigger fires
        rec1 = self.agent.evaluate_telemetry(telemetry, interaction, current_time=200.0)
        self.assertIsNotNone(rec1)

        # 5 seconds later (within 20s cooldown)
        rec2 = self.agent.evaluate_telemetry(telemetry, interaction, current_time=205.0)
        self.assertIsNone(rec2, "Repeated alert should be suppressed by cooldown.")

    def test_attention_drop_sensor_guard(self):
        """Attention drop recommendation must NOT fire if camera sensor is disconnected."""
        telemetry_camera_offline = {
            "overall_engagement": 30.0,
            "total_detected": 0,
            "sensor_coverage": 0.5,
            "active_sensors": ["audio"]  # Camera disconnected
        }
        interaction = {"consecutive_speech_sec": 0.0, "consecutive_silence_sec": 5.0}

        rec = self.agent.evaluate_telemetry(telemetry_camera_offline, interaction, current_time=300.0)
        # Should trigger SENSOR_QUALITY_ISSUE instead of falsely claiming students are not looking!
        self.assertIsNotNone(rec)
        self.assertEqual(rec["alert_type"], "SENSOR_QUALITY_ISSUE")

    def test_feedback_dismiss_and_helpful(self):
        """Instructors can dismiss or mark recommendations as helpful."""
        rec_id = self.agent._trigger_rule("HIGH_INTERACTION", current_time=400.0)["id"]
        
        # Mark as helpful
        success_helpful = self.agent.record_feedback(rec_id, is_helpful=True)
        self.assertTrue(success_helpful)

        # Dismiss
        success_dismiss = self.agent.record_feedback(rec_id, is_dismissed=True)
        self.assertTrue(success_dismiss)


if __name__ == "__main__":
    unittest.main()
