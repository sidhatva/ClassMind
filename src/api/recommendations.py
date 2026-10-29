"""
ClassMind AI - Teaching Copilot Recommendations API Router.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from src.dependencies import get_session_manager
from src.services.session_manager import SessionManager
from src.database import get_latest_suggestions, update_recommendation_feedback
from src.schemas import RecommendationSchema, RecommendationFeedbackRequest

router = APIRouter(prefix="/api/recommendations", tags=["Teaching Copilot Recommendations"])


@router.get("", response_model=List[RecommendationSchema])
async def get_recommendations(
    session_id: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    mgr: SessionManager = Depends(get_session_manager)
):
    target_id = session_id or mgr.active_session_id
    suggestions = get_latest_suggestions(target_id, limit=limit)
    res = []
    for s in suggestions:
        res.append(RecommendationSchema(
            id=s["id"],
            alert_type=s["alert_type"],
            priority=s["priority"],
            title=s["title"],
            suggestion=s["suggestion"],
            rationale=s["rationale"],
            instructional_purpose=s["instructional_purpose"],
            triggering_signal=s["triggering_signal"],
            timestamp=str(s["timestamp"]),
            is_dismissed=bool(s.get("is_dismissed", 0)),
            is_helpful=s.get("is_helpful")
        ))
    return res


@router.post("/{rec_id}/feedback")
async def give_recommendation_feedback(
    rec_id: int,
    payload: RecommendationFeedbackRequest,
    mgr: SessionManager = Depends(get_session_manager)
):
    success = update_recommendation_feedback(
        rec_id=rec_id,
        is_dismissed=payload.is_dismissed,
        is_helpful=payload.is_helpful
    )
    if not success:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return {"status": "success", "id": rec_id, "updated": payload.dict(exclude_unset=True)}
