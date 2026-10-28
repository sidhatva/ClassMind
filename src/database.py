"""
SQLite Database interface for local, offline storage of student rosters,
attendance logs, engagement metrics, and AI teaching suggestions.
"""

import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any
from config import DB_PATH


_initialized = False

def get_db_connection() -> sqlite3.Connection:
    """Returns a thread-safe connection with dictionary-like row access."""
    global _initialized
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    if not _initialized:
        _initialized = True
        init_database(conn)
        seed_default_roster(conn)
    return conn


def init_database(conn: Optional[sqlite3.Connection] = None):
    """Initializes schema tables if they do not exist."""
    close_at_end = False
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        close_at_end = True
    cursor = conn.cursor()

    # 1. Enrolled Students
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        student_id TEXT PRIMARY KEY,
        roll_no TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        face_encoding TEXT, -- JSON serialized vector embedding
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Classroom Sessions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        end_time TIMESTAMP,
        is_active INTEGER DEFAULT 1,
        total_enrolled INTEGER DEFAULT 0,
        total_present INTEGER DEFAULT 0,
        avg_engagement REAL DEFAULT 0.0
    );
    """)

    # 3. Attendance Logs (Scenario 1)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        student_id TEXT NOT NULL,
        first_detected TIMESTAMP,
        last_detected TIMESTAMP,
        sustained_seconds REAL DEFAULT 0.0,
        presence_ratio REAL DEFAULT 0.0,
        status TEXT DEFAULT 'Pending', -- 'Present', 'Partial', 'Absent'
        marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id),
        FOREIGN KEY (student_id) REFERENCES students(student_id),
        UNIQUE(session_id, student_id)
    );
    """)

    # 4. Multimodal Engagement Telemetry (Scenario 2)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS engagement_telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        timestamp REAL NOT NULL, -- Epoch seconds
        overall_engagement REAL NOT NULL, -- 0 to 100
        head_pose_score REAL NOT NULL,
        movement_score REAL NOT NULL,
        audio_score REAL NOT NULL,
        active_count INTEGER DEFAULT 0,
        disengaged_count INTEGER DEFAULT 0,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
    );
    """)

    # 5. AI Teaching Suggestions (Scenario 3)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS teaching_suggestions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        alert_type TEXT NOT NULL, -- 'ATTENTION_DROP', 'PACING_STAGNANT', 'HIGH_INTERACTION', 'INACTIVITY'
        severity TEXT NOT NULL, -- 'info', 'warning', 'urgent'
        title TEXT NOT NULL,
        suggestion TEXT NOT NULL,
        rationale TEXT NOT NULL,
        is_dismissed INTEGER DEFAULT 0,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
    );
    """)

    conn.commit()
    if close_at_end:
        conn.close()


def seed_default_roster(conn: Optional[sqlite3.Connection] = None):
    """Populates default sample student profiles for demonstration & testing."""
    close_at_end = False
    if conn is None:
        conn = get_db_connection()
        close_at_end = True
    cursor = conn.cursor()

    default_students = [
        ("S101", "2024-CS-01", "Alex Johnson", None),
        ("S102", "2024-CS-02", "Elena Rodriguez", None),
        ("S103", "2024-CS-03", "Marcus Chen", None),
        ("S104", "2024-CS-04", "Sarah Williams", None),
        ("S105", "2024-CS-05", "Rohan Gupta", None),
        ("S106", "2024-CS-06", "Amina Zahra", None),
    ]

    for s_id, roll, name, enc in default_students:
        cursor.execute("""
        INSERT OR IGNORE INTO students (student_id, roll_no, name, face_encoding)
        VALUES (?, ?, ?, ?)
        """, (s_id, roll, name, json.dumps(enc) if enc else None))

    conn.commit()
    if close_at_end:
        conn.close()


# Database query helpers
def create_session(session_id: str, title: str, total_enrolled: int = 6) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO sessions (session_id, title, total_enrolled, is_active)
    VALUES (?, ?, ?, 1)
    """, (session_id, title, total_enrolled))
    conn.commit()
    conn.close()
    return {"session_id": session_id, "title": title}


def log_attendance_record(
    session_id: str,
    student_id: str,
    first_detected: str,
    last_detected: str,
    sustained_seconds: float,
    presence_ratio: float,
    status: str
):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO attendance_logs (session_id, student_id, first_detected, last_detected, sustained_seconds, presence_ratio, status, marked_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(session_id, student_id) DO UPDATE SET
        last_detected=excluded.last_detected,
        sustained_seconds=excluded.sustained_seconds,
        presence_ratio=excluded.presence_ratio,
        status=excluded.status
    """, (session_id, student_id, first_detected, last_detected, sustained_seconds, presence_ratio, status))
    conn.commit()
    conn.close()


def save_engagement_telemetry(
    session_id: str,
    timestamp: float,
    overall_engagement: float,
    head_pose_score: float,
    movement_score: float,
    audio_score: float,
    active_count: int,
    disengaged_count: int
):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO engagement_telemetry (session_id, timestamp, overall_engagement, head_pose_score, movement_score, audio_score, active_count, disengaged_count)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (session_id, timestamp, overall_engagement, head_pose_score, movement_score, audio_score, active_count, disengaged_count))
    conn.commit()
    conn.close()


def save_teaching_suggestion(
    session_id: str,
    alert_type: str,
    severity: str,
    title: str,
    suggestion: str,
    rationale: str
) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO teaching_suggestions (session_id, alert_type, severity, title, suggestion, rationale)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (session_id, alert_type, severity, title, suggestion, rationale))
    s_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return s_id


def get_latest_suggestions(session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, timestamp, alert_type, severity, title, suggestion, rationale
    FROM teaching_suggestions
    WHERE session_id = ?
    ORDER BY id DESC LIMIT ?
    """, (session_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_session_attendance(session_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT s.student_id, s.roll_no, s.name, 
           COALESCE(a.status, 'Absent') as status,
           COALESCE(a.sustained_seconds, 0) as sustained_seconds,
           COALESCE(a.presence_ratio, 0.0) as presence_ratio,
           a.first_detected, a.last_detected
    FROM students s
    LEFT JOIN attendance_logs a ON s.student_id = a.student_id AND a.session_id = ?
    ORDER BY s.roll_no ASC
    """, (session_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_telemetry_history(session_id: str, limit: int = 60) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT timestamp, overall_engagement, head_pose_score, movement_score, audio_score, active_count, disengaged_count
    FROM engagement_telemetry
    WHERE session_id = ?
    ORDER BY id DESC LIMIT ?
    """, (session_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]
