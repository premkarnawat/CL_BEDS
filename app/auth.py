"""
CL-BEDS Auth Module
JWT creation, verification, and Supabase token validation.
"""

import time
import httpx
import jwt
from typing import Optional
from fastapi import HTTPException, status
from app.config import get_settings

settings = get_settings()

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def create_access_token(user_id: str, email: str, role: str = "student") -> str:
    """Create a signed JWT for API access."""
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT. Raises 401 on failure."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise CREDENTIALS_EXCEPTION


async def verify_supabase_token(token: str) -> Optional[dict]:
    """
    Verify a Supabase JWT by calling the Supabase auth API.
    Returns the user dict if valid, None otherwise.
    """
    url = f"{settings.SUPABASE_URL}/auth/v1/user"
    headers = {
        "Authorization": f"Bearer {token}",
        "apikey": settings.SUPABASE_ANON_KEY,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            return resp.json()
        return None


# ─── Password hashing (bcrypt via passlib) ────────────────────────────────

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Hash a plain-text password with bcrypt."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return _pwd_context.verify(plain, hashed)
