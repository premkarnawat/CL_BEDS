"""
CL-BEDS Dashboard Routes
GET  /dashboard/sessions
GET  /dashboard/sessions/{session_id}
GET  /dashboard/risk-trend
GET  /dashboard/latest-shap
POST /dashboard/sessions
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.dependencies import CurrentUser, DBSession, Pagination
from app.schemas.metrics import SHAPReport
from app.schemas.session import SessionCreate, SessionOut

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@router.post("/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(payload: SessionCreate, current_user: CurrentUser, db: DBSession):
    """Start a new monitoring session for the authenticated user."""
    session_id = uuid.uuid4()
    now = datetime.now(tz=timezone.utc)

    await db.execute(
        text("""
            INSERT INTO sessions (id, user_id, label, started_at)
            VALUES (:id, :uid, :label, :now)
        """),
        {"id": session_id, "uid": current_user.sub, "label": payload.label, "now": now},
    )

    return SessionOut(
        id=session_id,
        user_id=uuid.UUID(current_user.sub),
        label=payload.label,
        started_at=now,
        ended_at=None,
        final_risk_level=None,
        final_risk_score=None,
    )


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(current_user: CurrentUser, db: DBSession, pagination: Pagination):
    """Return paginated list of the user's sessions."""
    result = await db.execute(
        text("""
            SELECT id, user_id, label, started_at, ended_at,
                   final_risk_level, final_risk_score
            FROM sessions
            WHERE user_id = :uid
            ORDER BY started_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {"uid": current_user.sub, "limit": pagination.page_size, "offset": pagination.offset},
    )
    rows = result.fetchall()
    return [
        SessionOut(
            id=r.id,
            user_id=r.user_id,
            label=r.label,
            started_at=r.started_at,
            ended_at=r.ended_at,
            final_risk_level=r.final_risk_level,
            final_risk_score=r.final_risk_score,
        )
        for r in rows
    ]


@router.get("/sessions/{session_id}", response_model=SessionOut)
async def get_session(session_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    """Return a specific session by ID (must belong to current user)."""
    result = await db.execute(
        text("""
            SELECT id, user_id, label, started_at, ended_at,
                   final_risk_level, final_risk_score
            FROM sessions
            WHERE id = :sid AND user_id = :uid
        """),
        {"sid": session_id, "uid": current_user.sub},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    return SessionOut(
        id=row.id,
        user_id=row.user_id,
        label=row.label,
        started_at=row.started_at,
        ended_at=row.ended_at,
        final_risk_level=row.final_risk_level,
        final_risk_score=row.final_risk_score,
    )


# ---------------------------------------------------------------------------
# Risk trend (last N data points)
# ---------------------------------------------------------------------------

@router.get("/risk-trend")
async def get_risk_trend(
    current_user: CurrentUser,
    db: DBSession,
    limit: int = 50,
):
    """Return the last `limit` burnout risk scores for the user."""
    result = await db.execute(
        text("""
            SELECT bm.recorded_at, bm.risk_score, bm.risk_level,
                   bm.cmes_index, bm.hrv_stress, bm.backspace_ratio
            FROM behavioral_metrics bm
            JOIN sessions s ON s.id = bm.session_id
            WHERE s.user_id = :uid
            ORDER BY bm.recorded_at DESC
            LIMIT :limit
        """),
        {"uid": current_user.sub, "limit": min(limit, 200)},
    )
    rows = result.fetchall()
    return [
        {
            "timestamp": r.recorded_at.isoformat(),
            "risk_score": r.risk_score,
            "risk_level": r.risk_level,
            "cmes_index": r.cmes_index,
            "hrv_stress": r.hrv_stress,
            "backspace_ratio": r.backspace_ratio,
        }
        for r in reversed(rows)   # oldest first for charting
    ]


# ---------------------------------------------------------------------------
# Latest SHAP report
# ---------------------------------------------------------------------------

@router.get("/latest-shap", response_model=SHAPReport)
async def get_latest_shap(current_user: CurrentUser, db: DBSession):
    """Return the most recent SHAP report for the user."""
    result = await db.execute(
        text("""
            SELECT sr.risk_level, sr.confidence, sr.top_drivers, sr.session_id
            FROM shap_reports sr
            JOIN sessions s ON s.id = sr.session_id
            WHERE s.user_id = :uid
            ORDER BY sr.created_at DESC
            LIMIT 1
        """),
        {"uid": current_user.sub},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No SHAP report found")

    return SHAPReport(
        risk_level=row.risk_level,
        confidence=row.confidence,
        top_drivers=row.top_drivers,
        session_id=str(row.session_id),
    )
