"""
CL-BEDS Admin Routes

GET    /admin/stats
GET    /admin/users
GET    /admin/users/{user_id}
PATCH  /admin/users/{user_id}
POST   /admin/users/{user_id}/reset-password
DELETE /admin/users/{user_id}
GET    /admin/sessions
DELETE /admin/sessions/{session_id}
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.auth import hash_password
from app.dependencies import AdminUser, DBSession, Pagination

router = APIRouter()
logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Admin Stats
# -------------------------------------------------------------------

@router.get("/stats")
async def get_stats(_admin: AdminUser, db: DBSession):

    today = datetime.now(timezone.utc).date()

    rows = db.execute(text("SELECT COUNT(*) FROM users"))
    total_users = rows.scalar() or 0

    rows = db.execute(
        text("SELECT COUNT(*) FROM sessions WHERE started_at::date = :today"),
        {"today": today},
    )
    active_today = rows.scalar() or 0

    rows = db.execute(text("SELECT COUNT(*) FROM sessions"))
    total_sessions = rows.scalar() or 0

    rows = db.execute(text("SELECT COUNT(*) FROM journal_entries"))
    total_journal = rows.scalar() or 0

    rows = db.execute(text("SELECT COUNT(*) FROM chat_logs"))
    total_chat = rows.scalar() or 0

    return {
        "total_users": total_users,
        "active_sessions_today": active_today,
        "total_sessions": total_sessions,
        "total_journal_entries": total_journal,
        "total_chat_messages": total_chat,
    }


# -------------------------------------------------------------------
# List Users
# -------------------------------------------------------------------

@router.get("/users")
async def list_users(_admin: AdminUser, db: DBSession, pagination: Pagination, search: str = ""):

    query = """
        SELECT id, email, full_name, avatar_url, is_active, created_at
        FROM users
        WHERE (:search = '' OR email ILIKE :pattern OR full_name ILIKE :pattern)
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """

    result = db.execute(
        text(query),
        {
            "search": search,
            "pattern": f"%{search}%",
            "limit": pagination.page_size,
            "offset": pagination.offset,
        },
    )

    return [
        {
            "id": str(r.id),
            "email": r.email,
            "full_name": r.full_name,
            "avatar_url": r.avatar_url,
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in result.fetchall()
    ]


# -------------------------------------------------------------------
# Get Single User
# -------------------------------------------------------------------

@router.get("/users/{user_id}")
async def get_user(user_id: uuid.UUID, _admin: AdminUser, db: DBSession):

    result = db.execute(
        text("""
        SELECT id, email, full_name, avatar_url, is_active, created_at
        FROM users
        WHERE id = :uid
        """),
        {"uid": user_id},
    )

    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": str(row.id),
        "email": row.email,
        "full_name": row.full_name,
        "avatar_url": row.avatar_url,
        "is_active": row.is_active,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


# -------------------------------------------------------------------
# Update User
# -------------------------------------------------------------------

@router.patch("/users/{user_id}")
async def update_user(user_id: uuid.UUID, payload: dict, _admin: AdminUser, db: DBSession):

    allowed = {"full_name", "avatar_url", "is_active"}

    updates = {k: v for k, v in payload.items() if k in allowed}

    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)

    updates["uid"] = user_id

    result = db.execute(
        text(f"""
        UPDATE users
        SET {set_clause}, updated_at = NOW()
        WHERE id = :uid
        RETURNING id, email, full_name, avatar_url, is_active
        """),
        updates,
    )

    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": str(row.id),
        "email": row.email,
        "full_name": row.full_name,
        "avatar_url": row.avatar_url,
        "is_active": row.is_active,
    }


# -------------------------------------------------------------------
# Reset Password
# -------------------------------------------------------------------

@router.post("/users/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_user_password(user_id: uuid.UUID, payload: dict, _admin: AdminUser, db: DBSession):

    new_password = payload.get("new_password", "")

    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    hashed = hash_password(new_password)

    result = db.execute(
        text("""
        UPDATE users
        SET password_hash = :ph, updated_at = NOW()
        WHERE id = :uid
        RETURNING id
        """),
        {"ph": hashed, "uid": user_id},
    )

    if not result.fetchone():
        raise HTTPException(status_code=404, detail="User not found")

    return None


# -------------------------------------------------------------------
# Delete User
# -------------------------------------------------------------------

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: uuid.UUID, _admin: AdminUser, db: DBSession):

    result = db.execute(
        text("DELETE FROM users WHERE id = :uid RETURNING id"),
        {"uid": user_id},
    )

    if not result.fetchone():
        raise HTTPException(status_code=404, detail="User not found")

    logger.warning("Admin deleted user %s", user_id)

    return None


# -------------------------------------------------------------------
# List Sessions
# -------------------------------------------------------------------

@router.get("/sessions")
async def list_all_sessions(_admin: AdminUser, db: DBSession, pagination: Pagination):

    result = db.execute(
        text("""
        SELECT id, user_id, label, started_at, ended_at,
               final_risk_level, final_risk_score
        FROM sessions
        ORDER BY started_at DESC
        LIMIT :limit OFFSET :offset
        """),
        {
            "limit": pagination.page_size,
            "offset": pagination.offset,
        },
    )

    return [
        {
            "id": str(r.id),
            "user_id": str(r.user_id),
            "label": r.label,
            "started_at": r.started_at.isoformat(),
            "ended_at": r.ended_at.isoformat() if r.ended_at else None,
            "final_risk_level": r.final_risk_level,
            "final_risk_score": float(r.final_risk_score) if r.final_risk_score else None,
        }
        for r in result.fetchall()
    ]


# -------------------------------------------------------------------
# Delete Session
# -------------------------------------------------------------------

@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: uuid.UUID, _admin: AdminUser, db: DBSession):

    result = db.execute(
        text("DELETE FROM sessions WHERE id = :sid RETURNING id"),
        {"sid": session_id},
    )

    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Session not found")

    return None
