"""
CL-BEDS rPPG Service
Heart Rate Variability (HRV) computation from rPPG measurements.
"""

import numpy as np
from typing import List, Optional
from app.schemas.metrics import RPPGMetric


def compute_hrv_score(rppg_metric: Optional[RPPGMetric]) -> dict:
    """
    Compute an HRV-based stress score from rPPG data.

    Low HRV (low RMSSD) correlates with high stress/burnout.
    Normal RMSSD: 20–50ms; below 20ms is concerning.

    Returns:
        - heart_rate: BPM
        - rmssd: root mean square of successive differences (ms)
        - sdnn: std dev of NN intervals (ms)
        - hrv_score: 0–1 (0 = optimal HRV, 1 = very low HRV / high stress)
    """
    if rppg_metric is None:
        return _empty_hrv_metrics()

    hr = rppg_metric.heart_rate
    rmssd = rppg_metric.hrv_rmssd
    sdnn = rppg_metric.hrv_sdnn

    # Normalize: RMSSD < 10ms = max stress, 50ms+ = normal
    rmssd_norm = max(0.0, 1.0 - (rmssd / 50.0))
    rmssd_norm = min(rmssd_norm, 1.0)

    # High HR (>90 at rest) adds stress signal
    hr_norm = min(max((hr - 60) / 40.0, 0.0), 1.0)

    hrv_score = 0.7 * rmssd_norm + 0.3 * hr_norm

    return {
        "heart_rate": round(float(hr), 1),
        "rmssd": round(float(rmssd), 2),
        "sdnn": round(float(sdnn), 2),
        "hrv_score": round(float(hrv_score), 4),
    }


def _empty_hrv_metrics() -> dict:
    return {
        "heart_rate": 0.0,
        "rmssd": 0.0,
        "sdnn": 0.0,
        "hrv_score": 0.0,
    }
