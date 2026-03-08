"""
CL-BEDS FastAPI Dependencies
Annotated dependency shortcuts for use across all route modules.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth import decode_access_token
from app.database import get_db

bearer_scheme = HTTPBearer()


# ─── Token payload ────────────────────────────────────────────────────────

class TokenPayload:
    def __init__(self, sub: str, role: str, email: str):
        self.sub = sub
        self.role = role
        self.email = email


async def _get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> TokenPayload:

    payload = decode_access_token(credentials.credentials)

    if not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    return TokenPayload(
        sub=payload["sub"],
        role=payload.get("role", "student"),
        email=payload.get("email", ""),
    )


async def _require_admin(user: TokenPayload = Depends(_get_current_user)) -> TokenPayload:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


# ─── Annotated shortcuts ──────────────────────────────────────────────────

CurrentUser = Annotated[TokenPayload, Depends(_get_current_user)]
AdminUser = Annotated[TokenPayload, Depends(_require_admin)]
DBSession = Annotated[Session, Depends(get_db)]


# ─── Pagination helper ────────────────────────────────────────────────────

class PaginationParams:
    def __init__(self, page: int = 1, page_size: int = 20):
        self.page = max(1, page)
        self.page_size = min(max(1, page_size), 100)
        self.offset = (self.page - 1) * self.page_size


Pagination = Annotated[PaginationParams, Depends(PaginationParams)]
