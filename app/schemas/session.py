from __future__ import annotations
import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class SessionCreate(BaseModel):
    user_id: Optional[str] = None
    label: Optional[str] = None


class SessionOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    label: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    final_risk_level: Optional[str] = None
    final_risk_score: Optional[float] = None
    model_config = {"from_attributes": True}


class ChatMessageIn(BaseModel):
    content: str
    session_id: Optional[str] = None


class ChatMessageOut(BaseModel):
    role: str
    content: str
    timestamp: Optional[datetime] = None
    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    reply: str
    session_id: Optional[str] = None
    tokens_used: Optional[int] = None


class JournalEntryCreate(BaseModel):
    content: str
    mood_score: Optional[float] = None
    tags: Optional[List[str]] = None


class JournalEntryOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    content: str
    mood_score: Optional[float] = None
    tags: Optional[List[str]] = None
    detected_emotion: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}
