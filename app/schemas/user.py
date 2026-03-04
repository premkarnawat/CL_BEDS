from __future__ import annotations
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, EmailStr

class UserRole(str, Enum):
    student = "student"
    admin   = "admin"

class RegisterRequest(BaseModel):
    email:     EmailStr
    password:  str
    full_name: str
    role:      UserRole = UserRole.student

class LoginRequest(BaseModel):
    email:    EmailStr
    password: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int

class UserOut(BaseModel):
    id:         uuid.UUID
    email:      str
    full_name:  str
    role:       UserRole
    avatar_url: Optional[str] = None
    is_active:  bool = True
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}
