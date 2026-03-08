"""
CL-BEDS Profile Routes

PATCH  /profile/me              – update name / avatar
POST   /profile/change-password – change own password
DELETE /profile/delete-account  – permanently delete own account
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.auth import hash_password, verify_password
from app.dependencies import CurrentUser, DBSession

router = APIRouter()
logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Schemas
# -------------------------------------------------------------------

class UpdateProfilePayload(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    avatar_url: str | None = None


class ChangePasswordPayload(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class DeleteAccountPayload(BaseModel):
    password: str


# -------------------------------------------------------------------
# Update Profile
# -------------------------------------------------------------------

@router.patch("/me")
async def update_profile(
    payload: UpdateProfilePayload,
    current_user: CurrentUser,
    db: DBSession,
):
    """Update user full name or avatar."""

    updates = {}

    if payload.full_name is not None:
        updates["full_name"] = payload.full_name

    if payload.avatar_url is not None:
        updates["avatar_url"] = payload.avatar_url

    if not updates:
        raise HTTPException(status_code=400, detail="Nothing to update")

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)

    updates["uid"] = current_user.sub
    updates["now"] = datetime.now(timezone.utc)

    result = db.execute(
        text(f"""
            UPDATE users
            SET {set_clause}, updated_at = :now
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
# Change Password
# -------------------------------------------------------------------

@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordPayload,
    current_user: CurrentUser,
    db: DBSession,
):
    """Change password after verifying current password."""

    result = db.execute(
        text("SELECT password_hash FROM users WHERE id = :uid"),
        {"uid": current_user.sub},
    )

    row = result.fetchone()

    if not row or not verify_password(payload.current_password, row.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    new_hash = hash_password(payload.new_password)

    db.execute(
        text("UPDATE users SET password_hash = :ph, updated_at = NOW() WHERE id = :uid"),
        {"ph": new_hash, "uid": current_user.sub},
    )

    return None


# -------------------------------------------------------------------
# Delete Account
# -------------------------------------------------------------------

@router.delete("/delete-account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    payload: DeleteAccountPayload,
    current_user: CurrentUser,
    db: DBSession,
):
    """Delete user account permanently."""

    result = db.execute(
        text("SELECT password_hash FROM users WHERE id = :uid"),
        {"uid": current_user.sub},
    )

    row = result.fetchone()

    if not row or not verify_password(payload.password, row.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password is incorrect",
        )

    db.execute(
        text("DELETE FROM users WHERE id = :uid"),
        {"uid": current_user.sub},
    )

    logger.info("User %s deleted their account", current_user.sub)

    return None
