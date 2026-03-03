"""
CL-BEDS Authentication Routes
POST /auth/register
POST /auth/login
POST /auth/refresh
POST /auth/logout
GET  /auth/me
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import text

from app.auth import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.config import settings
from app.dependencies import CurrentUser, DBSession
from app.schemas.user import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
    UserRole,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: DBSession):
    """Create a new user account."""

    # Check if email already exists
    result = await db.execute(
        text("SELECT id FROM users WHERE email = :email"),
        {"email": payload.email},
    )
    if result.fetchone():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user_id = uuid.uuid4()
    hashed = hash_password(payload.password)

    await db.execute(
        text("""
            INSERT INTO users (id, email, full_name, role, password_hash, created_at)
            VALUES (:id, :email, :full_name, :role, :password_hash, :now)
        """),
        {
            "id": user_id,
            "email": payload.email,
            "full_name": payload.full_name,
            "role": payload.role.value,
            "password_hash": hashed,
            "now": datetime.now(tz=timezone.utc),
        },
    )

    logger.info("New user registered: %s (role=%s)", payload.email, payload.role)
    return UserOut(id=user_id, email=payload.email, full_name=payload.full_name, role=payload.role)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: DBSession):
    """Authenticate and return JWT tokens."""

    result = await db.execute(
        text("SELECT id, role, password_hash FROM users WHERE email = :email"),
        {"email": payload.email},
    )
    row = result.fetchone()

    if not row or not verify_password(payload.password, row.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user_id = str(row.id)
    access_token = create_access_token(
        subject=user_id,
        extra_claims={"role": row.role},
    )
    refresh_token = create_refresh_token(subject=user_id)

    # Persist refresh token (hashed) for rotation validation
    await db.execute(
        text("""
            INSERT INTO refresh_tokens (user_id, token_hash, created_at)
            VALUES (:uid, :tok, :now)
            ON CONFLICT (user_id) DO UPDATE
            SET token_hash = EXCLUDED.token_hash, created_at = EXCLUDED.created_at
        """),
        {
            "uid": user_id,
            "tok": hash_password(refresh_token),  # store hash only
            "now": datetime.now(tz=timezone.utc),
        },
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshTokenRequest, db: DBSession):
    """Exchange a refresh token for a new access token."""
    decoded = decode_token(payload.refresh_token)
    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a refresh token")

    user_id = decoded["sub"]

    result = await db.execute(
        text("SELECT role FROM users WHERE id = :uid"),
        {"uid": user_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    new_access = create_access_token(subject=user_id, extra_claims={"role": row.role})
    new_refresh = create_refresh_token(subject=user_id)

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ---------------------------------------------------------------------------
# Me
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserOut)
async def get_me(current_user: CurrentUser, db: DBSession):
    """Return the currently authenticated user's profile."""
    result = await db.execute(
        text("SELECT id, email, full_name, role FROM users WHERE id = :uid"),
        {"uid": current_user.sub},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserOut(id=row.id, email=row.email, full_name=row.full_name, role=UserRole(row.role))


# ---------------------------------------------------------------------------
# Logout (client-side token invalidation)
# ---------------------------------------------------------------------------

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: CurrentUser, db: DBSession):
    """Revoke the stored refresh token for this user."""
    await db.execute(
        text("DELETE FROM refresh_tokens WHERE user_id = :uid"),
        {"uid": current_user.sub},
    )
    return None
