"""
CL-BEDS Fusion Service
Combines keystroke, mouse, rPPG, CMES, and NLP features
using the PyTorch fusion model to produce a burnout risk score.
"""

import logging
import time
import uuid
from typing import Optional

import torch

from app.schemas.metrics import (
    CMESResult,
    FusionResult,
    KeystrokeFeatures,
    LiveRiskResponse,
    MouseFeatures,
    SHAPReport,
)
from app.services.shap_service import generate_shap_report

logger = logging.getLogger(__name__)

# Risk thresholds
_RISK_LOW_THRESHOLD = 0.35
_RISK_HIGH_THRESHOLD = 0.65


def _risk_label(score: float) -> str:
    if score < _RISK_LOW_THRESHOLD:
        return "Low"
    if score < _RISK_HIGH_THRESHOLD:
        return "Medium"
    return "High"


async def fuse_modalities(
    burnout_model,
    keystroke: KeystrokeFeatures,
    mouse: MouseFeatures,
    cmes: CMESResult,
    hrv_stress: float = 0.5,
    sentiment_score: float = 0.0,
    emotion: Optional[str] = None,
    session_id: Optional[str] = None,
) -> LiveRiskResponse:
    """
    Run the multimodal fusion pipeline and return a full LiveRiskResponse.

    Parameters
    ----------
    burnout_model     : loaded BurnoutModel instance
    keystroke         : extracted keystroke features
    mouse             : extracted mouse features
    cmes              : CMES result
    hrv_stress        : HRV-derived stress index 0–1
    sentiment_score   : RoBERTa negative sentiment score 0–1
    emotion           : top detected emotion label
    session_id        : optional session UUID string
    """

    # Build feature tensor [CMES, HRV, backspace_ratio, mouse_stiffness, sentiment]
    features = torch.tensor(
        [[
            cmes.cmes_index,
            hrv_stress,
            keystroke.backspace_ratio,
            mouse.stiffness_score,
            sentiment_score,
        ]],
        dtype=torch.float32,
    )

    # Model inference
    with torch.no_grad():
        raw_score, confidence = burnout_model.predict(features)

    risk_score = float(raw_score)
    confidence_val = float(confidence)
    risk_label = _risk_label(risk_score)

    fusion_result = FusionResult(
        risk_level=risk_label,
        risk_score=round(risk_score, 4),
        confidence=round(confidence_val, 4),
    )

    # SHAP explainability
    shap_report = generate_shap_report(
        burnout_model=burnout_model,
        features={
            "CMES":            cmes.cmes_index,
            "HRV_Stress":      hrv_stress,
            "Backspace_Ratio": keystroke.backspace_ratio,
            "Mouse_Stiffness": mouse.stiffness_score,
            "Sentiment":       sentiment_score,
        },
        risk_level=risk_label,
        confidence=confidence_val,
        session_id=session_id,
    )

    return LiveRiskResponse(
        session_id=session_id or str(uuid.uuid4()),
        timestamp=time.time(),
        keystroke_features=keystroke,
        mouse_features=mouse,
        cmes=cmes,
        emotion=emotion,
        fusion=fusion_result,
        shap=shap_report,
    )
