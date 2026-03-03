"""Behavioral metrics Pydantic schemas."""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class KeystrokeEvent(BaseModel):
    key: str
    event_type: str  # "keydown" | "keyup"
    timestamp: float
    dwell_time: Optional[float] = None
    flight_time: Optional[float] = None


class MouseEvent(BaseModel):
    x: float
    y: float
    event_type: str  # "move" | "click" | "scroll"
    timestamp: float
    velocity: Optional[float] = None
    acceleration: Optional[float] = None


class RPPGMetric(BaseModel):
    heart_rate: float = Field(..., ge=30, le=220)
    hrv_rmssd: float
    hrv_sdnn: float
    timestamp: float


class MetricsPayload(BaseModel):
    session_id: str
    keystrokes: List[KeystrokeEvent] = []
    mouse_events: List[MouseEvent] = []
    rppg: Optional[RPPGMetric] = None
    text_sample: Optional[str] = None


class BurnoutRiskResponse(BaseModel):
    session_id: str
    risk_level: str                # "Low" | "Medium" | "High"
    risk_score: float              # 0.0 – 1.0
    confidence: float
    cmes_index: float
    hrv_score: float
    typing_irregularity: float
    mouse_stiffness: float
    sentiment_label: str
    top_drivers: List[dict]
    timestamp: datetime
