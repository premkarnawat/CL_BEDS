"""
CL-BEDS Mouse Service
Computes mouse movement stiffness, velocity, and micro-tremor indicators.
"""

import numpy as np
from typing import List
from app.schemas.metrics import MouseEvent


def compute_mouse_stiffness(events: List[MouseEvent]) -> dict:
    """
    Mouse stiffness measures how rigid/jerky mouse movement is.

    High stiffness correlates with fatigue and cognitive load.

    Returns:
        - mean_velocity: average pixel/ms velocity
        - velocity_variance: variance of velocity
        - direction_changes: number of sharp direction changes
        - stiffness_score: composite 0–1 score
    """
    move_events = [e for e in events if e.event_type == "move"]
    if len(move_events) < 10:
        return _empty_mouse_metrics()

    xs = np.array([e.x for e in move_events])
    ys = np.array([e.y for e in move_events])
    ts = np.array([e.timestamp for e in move_events])

    # Velocities between consecutive points
    dx = np.diff(xs)
    dy = np.diff(ys)
    dt = np.diff(ts)
    dt = np.where(dt == 0, 1e-6, dt)  # avoid division by zero

    distances = np.sqrt(dx**2 + dy**2)
    velocities = distances / dt

    mean_vel = float(np.mean(velocities))
    vel_var = float(np.var(velocities))

    # Direction changes: dot product of consecutive direction vectors
    direction_vecs = np.column_stack([dx, dy])
    norms = np.linalg.norm(direction_vecs, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1e-6, norms)
    unit_vecs = direction_vecs / norms

    if len(unit_vecs) > 1:
        dot_products = np.sum(unit_vecs[:-1] * unit_vecs[1:], axis=1)
        direction_changes = int(np.sum(dot_products < 0))  # negative dot = direction reversal
    else:
        direction_changes = 0

    # Normalize for score
    # Velocity variance > 50000 is very erratic
    vel_norm = min(vel_var / 50000.0, 1.0)
    # Direction changes: >30 per 100 events is high
    dc_rate = direction_changes / max(len(move_events), 1)
    dc_norm = min(dc_rate / 0.30, 1.0)

    stiffness_score = 0.5 * vel_norm + 0.5 * dc_norm

    return {
        "mean_velocity": round(mean_vel, 4),
        "velocity_variance": round(vel_var, 4),
        "direction_changes": direction_changes,
        "stiffness_score": round(float(stiffness_score), 4),
    }


def _empty_mouse_metrics() -> dict:
    return {
        "mean_velocity": 0.0,
        "velocity_variance": 0.0,
        "direction_changes": 0,
        "stiffness_score": 0.0,
    }
