"""
ClassMind AI - Attendance Management & Verification API Router.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from src.dependencies import get_session_manager
from src.services.session_manager import SessionManager
from src.services.export_service import ExportService
from src.database import get_session_attendance, manual_correct_attendance, get_attendance_audit_logs
from src.schemas import (
    AttendanceSummaryResponse, AttendanceRecordSchema,
    ManualAttendanceCorrectionRequest, AttendanceAuditLogSchema
)

router = APIRouter(prefix="/api/attendance", tags=["Attendance Management"])


@router.get("/summary", response_model=AttendanceSummaryResponse)
async def get_attendance_summary(
    session_id: Optional[str] = None,
    mgr: SessionManager = Depends(get_session_manager)
):
    target_id = session_id or mgr.active_session_id
    if mgr.pipeline and target_id == mgr.active_session_id:
        summary = mgr.pipeline.attendance_engine.get_summary()
        records_schema = [AttendanceRecordSchema(**r) for r in summary["records"]]
        return AttendanceSummaryResponse(
            session_id=target_id,
            total_enrolled=summary["total_enrolled"],
            present_count=summary["present_count"],
            partial_count=summary["partial_count"],
            absent_count=summary["absent_count"],
            unverified_count=summary["unverified_count"],
            attendance_rate=summary["attendance_rate"],
            records=records_schema
        )

    # Database query fallback
    raw_records = get_session_attendance(target_id)
    records_schema = []
    present_cnt = sum(1 for r in raw_records if r.get("status") == "Present")
    partial_cnt = sum(1 for r in raw_records if r.get("status") == "Partial")
    unverified_cnt = sum(1 for r in raw_records if r.get("status") == "Unverified")
    total_enrolled = len(raw_records)
    absent_cnt = total_enrolled - present_cnt - partial_cnt - unverified_cnt

    for r in raw_records:
        records_schema.append(AttendanceRecordSchema(
            student_id=r["student_id"],
            roll_no=r["roll_no"],
            name=r["name"],
            section=r.get("section", "Section A"),
            status=r.get("status", "Absent"),
            sustained_seconds=r.get("sustained_seconds", 0.0),
            presence_ratio=r.get("presence_ratio", 0.0),
            confidence=r.get("confidence", 0.85),
            verification_reason=r.get("verification_reason", "Database Record"),
            first_detected=r.get("first_detected"),
            last_detected=r.get("last_detected"),
            is_late=bool(r.get("is_late", 0)),
            is_early_departure=bool(r.get("is_early_departure", 0)),
            manual_correction=bool(r.get("manual_correction", 0)),
            correction_reason=r.get("correction_reason")
        ))

    rate = round((present_cnt / max(1, total_enrolled)) * 100, 1)
    return AttendanceSummaryResponse(
        session_id=target_id,
        total_enrolled=total_enrolled,
        present_count=present_cnt,
        partial_count=partial_cnt,
        absent_count=absent_cnt,
        unverified_count=unverified_cnt,
        attendance_rate=rate,
        records=records_schema
    )


@router.post("/correct")
async def correct_student_attendance(
    payload: ManualAttendanceCorrectionRequest,
    mgr: SessionManager = Depends(get_session_manager)
):
    target_id = mgr.active_session_id
    success = manual_correct_attendance(
        session_id=target_id,
        student_id=payload.student_id,
        new_status=payload.new_status,
        reason=payload.reason,
        changed_by=payload.instructor_id or "Instructor"
    )

    # If pipeline is active in memory, update in-memory state too
    if mgr.pipeline and payload.student_id in mgr.pipeline.attendance_engine.states:
        state = mgr.pipeline.attendance_engine.states[payload.student_id]
        state.status = payload.new_status
        state.manual_override = True
        state.verification_reason = f"Teacher-Reviewed Manual Override: {payload.reason}"

    return {"status": "success", "student_id": payload.student_id, "new_status": payload.new_status}


@router.get("/audit-trail", response_model=List[AttendanceAuditLogSchema])
async def get_audit_trail(
    session_id: Optional[str] = None,
    mgr: SessionManager = Depends(get_session_manager)
):
    target_id = session_id or mgr.active_session_id
    logs = get_attendance_audit_logs(target_id)
    return [
        AttendanceAuditLogSchema(
            id=log["id"],
            session_id=log["session_id"],
            student_id=log.get("student_id", ""),
            previous_status=log.get("previous_state", ""),
            new_status=log.get("new_state", ""),
            changed_by=log.get("changed_by", "Instructor"),
            reason=log.get("reason", ""),
            timestamp=str(log.get("timestamp", ""))
        )
        for log in logs
    ]


@router.get("/export/csv")
async def export_attendance_csv(
    session_id: Optional[str] = None,
    mgr: SessionManager = Depends(get_session_manager)
):
    target_id = session_id or mgr.active_session_id
    csv_content = ExportService.export_attendance_csv(target_id)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=attendance_{target_id}.csv"}
    )


@router.get("/export/json")
async def export_session_json(
    session_id: Optional[str] = None,
    mgr: SessionManager = Depends(get_session_manager)
):
    target_id = session_id or mgr.active_session_id
    data = ExportService.export_session_json(target_id)
    return data
