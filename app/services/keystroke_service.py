"""
CL-BEDS Keystroke Service
Analyzes keystroke dynamics to detect typing irregularity and cognitive load.
"""

import numpy as np
from typing import List
from app.schemas.metrics import KeystrokeEvent


def compute_typing_irregularity(events: List[KeystrokeEvent]) -> dict:
    """
    Compute typing irregularity metrics from keystroke events.

    Returns:
        - backspace_ratio: fraction of keys that are backspaces (error correction proxy)
        - mean_dwell_time: average key hold duration (ms)
        - std_dwell_time: std dev of dwell (higher = more irregular)
        - mean_flight_time: average inter-key interval (ms)
        - std_flight_time: std dev of flight time
        - irregularity_score: composite 0–1 score
    """
    if len(events) < 5:
        return _empty_keystroke_metrics()

    # Separate keys
    total_keys = len(events)
    backspace_count = sum(1 for e in events if e.key in ("Backspace", "Delete"))
    backspace_ratio = backspace_count / max(total_keys, 1)

    # Dwell times (ms) — use provided or estimate from consecutive down/up
    dwell_times = [e.dwell_time for e in events if e.dwell_time is not None and e.dwell_time > 0]
    flight_times = [e.flight_time for e in events if e.flight_time is not None and e.flight_time > 0]

    mean_dwell = float(np.mean(dwell_times)) if dwell_times else 120.0
    std_dwell = float(np.std(dwell_times)) if len(dwell_times) > 1 else 0.0
    mean_flight = float(np.mean(flight_times)) if flight_times else 200.0
    std_flight = float(np.std(flight_times)) if len(flight_times) > 1 else 0.0

    # Normalize components into 0–1
    # Backspace ratio: >20% is concerning
    br_norm = min(backspace_ratio / 0.20, 1.0)
    # Dwell std: >100ms is high irregularity
    dwell_norm = min(std_dwell / 100.0, 1.0)
    # Flight std: >300ms is high irregularity
    flight_norm = min(std_flight / 300.0, 1.0)

    irregularity_score = 0.4 * br_norm + 0.3 * dwell_norm + 0.3 * flight_norm

    return {
        "backspace_ratio": round(backspace_ratio, 4),
        "mean_dwell_time": round(mean_dwell, 2),
        "std_dwell_time": round(std_dwell, 2),
        "mean_flight_time": round(mean_flight, 2),
        "std_flight_time": round(std_flight, 2),
        "irregularity_score": round(float(irregularity_score), 4),
    }


def _empty_keystroke_metrics() -> dict:
    return {
        "backspace_ratio": 0.0,
        "mean_dwell_time": 0.0,
        "std_dwell_time": 0.0,
        "mean_flight_time": 0.0,
        "std_flight_time": 0.0,
        "irregularity_score": 0.0,
    }
