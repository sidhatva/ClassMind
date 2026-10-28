"""
Scenario 1: Automated Attendance Engine via Sustained Presence.
Filters out transient appearances, walking passersby, and brief glimpses by requiring
a verified threshold of active presence across temporal observation windows.
"""

from collections import deque
from datetime import datetime
from typing import Dict, List, Optional
from config import config
from src.database import log_attendance_record, get_session_attendance


class StudentPresenceRecord:
    def __init__(self, student_id: str, name: str, roll_no: str):
        self.student_id = student_id
        self.name = name
        self.roll_no = roll_no
        self.first_detected: Optional[datetime] = None
        self.last_detected: Optional[datetime] = None
        self.sustained_seconds: float = 0.0
        self.status: str = "Absent"  # "Absent", "Pending", "Partial", "Present"
        
        # Sliding buffer of (timestamp, detected_bool)
        self.presence_buffer: deque = deque()

    def update_presence(self, is_present: bool, timestamp: float, dt: float):
        now = datetime.now()
        if is_present:
            if self.first_detected is None:
                self.first_detected = now
            self.last_detected = now
            self.sustained_seconds += dt

        self.presence_buffer.append((timestamp, is_present))
        
        # Prune records older than window_duration
        cutoff = timestamp - config.attendance.window_duration_seconds
        while self.presence_buffer and self.presence_buffer[0][0] < cutoff:
            self.presence_buffer.popleft()

    @property
    def presence_ratio(self) -> float:
        if not self.presence_buffer:
            return 0.0
        present_count = sum(1 for _, pres in self.presence_buffer if pres)
        return float(present_count / len(self.presence_buffer))


class SustainedPresenceEngine:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.records: Dict[str, StudentPresenceRecord] = {}
        self.window_duration = config.attendance.window_duration_seconds
        self.threshold_ratio = config.attendance.sustained_presence_ratio
        self._load_enrolled_roster()

    def _load_enrolled_roster(self):
        """Initializes records from the enrolled student roster."""
        initial_data = get_session_attendance(self.session_id)
        for row in initial_data:
            s_id = row["student_id"]
            rec = StudentPresenceRecord(s_id, row["name"], row["roll_no"])
            rec.status = row["status"]
            rec.sustained_seconds = row["sustained_seconds"]
            self.records[s_id] = rec

    def register_or_get(self, student_id: str, name: str, roll_no: str) -> StudentPresenceRecord:
        if student_id not in self.records:
            self.records[student_id] = StudentPresenceRecord(student_id, name, roll_no)
        return self.records[student_id]

    def process_frame_observations(self, detected_student_ids: List[str], current_timestamp: float, dt: float):
        """
        Evaluates sustained presence for all students based on the current frame's detections.
        """
        detected_set = set(detected_student_ids)

        for s_id, record in self.records.items():
            is_detected = s_id in detected_set
            record.update_presence(is_detected, current_timestamp, dt)

            # Evaluate presence status using sustained ratio
            ratio = record.presence_ratio
            if ratio >= self.threshold_ratio and record.sustained_seconds >= (self.window_duration * 0.5):
                record.status = "Present"
            elif record.sustained_seconds > 3.0:
                record.status = "Partial"
            elif record.first_detected is not None:
                record.status = "Pending"
            else:
                record.status = "Absent"

            # Sync with database
            if record.first_detected is not None:
                log_attendance_record(
                    session_id=self.session_id,
                    student_id=record.student_id,
                    first_detected=record.first_detected.strftime("%Y-%m-%d %H:%M:%S"),
                    last_detected=record.last_detected.strftime("%Y-%m-%d %H:%M:%S") if record.last_detected else "",
                    sustained_seconds=round(record.sustained_seconds, 1),
                    presence_ratio=round(ratio, 2),
                    status=record.status
                )

    def get_summary(self) -> Dict[str, any]:
        total = len(self.records)
        present = sum(1 for r in self.records.values() if r.status == "Present")
        partial = sum(1 for r in self.records.values() if r.status == "Partial")
        absent = total - present - partial

        roster_list = []
        for r in self.records.values():
            roster_list.append({
                "student_id": r.student_id,
                "roll_no": r.roll_no,
                "name": r.name,
                "status": r.status,
                "sustained_seconds": round(r.sustained_seconds, 1),
                "presence_ratio": round(r.presence_ratio * 100, 1),
                "first_detected": r.first_detected.strftime("%H:%M:%S") if r.first_detected else "-",
                "last_detected": r.last_detected.strftime("%H:%M:%S") if r.last_detected else "-"
            })

        return {
            "total_enrolled": total,
            "present_count": present,
            "partial_count": partial,
            "absent_count": absent,
            "attendance_rate": round((present / max(1, total)) * 100, 1),
            "roster": roster_list
        }
