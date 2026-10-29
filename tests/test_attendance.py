"""
ClassMind AI - Automated Attendance Engine Tests.
Validates temporal sliding window observations, sustained presence thresholds,
temporary occlusion handling, late arrivals, and manual instructor overrides.
"""

import unittest
import time
from src.database import init_database, seed_default_roster, create_session, manual_correct_attendance, get_session_attendance, get_attendance_audit_logs
from src.attendance.sustained_presence import SustainedPresenceEngine, StudentPresenceState


class TestAttendanceEngine(unittest.TestCase):
    def setUp(self):
        init_database()
        seed_default_roster()
        self.session_id = f"TEST-ATT-{int(time.time()*1000)}"
        create_session(self.session_id, "Test Attendance Session", "Section A", total_enrolled=6)
        self.engine = SustainedPresenceEngine(self.session_id)

    def test_initial_state_is_unverified_or_absent(self):
        summary = self.engine.get_summary()
        self.assertEqual(summary["total_enrolled"], 6)
        self.assertEqual(summary["present_count"], 0)
        for rec in summary["records"]:
            self.assertIn(rec["status"], ["Unverified", "Absent"])

    def test_transient_glance_does_not_mark_present(self):
        """A transient appearance of 1 second should not qualify for Present."""
        t0 = 1000.0
        # Student S101 appears for 1 second only
        self.engine.process_frame(["S101"], current_epoch=t0, dt=1.0)
        state = self.engine.states["S101"]
        self.assertNotEqual(state.status, "Present")
        self.assertEqual(state.status, "Unverified")

    def test_sustained_presence_reaches_present(self):
        """Continuous presence exceeding the threshold marks student as Present."""
        t = 1000.0
        # S101 is present for 12 continuous seconds (each step dt=1.0s)
        for _ in range(12):
            self.engine.process_frame(["S101"], current_epoch=t, dt=1.0)
            t += 1.0

        state = self.engine.states["S101"]
        self.assertEqual(state.status, "Present")
        self.assertGreaterEqual(state.observed_presence_seconds, 8.0)
        self.assertGreaterEqual(state.window_presence_ratio, 0.60)

    def test_temporary_occlusion_tolerance(self):
        """A brief occlusion (3 seconds absent out of 15 seconds) keeps student Present."""
        t = 1000.0
        # Student present for 10 seconds
        for _ in range(10):
            self.engine.process_frame(["S102"], current_epoch=t, dt=1.0)
            t += 1.0
        
        self.assertEqual(self.engine.states["S102"].status, "Present")

        # Briefly occluded for 3 seconds
        for _ in range(3):
            self.engine.process_frame([], current_epoch=t, dt=1.0)
            t += 1.0

        # Ratio in window: 10/13 = 77% >= 60% -> Still Present!
        state = self.engine.states["S102"]
        self.assertEqual(state.status, "Present")

    def test_manual_attendance_correction_with_audit(self):
        """Manual instructor override updates status and creates persistent audit record."""
        # Manually mark S103 as Present with a valid rationale
        success = manual_correct_attendance(
            session_id=self.session_id,
            student_id="S103",
            new_status="Present",
            reason="Student sitting in blind spot behind projector column",
            changed_by="Prof. Test"
        )
        self.assertTrue(success)

        # Check DB records
        records = get_session_attendance(self.session_id)
        s103 = next(r for r in records if r["student_id"] == "S103")
        self.assertEqual(s103["status"], "Present")
        self.assertEqual(s103["manual_correction"], 1)

        # Check audit trail
        audit_logs = get_attendance_audit_logs(self.session_id)
        self.assertGreaterEqual(len(audit_logs), 1)
        latest_audit = audit_logs[0]
        self.assertEqual(latest_audit["student_id"], "S103")
        self.assertEqual(latest_audit["new_state"], "Present")
        self.assertIn("blind spot", latest_audit["reason"])


if __name__ == "__main__":
    unittest.main()
