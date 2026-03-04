from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel


class KeystrokeEvent(BaseModel):
    timestamp: float
    key: str
    event_type: str
    hold_time_ms: Optional[float] = None
    flight_time_ms: Optional[float] = None


class MouseEvent(BaseModel):
    timestamp: float
    event_type: str
    x: float
    y: float
    velocity: Optional[float] = None


class RPPGMetric(BaseModel):
    timestamp: float
    bpm: float
    hrv_sdnn: Optional[float] = None
    hrv_rmssd: Optional[float] = None
    signal_quality: Optional[float] = None


class MetricsBatch(BaseModel):
    type: str = "metrics_batch"
    session_id: Optional[str] = None
    keystrokes: List[KeystrokeEvent] = []
    mouse_events: List[MouseEvent] = []
    rppg: Optional[RPPGMetric] = None
    text_snippet: Optional[str] = None


class KeystrokeFeatures(BaseModel):
    avg_hold_time_ms: float = 0
    avg_flight_time_ms: float = 0
    backspace_ratio: float = 0
    typing_speed_wpm: float = 0
    irregularity_score: float = 0


class MouseFeatures(BaseModel):
    avg_velocity: float = 0
    avg_acceleration: float = 0
    stiffness_score: float = 0
    idle_ratio: float = 0


class CMESResult(BaseModel):
    cmes_index: float = 0
    sample_entropy_ks: float = 0
    sample_entropy_mouse: float = 0
    cross_approx_entropy: float = 0


class FusionResult(BaseModel):
    risk_level: str = "Low"
    risk_score: float = 0.0
    confidence: float = 0.0


class SHAPDriver(BaseModel):
    feature: str
    impact: float


class SHAPReport(BaseModel):
    risk_level: str
    confidence: float
    top_drivers: List[SHAPDriver]
    session_id: Optional[str] = None


class LiveRiskResponse(BaseModel):
    session_id: str
    timestamp: float
    keystroke_features: Optional[KeystrokeFeatures] = None
    mouse_features: Optional[MouseFeatures] = None
    cmes: Optional[CMESResult] = None
    emotion: Optional[str] = None
    fusion: FusionResult
    shap: SHAPReport
