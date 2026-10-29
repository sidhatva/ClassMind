"""
ClassMind AI - SQLite Database Interface.
Provides persistent, local, privacy-first storage for classroom sessions,
attendance records, engagement telemetry, pedagogical recommendations,
audit trails, and configuration.
"""

import os
import json
import sqlite3
import shutil
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from config import DB_PATH, DATA_DIR


SCHEMA_VERSION = 2
_initialized = False


def get_db_connection(db_file: Optional[str] = None) -> sqlite3.Connection:
    """Returns a thread-safe connection with dictionary-like row access and foreign keys enabled."""
    global _initialized
    target = str(db_file or DB_PATH)
    conn = sqlite3.connect(target, check_same_thread=False, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA foreign_keys = ON;")
    if not _initialized and db_file is None:
        _initialized = True
        init_database(conn)
        seed_default_roster(conn)
    return conn


def init_database(conn: Optional[sqlite3.Connection] = None):
    """Initializes schema tables with strict constraints, indexes, and audit tables."""
    close_at_end = False
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=10.0)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA foreign_keys = ON;")
        close_at_end = True
    cursor = conn.cursor()

    # Automatic schema migration check for existing tables
    try:
        cursor.execute("PRAGMA table_info(students)")
        student_cols = [c[1] for c in cursor.fetchall()]
        if student_cols and "section" not in student_cols:
            cursor.execute("ALTER TABLE students ADD COLUMN section TEXT DEFAULT 'Section A'")
    except Exception:
        pass

    try:
        cursor.execute("PRAGMA table_info(sessions)")
        session_cols = [c[1] for c in cursor.fetchall()]
        if session_cols:
            if "section" not in session_cols:
                cursor.execute("ALTER TABLE sessions ADD COLUMN section TEXT DEFAULT 'Section A'")
            if "instructor_name" not in session_cols:
                cursor.execute("ALTER TABLE sessions ADD COLUMN instructor_name TEXT DEFAULT 'Instructor'")
            if "is_paused" not in session_cols:
                cursor.execute("ALTER TABLE sessions ADD COLUMN is_paused INTEGER DEFAULT 0")
    except Exception:
        pass

    # 1. Schema versioning / metadata
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS schema_info (
        version INTEGER PRIMARY KEY,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Students & Roster
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        student_id TEXT PRIMARY KEY,
        roll_no TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        section TEXT DEFAULT 'Section A',
        face_encoding TEXT, -- Optional JSON serialized vector embedding
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 3. Classroom Sessions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        section TEXT DEFAULT 'Section A',
        instructor_name TEXT DEFAULT 'Instructor',
        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        end_time TIMESTAMP,
        is_active INTEGER DEFAULT 1,
        is_paused INTEGER DEFAULT 0,
        total_enrolled INTEGER DEFAULT 0,
        total_present INTEGER DEFAULT 0,
        avg_engagement REAL DEFAULT 0.0
    );
    """)

    # 4. Attendance Records
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        student_id TEXT NOT NULL,
        first_detected TIMESTAMP,
        last_detected TIMESTAMP,
        sustained_seconds REAL DEFAULT 0.0,
        presence_ratio REAL DEFAULT 0.0,
        confidence REAL DEFAULT 0.90,
        verification_reason TEXT DEFAULT 'Awaiting Observation',
        status TEXT DEFAULT 'Unverified', -- 'Present', 'Partial', 'Absent', 'Unverified'
        is_late INTEGER DEFAULT 0,
        is_early_departure INTEGER DEFAULT 0,
        manual_correction INTEGER DEFAULT 0,
        correction_reason TEXT,
        marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
        UNIQUE(session_id, student_id)
    );
    """)

    # 5. Engagement Samples (Telemetry)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS engagement_samples (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        timestamp REAL NOT NULL, -- Epoch seconds
        overall_engagement REAL NOT NULL,
        head_pose_score REAL NOT NULL,
        movement_score REAL NOT NULL,
        audio_score REAL NOT NULL,
        active_count INTEGER DEFAULT 0,
        disengaged_count INTEGER DEFAULT 0,
        total_detected INTEGER DEFAULT 0,
        trend TEXT DEFAULT 'Steady',
        is_speech INTEGER DEFAULT 0,
        rms_energy REAL DEFAULT 0.0,
        sensor_coverage REAL DEFAULT 1.0,
        active_sensors TEXT DEFAULT '["camera","audio"]',
        confidence REAL DEFAULT 0.90,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
    );
    """)

    # 6. Teaching Copilot Recommendations
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        alert_type TEXT NOT NULL,
        priority TEXT NOT NULL, -- 'info', 'warning', 'urgent'
        title TEXT NOT NULL,
        suggestion TEXT NOT NULL,
        rationale TEXT NOT NULL,
        instructional_purpose TEXT NOT NULL,
        triggering_signal TEXT NOT NULL,
        is_dismissed INTEGER DEFAULT 0,
        is_helpful INTEGER DEFAULT NULL,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
    );
    """)

    # 7. Session Events Log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS session_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        event_type TEXT NOT NULL, -- 'START', 'PAUSE', 'RESUME', 'STOP', 'SENSOR_ERROR', 'STUDENT_JOIN', 'STUDENT_LEAVE'
        details TEXT,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
    );
    """)

    # 8. Audit Logs (Instructor Manual Overrides & Privacy Actions)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        student_id TEXT,
        action TEXT NOT NULL, -- 'MANUAL_ATTENDANCE_CORRECTION', 'SETTINGS_UPDATE', 'DATA_PURGE'
        previous_state TEXT,
        new_state TEXT,
        changed_by TEXT DEFAULT 'Instructor',
        reason TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
    );
    """)

    # 9. System Settings KV Store
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Optimized Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_att_session ON attendance_records(session_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_eng_session_time ON engagement_samples(session_id, timestamp);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rec_session ON recommendations(session_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_session ON session_events(session_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_logs(session_id);")

    # Record Schema Version
    cursor.execute("INSERT OR IGNORE INTO schema_info (version) VALUES (?)", (SCHEMA_VERSION,))

    conn.commit()
    if close_at_end:
        conn.close()


def seed_default_roster(conn: Optional[sqlite3.Connection] = None):
    """Populates standard sample student roster for demonstration and testing."""
    close_at_end = False
    if conn is None:
        conn = get_db_connection()
        close_at_end = True
    cursor = conn.cursor()

    default_students = [
        ("S101", "2024-CS-01", "Alex Johnson", "Section A", None),
        ("S102", "2024-CS-02", "Elena Rodriguez", "Section A", None),
        ("S103", "2024-CS-03", "Marcus Chen", "Section A", None),
        ("S104", "2024-CS-04", "Sarah Williams", "Section A", None),
        ("S105", "2024-CS-05", "Rohan Gupta", "Section A", None),
        ("S106", "2024-CS-06", "Amina Zahra", "Section A", None),
    ]

    for s_id, roll, name, sec, enc in default_students:
        cursor.execute("""
        INSERT OR IGNORE INTO students (student_id, roll_no, name, section, face_encoding)
        VALUES (?, ?, ?, ?, ?)
        """, (s_id, roll, name, sec, json.dumps(enc) if enc else None))

    conn.commit()
    if close_at_end:
        conn.close()


# ==========================================
# Session Database Operations
# ==========================================
def create_session(
    session_id: str,
    title: str,
    section: str = "Section A",
    instructor_name: str = "Instructor",
    total_enrolled: int = 6
) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR IGNORE INTO sessions (session_id, title, section, instructor_name, total_enrolled, is_active, is_paused)
    VALUES (?, ?, ?, ?, ?, 1, 0)
    """, (session_id, title, section, instructor_name, total_enrolled))
    
    # Initialize attendance records for all students in section
    cursor.execute("SELECT student_id FROM students WHERE section = ?", (section,))
    enrolled_students = cursor.fetchall()
    for row in enrolled_students:
        cursor.execute("""
        INSERT OR IGNORE INTO attendance_records (session_id, student_id, status, verification_reason)
        VALUES (?, ?, 'Unverified', 'Session Initialized - Awaiting Detection')
        """, (session_id, row["student_id"]))

    log_session_event(session_id, "START", f"Session '{title}' started with {total_enrolled} enrolled.", conn=conn)

    conn.commit()
    conn.close()
    return {
        "session_id": session_id,
        "title": title,
        "section": section,
        "instructor_name": instructor_name,
        "total_enrolled": total_enrolled,
        "is_active": True
    }


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def list_sessions(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT s.*, 
           COUNT(CASE WHEN a.status = 'Present' THEN 1 END) as present_count
    FROM sessions s
    LEFT JOIN attendance_records a ON s.session_id = a.session_id
    GROUP BY s.session_id
    ORDER BY s.start_time DESC
    LIMIT ? OFFSET ?
    """, (limit, offset))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_session_state(session_id: str, is_active: Optional[bool] = None, is_paused: Optional[bool] = None, end_time: Optional[str] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    updates = []
    params = []

    if is_active is not None:
        updates.append("is_active = ?")
        params.append(1 if is_active else 0)
    if is_paused is not None:
        updates.append("is_paused = ?")
        params.append(1 if is_paused else 0)
    if end_time is not None:
        updates.append("end_time = ?")
        params.append(end_time)

    if updates:
        query = f"UPDATE sessions SET {', '.join(updates)} WHERE session_id = ?"
        params.append(session_id)
        cursor.execute(query, params)
        conn.commit()
    conn.close()


def log_session_event(session_id: str, event_type: str, details: str = "", conn: Optional[sqlite3.Connection] = None):
    close_at_end = False
    if conn is None:
        conn = get_db_connection()
        close_at_end = True
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO session_events (session_id, event_type, details)
    VALUES (?, ?, ?)
    """, (session_id, event_type, details))
    if close_at_end:
        conn.commit()
        conn.close()


def get_session_events(session_id: str, limit: int = 30) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM session_events WHERE session_id = ? ORDER BY id DESC LIMIT ?
    """, (session_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==========================================
# Attendance Database Operations
# ==========================================
def log_attendance_record(
    session_id: str,
    student_id: str,
    first_detected: Optional[str],
    last_detected: Optional[str],
    sustained_seconds: float,
    presence_ratio: float,
    status: str,
    confidence: float = 0.90,
    verification_reason: str = "Automated Sustained Presence",
    is_late: bool = False,
    is_early_departure: bool = False
):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO attendance_records (
            session_id, student_id, first_detected, last_detected,
            sustained_seconds, presence_ratio, status, confidence,
            verification_reason, is_late, is_early_departure, marked_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(session_id, student_id) DO UPDATE SET
            last_detected=excluded.last_detected,
            sustained_seconds=excluded.sustained_seconds,
            presence_ratio=excluded.presence_ratio,
            status=CASE WHEN attendance_records.manual_correction = 1 THEN attendance_records.status ELSE excluded.status END,
            confidence=excluded.confidence,
            verification_reason=CASE WHEN attendance_records.manual_correction = 1 THEN attendance_records.verification_reason ELSE excluded.verification_reason END,
            is_late=excluded.is_late,
            is_early_departure=excluded.is_early_departure
        """, (
            session_id, student_id, first_detected, last_detected,
            sustained_seconds, presence_ratio, status, confidence,
            verification_reason, 1 if is_late else 0, 1 if is_early_departure else 0
        ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def manual_correct_attendance(
    session_id: str,
    student_id: str,
    new_status: str,
    reason: str,
    changed_by: str = "Instructor"
) -> bool:
    """Allows instructors to manually override attendance with an explicit audit trail."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch previous status
    cursor.execute("""
    SELECT status FROM attendance_records WHERE session_id = ? AND student_id = ?
    """, (session_id, student_id))
    row = cursor.fetchone()
    prev_status = row["status"] if row else "Absent"

    # Update attendance record
    cursor.execute("""
    INSERT INTO attendance_records (
        session_id, student_id, status, manual_correction, correction_reason, verification_reason, marked_at
    )
    VALUES (?, ?, ?, 1, ?, 'Teacher-Reviewed Manual Override', CURRENT_TIMESTAMP)
    ON CONFLICT(session_id, student_id) DO UPDATE SET
        status=excluded.status,
        manual_correction=1,
        correction_reason=excluded.correction_reason,
        verification_reason='Teacher-Reviewed Manual Override'
    """, (session_id, student_id, new_status, reason))

    # Record Audit Log
    cursor.execute("""
    INSERT INTO audit_logs (
        session_id, student_id, action, previous_state, new_state, changed_by, reason
    )
    VALUES (?, ?, 'MANUAL_ATTENDANCE_CORRECTION', ?, ?, ?, ?)
    """, (session_id, student_id, prev_status, new_status, changed_by, reason))

    log_session_event(
        session_id,
        "ATTENDANCE_OVERRIDE",
        f"Student {student_id} changed from '{prev_status}' to '{new_status}' by {changed_by}. Reason: {reason}",
        conn=conn
    )

    conn.commit()
    conn.close()
    return True


def get_session_attendance(session_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT s.student_id, s.roll_no, s.name, s.section,
           COALESCE(a.status, 'Unverified') as status,
           COALESCE(a.sustained_seconds, 0.0) as sustained_seconds,
           COALESCE(a.presence_ratio, 0.0) as presence_ratio,
           COALESCE(a.confidence, 0.85) as confidence,
           COALESCE(a.verification_reason, 'No Data') as verification_reason,
           COALESCE(a.is_late, 0) as is_late,
           COALESCE(a.is_early_departure, 0) as is_early_departure,
           COALESCE(a.manual_correction, 0) as manual_correction,
           a.correction_reason,
           a.first_detected, a.last_detected
    FROM students s
    LEFT JOIN attendance_records a ON s.student_id = a.student_id AND a.session_id = ?
    ORDER BY s.roll_no ASC
    """, (session_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_attendance_audit_logs(session_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM audit_logs WHERE session_id = ? ORDER BY id DESC
    """, (session_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==========================================
# Telemetry Database Operations
# ==========================================
def save_engagement_telemetry(
    session_id: str,
    timestamp: float,
    overall_engagement: float,
    head_pose_score: float,
    movement_score: float,
    audio_score: float,
    active_count: int,
    disengaged_count: int,
    total_detected: int = 0,
    trend: str = "Steady",
    is_speech: bool = False,
    rms_energy: float = 0.0,
    sensor_coverage: float = 1.0,
    active_sensors: List[str] = None,
    confidence: float = 0.90
):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO engagement_samples (
        session_id, timestamp, overall_engagement, head_pose_score,
        movement_score, audio_score, active_count, disengaged_count,
        total_detected, trend, is_speech, rms_energy, sensor_coverage,
        active_sensors, confidence
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id, timestamp, overall_engagement, head_pose_score,
        movement_score, audio_score, active_count, disengaged_count,
        total_detected, trend, 1 if is_speech else 0, rms_energy, sensor_coverage,
        json.dumps(active_sensors or ["camera", "audio"]), confidence
    ))
    conn.commit()
    conn.close()


def get_telemetry_history(session_id: str, limit: int = 60) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT timestamp, overall_engagement, head_pose_score, movement_score, audio_score,
           active_count, disengaged_count, total_detected, trend, is_speech, rms_energy,
           sensor_coverage, active_sensors, confidence
    FROM engagement_samples
    WHERE session_id = ?
    ORDER BY id DESC LIMIT ?
    """, (session_id, limit))
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for r in reversed(rows):
        d = dict(r)
        d["active_sensors"] = json.loads(d["active_sensors"]) if d.get("active_sensors") else ["camera", "audio"]
        d["is_speech"] = bool(d["is_speech"])
        result.append(d)
    return result


# ==========================================
# Recommendations Database Operations
# ==========================================
def save_teaching_suggestion(
    session_id: str,
    alert_type: str,
    priority: str,
    title: str,
    suggestion: str,
    rationale: str,
    instructional_purpose: str = "Maintain engagement and learning momentum",
    triggering_signal: str = "Multimodal threshold condition"
) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO recommendations (
        session_id, alert_type, priority, title, suggestion, rationale,
        instructional_purpose, triggering_signal
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (session_id, alert_type, priority, title, suggestion, rationale, instructional_purpose, triggering_signal))
    r_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return r_id


def get_latest_suggestions(session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, timestamp, alert_type, priority, title, suggestion, rationale,
           instructional_purpose, triggering_signal, is_dismissed, is_helpful
    FROM recommendations
    WHERE session_id = ? AND is_dismissed = 0
    ORDER BY id DESC LIMIT ?
    """, (session_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_recommendation_feedback(rec_id: int, is_dismissed: Optional[bool] = None, is_helpful: Optional[bool] = None) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    updates = []
    params = []

    if is_dismissed is not None:
        updates.append("is_dismissed = ?")
        params.append(1 if is_dismissed else 0)
    if is_helpful is not None:
        updates.append("is_helpful = ?")
        params.append(1 if is_helpful else 0)

    if updates:
        query = f"UPDATE recommendations SET {', '.join(updates)} WHERE id = ?"
        params.append(rec_id)
        cursor.execute(query, params)
        conn.commit()
    conn.close()
    return True


# ==========================================
# Settings & Retention Operations
# ==========================================
def get_db_setting(key: str, default: Any = None) -> Any:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        try:
            return json.loads(row["value"])
        except Exception:
            return row["value"]
    return default


def set_db_setting(key: str, value: Any):
    conn = get_db_connection()
    cursor = conn.cursor()
    serialized = json.dumps(value) if not isinstance(value, str) else value
    cursor.execute("""
    INSERT INTO app_settings (key, value, updated_at)
    VALUES (?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
    """, (key, serialized))
    conn.commit()
    conn.close()


def prune_old_sessions(retention_days: int) -> int:
    """Removes sessions and all associated telemetry/attendance older than retention_days."""
    if retention_days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT session_id FROM sessions WHERE start_time < ?", (cutoff_str,))
    old_sessions = cursor.fetchall()
    deleted_count = len(old_sessions)

    for row in old_sessions:
        cursor.execute("DELETE FROM sessions WHERE session_id = ?", (row["session_id"],))

    conn.commit()
    conn.close()
    return deleted_count


def backup_database() -> str:
    """Creates a timestamped snapshot of the local database in data/backups/."""
    backups_dir = DATA_DIR / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backups_dir / f"classmind_backup_{stamp}.db"
    shutil.copy2(str(DB_PATH), str(backup_path))
    return str(backup_path)


def reset_database():
    """Wipes and re-initializes clean schema and default roster."""
    if os.path.exists(str(DB_PATH)):
        os.remove(str(DB_PATH))
    global _initialized
    _initialized = False
    init_database()
    seed_default_roster()
