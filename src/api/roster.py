"""
ClassMind AI - Student Roster Management API Router.
"""

from typing import List
from fastapi import APIRouter, HTTPException
from src.database import get_db_connection
from src.schemas import StudentSchema

router = APIRouter(prefix="/api/roster", tags=["Student Roster Management"])


@router.get("", response_model=List[StudentSchema])
async def get_all_students():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT student_id, roll_no, name, section, face_encoding FROM students ORDER BY roll_no ASC")
    rows = cursor.fetchall()
    conn.close()

    return [
        StudentSchema(
            student_id=r["student_id"],
            roll_no=r["roll_no"],
            name=r["name"],
            section=r.get("section", "Section A"),
            has_biometric_enrolled=bool(r.get("face_encoding"))
        )
        for r in rows
    ]


@router.post("", response_model=StudentSchema)
async def add_student(student: StudentSchema):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO students (student_id, roll_no, name, section)
        VALUES (?, ?, ?, ?)
        """, (student.student_id, student.roll_no, student.name, student.section))
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Failed to add student: {str(e)}")
    conn.close()
    return student
