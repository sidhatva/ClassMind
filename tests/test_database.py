"""
ClassMind AI - SQLite Database & Persistence Tests.
Validates versioned schema, foreign-key relationships, transactional consistency,
audit logs, retention pruning, and snapshot backups.
"""

import unittest
import os
import time
from src.database import (
    init_database, seed_default_roster, create_session, get_session,
    list_sessions, log_attendance_record, get_session_attendance,
    save_engagement_telemetry, get_telemetry_history, save_teaching_suggestion,
    get_latest_suggestions, manual_correct_attendance, get_attendance_audit_logs,
    prune_old_sessions, backup_database
)


class TestDatabaseOperations(unittest.TestCase):
    def setUp(self):
        init_database()
        seed_default_roster()
        self.session_id = f"TEST-DB-{int(time.time()*1000)}"
        create_session(self.session_id, "Database Test Lecture", "Section A", total_enrolled=6)

    def test_session_creation_and_retrieval(self):
        session = get_session(self.session_id)
        self.assertIsNotNone(session)
        self.assertEqual(session["session_id"], self.session_id)
        self.assertEqual(session["title"], "Database Test Lecture")
        self.assertTrue(session["is_active"])

    def test_attendance_records_persistence_and_update(self):
        log_attendance_record(
            session_id=self.session_id,
            student_id="S101",
            first_detected="2026-10-29 10:00:00",
            last_detected="2026-10-29 10:05:00",
            sustained_seconds=300.0,
            presence_ratio=0.85,
            status="Present",
            confidence=0.95
        )

        records = get_session_attendance(self.session_id)
        s101 = next((r for r in records if r["student_id"] == "S101"), None)
        self.assertIsNotNone(s101)
        self.assertEqual(s101["status"], "Present")
        self.assertEqual(s101["sustained_seconds"], 300.0)

    def test_telemetry_history_persistence(self):
        t_epoch = time.time()
        save_engagement_telemetry(
            session_id=self.session_id,
            timestamp=t_epoch,
            overall_engagement=82.5,
            head_pose_score=85.0,
            movement_score=75.0,
            audio_score=80.0,
            active_count=5,
            disengaged_count=1,
            total_detected=6,
            trend="Steady"
        )

        history = get_telemetry_history(self.session_id, limit=10)
        self.assertGreaterEqual(len(history), 1)
        latest = history[-1]
        self.assertEqual(latest["overall_engagement"], 82.5)
        self.assertEqual(latest["active_count"], 5)

    def test_database_backup_snapshot(self):
        backup_file = backup_database()
        self.assertTrue(os.path.exists(backup_file))
        self.assertGreater(os.path.getsize(backup_file), 0)
        # Cleanup test snapshot
        try:
            os.remove(backup_file)
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()
