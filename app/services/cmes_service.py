"""
CL-BEDS CMES Service
Cross-Modal Entropy Synchronization — measures entropy alignment across
keystroke, mouse, and HRV signals to detect cognitive load.

References:
  - Sample Entropy (SampEn) — Richman & Moorman (2000)
  - Cross Approximate Entropy (CrossApEn)
"""

import numpy as np
from typing import List


# ─────────────────────────────────────────────────────────────────────────────
# Core Entropy Functions
# ─────────────────────────────────────────────────────────────────────────────

def _template_matches(template: np.ndarray, data: np.ndarray, r: float) -> int:
    """Count how many length-m subsequences in data match the template within tolerance r."""
    count = 0
    m = len(template)
    for i in range(len(data) - m + 1):
        if np.max(np.abs(data[i:i+m] - template)) < r:
            count += 1
    return count


def sample_entropy(time_series: np.ndarray, m: int = 2, r_ratio: float = 0.2) -> float:
    """
    Sample Entropy (SampEn).

    Args:
        time_series: 1D numpy array
        m: template length
        r_ratio: tolerance as fraction of std dev

    Returns:
        SampEn value; NaN if computation fails
    """
    if len(time_series) < 2 * m + 10:
        return float("nan")

    ts = np.asarray(time_series, dtype=float)
    std = np.std(ts)
    if std == 0:
        return 0.0

    r = r_ratio * std
    N = len(ts)

    A = 0  # m+1 matches
    B = 0  # m   matches

    for i in range(N - m):
        template_m = ts[i:i+m]
        template_m1 = ts[i:i+m+1]

        for j in range(N - m):
            if i == j:
                continue
            if np.max(np.abs(ts[j:j+m] - template_m)) < r:
                B += 1
                if i < N - m and j < N - m:
                    if np.max(np.abs(ts[j:j+m+1] - template_m1)) < r:
                        A += 1

    if B == 0:
        return float("nan")

    return -np.log(A / B) if A > 0 else float("nan")


def cross_approximate_entropy(
    series_x: np.ndarray,
    series_y: np.ndarray,
    m: int = 2,
    r_ratio: float = 0.2,
) -> float:
    """
    Cross Approximate Entropy (CrossApEn).
    Measures the likelihood that patterns similar in series_x are also
    similar in series_y.

    Higher CrossApEn = less synchrony between modalities.
    """
    min_len = min(len(series_x), len(series_y))
    if min_len < m + 10:
        return float("nan")

    x = np.asarray(series_x[:min_len], dtype=float)
    y = np.asarray(series_y[:min_len], dtype=float)

    std = np.std(x)
    if std == 0:
        return 0.0
    r = r_ratio * std

    N = min_len
    C_m = 0
    C_m1 = 0

    for i in range(N - m):
        template = x[i:i+m]
        matches_m = sum(
            1 for j in range(N - m) if np.max(np.abs(y[j:j+m] - template)) < r
        )
        C_m += matches_m

        template1 = x[i:i+m+1]
        matches_m1 = sum(
            1 for j in range(N - m - 1) if np.max(np.abs(y[j:j+m+1] - template1)) < r
        )
        C_m1 += matches_m1

    if C_m == 0:
        return float("nan")

    phi_m = C_m / (N - m)
    phi_m1 = C_m1 / (N - m)

    if phi_m1 == 0 or phi_m == 0:
        return float("nan")

    return float(-np.log(phi_m1 / phi_m))


# ─────────────────────────────────────────────────────────────────────────────
# Rolling Window CMES
# ─────────────────────────────────────────────────────────────────────────────

def compute_cmes_index(
    keystroke_series: List[float],
    mouse_series: List[float],
    hrv_series: List[float],
    window_size: int = 30,
) -> dict:
    """
    Compute the Cross-Modal Entropy Synchronization (CMES) index.

    The CMES index measures the entropy mismatch across behavioral modalities.
    High CMES = high cognitive load / desynchronization.

    Pipeline:
      1. Compute SampEn for each modality
      2. Compute CrossApEn between pairs
      3. Aggregate into CMES index

    Returns dict with per-modality entropy and overall CMES index.
    """
    ks_arr = np.array(keystroke_series[-window_size:]) if keystroke_series else np.array([])
    ms_arr = np.array(mouse_series[-window_size:]) if mouse_series else np.array([])
    hv_arr = np.array(hrv_series[-window_size:]) if hrv_series else np.array([])

    # Sample entropy per modality
    ks_sampen = sample_entropy(ks_arr) if len(ks_arr) >= 10 else float("nan")
    ms_sampen = sample_entropy(ms_arr) if len(ms_arr) >= 10 else float("nan")
    hv_sampen = sample_entropy(hv_arr) if len(hv_arr) >= 10 else float("nan")

    # Cross entropies between pairs
    cross_ks_ms = cross_approximate_entropy(ks_arr, ms_arr) if len(ks_arr) >= 10 and len(ms_arr) >= 10 else float("nan")
    cross_ks_hv = cross_approximate_entropy(ks_arr, hv_arr) if len(ks_arr) >= 10 and len(hv_arr) >= 10 else float("nan")
    cross_ms_hv = cross_approximate_entropy(ms_arr, hv_arr) if len(ms_arr) >= 10 and len(hv_arr) >= 10 else float("nan")

    # Aggregate: mean of non-NaN values, fallback to 0
    all_values = [v for v in [ks_sampen, ms_sampen, hv_sampen, cross_ks_ms, cross_ks_hv, cross_ms_hv]
                  if not np.isnan(v)]
    cmes_index = float(np.mean(all_values)) if all_values else 0.0

    # Normalize to 0–1 range (typical SampEn range is 0–3)
    cmes_normalized = min(cmes_index / 3.0, 1.0)

    return {
        "ks_sample_entropy": round(ks_sampen if not np.isnan(ks_sampen) else 0.0, 4),
        "ms_sample_entropy": round(ms_sampen if not np.isnan(ms_sampen) else 0.0, 4),
        "hrv_sample_entropy": round(hv_sampen if not np.isnan(hv_sampen) else 0.0, 4),
        "cross_ks_ms": round(cross_ks_ms if not np.isnan(cross_ks_ms) else 0.0, 4),
        "cross_ks_hrv": round(cross_ks_hv if not np.isnan(cross_ks_hv) else 0.0, 4),
        "cross_ms_hrv": round(cross_ms_hv if not np.isnan(cross_ms_hv) else 0.0, 4),
        "cmes_raw": round(cmes_index, 4),
        "cmes_index": round(cmes_normalized, 4),
    }
   
