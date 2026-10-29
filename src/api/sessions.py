"""
ClassMind AI - Sessions Management API Router.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from src.dependencies import get_session_manager
from src.services.session_manager import SessionManager
from src.database import get_session, list_sessions, get_session_events
from src.schemas import SessionResponse, SessionCreateRequest, SessionActionRequest

router = APIRouter(prefix="/api/sessions", tags=["Session Management"])


@router.get("", response_model=List[SessionResponse])
async def get_all_sessions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    sessions = list_sessions(limit=limit, offset=offset)
    res = []
    for s in sessions:
        res.append(SessionResponse(
            session_id=s["session_id"],
            title=s["title"],
            section=s.get("section", "Section A"),
            instructor_name=s.get("instructor_name", "Instructor"),
            start_time=str(s["start_time"]),
            end_time=str(s["end_time"]) if s.get("end_time") else None,
            is_active=bool(s.get("is_active", 0)),
            is_paused=bool(s.get("is_paused", 0)),
            total_enrolled=s.get("total_enrolled", 0),
            total_present=s.get("present_count", 0),
            avg_engagement=s.get("avg_engagement", 0.0)
        ))
    return res


@router.get("/current", response_model=SessionResponse)
async def get_current_session(mgr: SessionManager = Depends(get_session_manager)):
    s = get_session(mgr.active_session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Active session not found.")
    return SessionResponse(
        session_id=s["session_id"],
        title=s["title"],
        section=s.get("section", "Section A"),
        instructor_name=s.get("instructor_name", "Instructor"),
        start_time=str(s["start_time"]),
        end_time=str(s["end_time"]) if s.get("end_time") else None,
        is_active=bool(s.get("is_active", 0)),
        is_paused=mgr.is_paused,
        total_enrolled=s.get("total_enrolled", 0),
        total_present=s.get("total_present", 0),
        avg_engagement=s.get("avg_engagement", 0.0)
    )


@router.post("", response_model=SessionResponse)
async def create_new_session(
    payload: SessionCreateRequest,
    mgr: SessionManager = Depends(get_session_manager)
):
    new_id = mgr.start_new_session(
        title=payload.title,
        section=payload.section or "Section A",
        instructor=payload.instructor_name or "Instructor",
        total_enrolled=payload.total_enrolled or 6
    )
    s = get_session(new_id)
    return SessionResponse(
        session_id=s["session_id"],
        title=s["title"],
        section=s.get("section", "Section A"),
        instructor_name=s.get("instructor_name", "Instructor"),
        start_time=str(s["start_time"]),
        end_time=None,
        is_active=True,
        is_paused=False,
        total_enrolled=s.get("total_enrolled", 0),
        total_present=0,
        avg_engagement=0.0
    )


@router.post("/current/action")
async def execute_session_action(
    payload: SessionActionRequest,
    mgr: SessionManager = Depends(get_session_manager)
):
    action = payload.action.lower()
    if action == "pause":
        success = mgr.pause_session()
        return {"status": "paused" if success else "failed", "session_id": mgr.active_session_id}
    elif action == "resume":
        success = mgr.resume_session()
        return {"status": "active" if success else "failed", "session_id": mgr.active_session_id}
    elif action == "stop":
        success = mgr.stop_current_session()
        return {"status": "stopped" if success else "failed", "session_id": mgr.active_session_id}
    else:
        raise HTTPException(status_code=400, detail="Action must be 'pause', 'resume', or 'stop'")


@router.get("/{session_id}/events")
async def get_events(session_id: str):
    events = get_session_events(session_id, limit=50)
    return events
