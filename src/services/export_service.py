"""
ClassMind AI - Data Export Service.
Generates privacy-compliant CSV and JSON reports for attendance and session telemetry.
"""

import io
import csv
import json
from typing import Dict, Any, List
from src.database import get_session, get_session_attendance, get_telemetry_history, get_session_events, get_attendance_audit_logs


class ExportService:
    @staticmethod
    def export_attendance_csv(session_id: str) -> str:
        """Exports verified attendance records as structured CSV."""
        records = get_session_attendance(session_id)
        session = get_session(session_id) or {}
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["# ClassMind AI - Attendance Report"])
        writer.writerow([f"# Session ID: {session_id}", f"Title: {session.get('title', '')}", f"Date: {session.get('start_time', '')}"])
        writer.writerow([])
        writer.writerow([
            "Roll No", "Student Name", "Section", "Status",
            "Sustained (sec)", "Presence Ratio", "Confidence",
            "Verification Reason", "First Detected", "Last Detected",
            "Late Arrival", "Early Departure", "Manual Override", "Override Reason"
        ])

        for r in records:
            writer.writerow([
                r.get("roll_no", ""),
                r.get("name", ""),
                r.get("section", "Section A"),
                r.get("status", "Absent"),
                r.get("sustained_seconds", 0.0),
                f"{r.get('presence_ratio', 0.0):.1f}%",
                f"{r.get('confidence', 0.85):.2f}",
                r.get("verification_reason", ""),
                r.get("first_detected") or "N/A",
                r.get("last_detected") or "N/A",
                "Yes" if r.get("is_late") else "No",
                "Yes" if r.get("is_early_departure") else "No",
                "Yes" if r.get("manual_correction") else "No",
                r.get("correction_reason") or ""
            ])

        return output.getvalue()

    @staticmethod
    def export_session_json(session_id: str) -> Dict[str, Any]:
        """Exports complete comprehensive session package in JSON format."""
        session = get_session(session_id) or {}
        attendance = get_session_attendance(session_id)
        telemetry = get_telemetry_history(session_id, limit=300)
        events = get_session_events(session_id, limit=100)
        audit_logs = get_attendance_audit_logs(session_id)

        return {
            "metadata": {
                "system": "ClassMind AI",
                "version": "2.0.0",
                "export_time": json.dumps(str(session.get("start_time"))),
                "privacy_note": "Local edge-processed intelligence report. No raw biometric encodings included."
            },
            "session": session,
            "attendance": attendance,
            "telemetry_samples": telemetry,
            "session_events": events,
            "attendance_audit_logs": audit_logs
        }
