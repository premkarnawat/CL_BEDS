"""
CL-BEDS SHAP Explainability Service

Generates structured SHAP-style feature attribution reports without
requiring the full shap library (which has heavy scipy/sklearn deps).

We implement a lightweight kernel-SHAP approximation using linear
perturbation analysis — production-safe and fast on CPU.
"""

import logging
from typing import Any, Dict, List, Optional

import torch

from app.schemas.metrics import SHAPReport

logger = logging.getLogger(__name__)

_FEATURE_NAMES = [
    "CMES",
    "HRV_Stress",
    "Backspace_Ratio",
    "Mouse_Stiffness",
    "Sentiment",
]

# Baseline (mean) feature values for SHAP perturbation
_BASELINE = {
    "CMES":            0.5,
    "HRV_Stress":      0.4,
    "Backspace_Ratio": 0.05,
    "Mouse_Stiffness": 0.3,
    "Sentiment":       0.2,
}

# Delta used for numerical gradient approximation
_DELTA = 0.05


def generate_shap_report(
    burnout_model,
    features: Dict[str, float],
    risk_level: str,
    confidence: float,
    session_id: Optional[str] = None,
) -> SHAPReport:
    """
    Compute SHAP-like feature attribution via numerical perturbation.

    For each feature:
      impact = (f(x + δ_i) - f(x - δ_i)) / (2δ)

    Positive impact → feature increases risk score.
    Negative impact → feature decreases risk score.

    Returns the top-5 drivers sorted by absolute impact.
    """
    try:
        feature_vector = [features.get(name, 0.0) for name in _FEATURE_NAMES]
        base_tensor = torch.tensor([feature_vector], dtype=torch.float32)

        with torch.no_grad():
            base_score, _ = burnout_model.predict(base_tensor)
        base_score = float(base_score)

        impacts: List[Dict[str, Any]] = []
        for i, name in enumerate(_FEATURE_NAMES):
            perturbed_plus = feature_vector.copy()
            perturbed_minus = feature_vector.copy()
            perturbed_plus[i] = min(perturbed_plus[i] + _DELTA, 1.0)
            perturbed_minus[i] = max(perturbed_minus[i] - _DELTA, 0.0)

            t_plus = torch.tensor([perturbed_plus], dtype=torch.float32)
            t_minus = torch.tensor([perturbed_minus], dtype=torch.float32)

            with torch.no_grad():
                s_plus, _ = burnout_model.predict(t_plus)
                s_minus, _ = burnout_model.predict(t_minus)

            gradient = (float(s_plus) - float(s_minus)) / (2 * _DELTA)
            # Scale by actual feature value deviation from baseline
            deviation = features.get(name, 0.0) - _BASELINE.get(name, 0.0)
            impact = round(gradient * deviation * 100, 2)  # percentage-scale

            impacts.append({"feature": name, "impact": impact})

        # Sort by absolute impact descending
        impacts.sort(key=lambda x: abs(x["impact"]), reverse=True)

        return SHAPReport(
            risk_level=risk_level,
            confidence=round(confidence, 4),
            top_drivers=impacts[:5],
            session_id=session_id,
        )

    except Exception as exc:
        logger.exception("SHAP report generation failed: %s", exc)
        # Fallback – return zero impacts
        return SHAPReport(
            risk_level=risk_level,
            confidence=round(confidence, 4),
            top_drivers=[{"feature": name, "impact": 0.0} for name in _FEATURE_NAMES],
            session_id=session_id,
        )
