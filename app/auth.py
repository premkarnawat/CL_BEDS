"""
CL-BEDS Auth Module
JWT creation/validation, password hashing, Supabase token verification.
"""

import time
from typing import Optional

import httpx
import jwt
from fastapi import HTTPException, status
from passlib.context import CryptContext

from app.config import settings

# ─── Password hashing ─────────────────────────────────────────────────────

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ─── JWT helpers ──────────────────────────────────────────────────────────

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def _secret() -> str:
    """Return the active JWT signing secret."""
    return settings.get_jwt_secret()


def create_access_token(subject: str, extra_claims=None) -> str:
    """Create a short-lived access JWT."""
    now = int(time.time())
    payload = {"sub": subject, "type": "access", "iat": now,
               "exp": now + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, _secret(), algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    """Create a long-lived refresh JWT."""
    now = int(time.time())
    payload = {
        "sub":  user_id,
        "type": "refresh",
        "iat":  now,
        "exp":  now + settings.REFRESH_TOKEN_EXPIRE_DAYS * 86_400,
    }
    return jwt.encode(payload, _secret(), algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate an access JWT. Raises HTTP 401 on failure."""
    return _decode(token, expected_type="access")


def decode_token(token: str) -> dict:
    """Decode any CL-BEDS JWT (access or refresh). Raises HTTP 401 on failure."""
    return _decode(token)


def _decode(token: str, expected_type: Optional[str] = None) -> dict:
    try:
        payload = jwt.decode(
            token,
            _secret(),
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise CREDENTIALS_EXCEPTION

    if expected_type and payload.get("type") != expected_type:
        raise HTTPException(status_code=401, detail=f"Expected {expected_type} token")

    return payload


# ─── Supabase token verification (optional) ───────────────────────────────

async def verify_supabase_token(token: str) -> Optional[dict]:
    """
    Verify a Supabase JWT by calling the Supabase auth API.
    Returns the user dict if valid, None otherwise.
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        return None
    url = f"{settings.SUPABASE_URL}/auth/v1/user"
    headers = {
        "Authorization": f"Bearer {token}",
        "apikey": settings.SUPABASE_ANON_KEY,
    }
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(url, headers=headers)
        return resp.json() if resp.status_code == 200 else None
