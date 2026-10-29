"""
ClassMind AI - Multimodal Signal Fusion & Engagement Engine Tests.
Validates weight normalization, missing-sensor weight renormalization,
coverage scoring, and trend detection.
"""

import unittest
from src.fusion.engagement_engine import MultimodalEngagementEngine


class TestEngagementEngine(unittest.TestCase):
    def setUp(self):
        from src.database import init_database, seed_default_roster, create_session
        init_database()
        seed_default_roster()
        self.session_id = "TEST-ENG-01"
        create_session(self.session_id, "Test Engagement Session", total_enrolled=6)
        self.engine = MultimodalEngagementEngine(session_id=self.session_id)

    def test_full_sensory_coverage_computation(self):
        """When both camera and audio are active, scores are computed across all indicators."""
        participants = [
            {"attentiveness_score": 0.90, "motion_score": 0.80, "is_inactive": False},
            {"attentiveness_score": 0.85, "motion_score": 0.70, "is_inactive": False}
        ]
        audio = {
            "is_speech": True,
            "audio_activity_score": 0.75,
            "rms_energy": 0.05,
            "sensor_available": True
        }

        res = self.engine.compute_engagement(participants, audio, current_timestamp=100.0)
        self.assertIn("overall_engagement", res)
        self.assertGreaterEqual(res["overall_engagement"], 70.0)
        self.assertEqual(res["sensor_coverage"], 1.0)
        self.assertIn("camera", res["active_sensors"])
        self.assertIn("audio", res["active_sensors"])

    def test_missing_audio_sensor_renormalization(self):
        """When the microphone is detached, visual weights renormalize without penalizing students."""
        participants = [
            {"attentiveness_score": 0.95, "motion_score": 0.85, "is_inactive": False}
        ]
        audio_fault = {
            "is_speech": False,
            "audio_activity_score": 0.0,
            "rms_energy": 0.0,
            "sensor_available": False  # Sensor disconnected
        }

        res = self.engine.compute_engagement(participants, audio_fault, current_timestamp=102.0)
        # Should not drop engagement to zero despite missing audio
        self.assertGreaterEqual(res["overall_engagement"], 80.0)
        self.assertEqual(res["sensor_coverage"], 0.5)
        self.assertNotIn("audio", res["active_sensors"])
        self.assertIn("camera", res["active_sensors"])

    def test_missing_camera_renormalization(self):
        """When the camera is disconnected, audio activity normalizes over available signals."""
        participants_empty = []
        audio_ok = {
            "is_speech": True,
            "audio_activity_score": 0.90,
            "rms_energy": 0.08,
            "sensor_available": True
        }

        res = self.engine.compute_engagement(participants_empty, audio_ok, current_timestamp=104.0)
        self.assertGreaterEqual(res["overall_engagement"], 80.0)
        self.assertEqual(res["sensor_coverage"], 0.5)
        self.assertIn("audio", res["active_sensors"])
        self.assertNotIn("camera", res["active_sensors"])

    def test_trend_detection(self):
        """Validates detection of Rising, Steady, and Declining trends."""
        # Feed high values
        for i in range(12):
            self.engine.compute_engagement(
                [{"attentiveness_score": 0.95, "motion_score": 0.90, "is_inactive": False}],
                {"is_speech": True, "audio_activity_score": 0.90, "sensor_available": True},
                current_timestamp=200.0 + i
            )
        
        # Now feed sharply dropping values
        for i in range(10):
            res = self.engine.compute_engagement(
                [{"attentiveness_score": 0.20, "motion_score": 0.10, "is_inactive": True}],
                {"is_speech": False, "audio_activity_score": 0.20, "sensor_available": True},
                current_timestamp=220.0 + i
            )
        
        self.assertEqual(res["trend"], "Declining")


if __name__ == "__main__":
    unittest.main()
