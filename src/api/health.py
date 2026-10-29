"""
ClassMind AI - Health & Hardware Diagnostics API Router.
"""

from fastapi import APIRouter, Depends
from src.dependencies import get_session_manager
from src.services.session_manager import SessionManager
from src.schemas import SystemHealthResponse, HardwareStatus

router = APIRouter(prefix="/api/health", tags=["Health & Diagnostics"])


@router.get("", response_model=SystemHealthResponse)
async def get_system_health(mgr: SessionManager = Depends(get_session_manager)):
    hw = mgr.get_hardware_status()
    return SystemHealthResponse(
        status="healthy",
        app_name="ClassMind AI",
        version="2.0.0",
        offline_mode=True,
        hardware=HardwareStatus(**hw),
        active_session_id=mgr.active_session_id
    )
