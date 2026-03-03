"""Session Pydantic schemas."""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SessionCreate(BaseModel):
    user_id: str
    device_info: Optional[str] = None


class SessionResponse(BaseModel):
    id: str
    user_id: str
    started_at: datetime
    ended_at: Optional[datetime]
    avg_risk_score: Optional[float]
    final_risk_level: Optional[str]

    class Config:
        from_attributes = True
