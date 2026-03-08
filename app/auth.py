"""
CL-BEDS Auth Module
JWT creation/validation, password hashing, Supabase token verification.

Compatible with both calling conventions:
  create_access_token(user_id, email, role)
  create_access_token(subject=x, extra_claims={...})
"""

import time
from typing import Optional

import httpx
import jwt
from fastapi import HTTPException, status
from passlib.context import CryptContext

from app.config import settings


# -------------------------------------------------------------------
# Password Hashing
# -------------------------------------------------------------------

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _normalize_password(password: str) -> str:
    """
    bcrypt supports max 72 bytes.
    Prevents crashes when users enter very long passwords.
    """
    return password.encode("utf-8")[:72].decode("utf-8", "ignore")


def hash_password(plain: str) -> str:
    plain = _normalize_password(plain)
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    plain = _normalize_password(plain)
    return _pwd_context.verify(plain, hashed)


# -------------------------------------------------------------------
# Exceptions
# -------------------------------------------------------------------

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


# -------------------------------------------------------------------
# JWT Helpers
# -------------------------------------------------------------------

def _secret() -> str:
    return settings.get_jwt_secret()


# -------------------------------------------------------------------
# Access Token
# -------------------------------------------------------------------

def create_access_token(
    user_id: str = "",
    email: str = "",
    role: str = "student",
    *,
    subject: str = "",
    extra_claims: Optional[dict] = None,
) -> str:
    """
    Creates JWT access token.

    Supports:
        create_access_token(user_id="123")
        create_access_token(subject="123", extra_claims={...})
    """

    sub = subject or user_id

    if not sub:
        raise ValueError("create_access_token requires user_id or subject")

    now = int(time.time())

    payload = {
        "sub": sub,
        "email": email,
        "type": "access",
        "iat": now,
        "exp": now + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }

    # optional role support
    if role:
        payload["role"] = role

    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, _secret(), algorithm=settings.JWT_ALGORITHM)


# -------------------------------------------------------------------
# Refresh Token
# -------------------------------------------------------------------

def create_refresh_token(user_id: str = "", *, subject: str = "") -> str:

    sub = subject or user_id

    if not sub:
        raise ValueError("create_refresh_token requires user_id or subject")

    now = int(time.time())

    payload = {
        "sub": sub,
        "type": "refresh",
        "iat": now,
        "exp": now + settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    }

    return jwt.encode(payload, _secret(), algorithm=settings.JWT_ALGORITHM)


# -------------------------------------------------------------------
# Token Decode
# -------------------------------------------------------------------

def decode_access_token(token: str) -> dict:
    return _decode(token, expected_type="access")


def decode_token(token: str) -> dict:
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
        raise HTTPException(
            status_code=401,
            detail=f"Expected {expected_type} token",
        )

    return payload


# -------------------------------------------------------------------
# Supabase Token Verification
# -------------------------------------------------------------------

async def verify_supabase_token(token: str) -> Optional[dict]:

    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        return None

    url = f"{settings.SUPABASE_URL}/auth/v1/user"

    headers = {
        "Authorization": f"Bearer {token}",
        "apikey": settings.SUPABASE_ANON_KEY,
    }

    async with httpx.AsyncClient(timeout=5.0) as client:

        resp = await client.get(url, headers=headers)

        if resp.status_code == 200:
            return resp.json()

        return None
