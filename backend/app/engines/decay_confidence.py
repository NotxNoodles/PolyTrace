"""Decay Adjusted Confidence (DAC) Algorithm.

Core insight: probability changes near resolution are mechanical (approaching 0
or 1), not informational.  A 15% spike 24h out with surging volume is alpha;
the same spike 5 minutes out is noise.

Formula:
    DAC(t) = |ΔP| × volume_surge × decay_weight(TTR)

    ΔP           = P(t) - P(t - lookback)
    volume_surge = V(t_window) / V_avg
    TTR          = (end_date - t) / 3600            hours to resolution
    decay_weight = σ(TTR; k, mid) = 1 / (1 + exp(-k × (TTR - mid)))

The sigmoid is centered at `mid` hours (default 6).  Signals with TTR > 12h
get near-full weight; signals with TTR < 2h get near-zero weight.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class DACParams:
    """Tunable parameters for the DAC calculation."""

    sigmoid_k: float = 0.15
    sigmoid_mid_hours: float = 6.0
    lookback_minutes: int = 60
    volume_surge_floor: float = 0.1
    # DAC thresholds for signal classification
    alpha_threshold: float = 0.10
    noise_ceiling: float = 0.03


DEFAULT_PARAMS = DACParams()


def sigmoid(x: float, k: float, mid: float) -> float:
    """Numerically stable sigmoid: 1 / (1 + exp(-k*(x - mid)))."""
    z = -k * (x - mid)
    if z > 500:
        return 0.0
    if z < -500:
        return 1.0
    return 1.0 / (1.0 + math.exp(z))


def compute_ttr(end_date: datetime, now: datetime | None = None) -> float:
    """Time-to-resolution in hours.  Returns 0.0 if already past."""
    now = now or datetime.now(timezone.utc)
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    delta = (end_date - now).total_seconds() / 3600.0
    return max(delta, 0.0)


def decay_weight(ttr_hours: float, params: DACParams = DEFAULT_PARAMS) -> float:
    """Sigmoid-based decay weight.  Near 1.0 for long TTR, near 0.0 at resolution."""
    return sigmoid(ttr_hours, params.sigmoid_k, params.sigmoid_mid_hours)


def compute_volume_surge(
    current_volume: float,
    avg_volume: float,
    floor: float | None = None,
) -> float:
    """Volume surge ratio, floored to avoid division by near-zero averages."""
    floor = floor if floor is not None else DEFAULT_PARAMS.volume_surge_floor
    denominator = max(avg_volume, floor)
    return current_volume / denominator


@dataclass(frozen=True)
class DACResult:
    """Output of a single DAC computation."""

    delta_p: float
    volume_surge: float
    ttr_hours: float
    decay_w: float
    dac_score: float
    signal: str  # "bullish_lead", "bearish_lead", or "noise"


def compute_dac(
    price_now: float,
    price_prev: float,
    current_volume: float,
    avg_volume: float,
    end_date: datetime,
    now: datetime | None = None,
    params: DACParams = DEFAULT_PARAMS,
) -> DACResult:
    """Compute the Decay Adjusted Confidence score.

    Parameters
    ----------
    price_now : float
        Current "Yes" token probability [0, 1].
    price_prev : float
        "Yes" token probability at (now - lookback).
    current_volume : float
        Volume in the recent window (e.g. last hour).
    avg_volume : float
        Historical average volume for the same window length.
    end_date : datetime
        Market resolution date.
    now : datetime | None
        Override for current time (useful for backtesting).
    params : DACParams
        Tunable parameters.

    Returns
    -------
    DACResult with the composite DAC score and signal classification.
    """
    delta_p = price_now - price_prev
    abs_delta = abs(delta_p)

    ttr = compute_ttr(end_date, now)
    dw = decay_weight(ttr, params)
    vs = compute_volume_surge(current_volume, avg_volume, params.volume_surge_floor)

    dac_score = abs_delta * vs * dw

    if dac_score >= params.alpha_threshold:
        signal = "bullish_lead" if delta_p > 0 else "bearish_lead"
    elif dac_score <= params.noise_ceiling:
        signal = "noise"
    else:
        signal = "bullish_lead" if delta_p > 0 else "bearish_lead"

    return DACResult(
        delta_p=delta_p,
        volume_surge=vs,
        ttr_hours=ttr,
        decay_w=dw,
        dac_score=dac_score,
        signal=signal,
    )


def compute_dac_timeseries(
    prices: list[tuple[datetime, float]],
    volumes: list[tuple[datetime, float]],
    end_date: datetime,
    lookback_points: int = 1,
    params: DACParams = DEFAULT_PARAMS,
) -> list[DACResult]:
    """Run DAC over aligned price+volume time-series.

    `prices` and `volumes` should be sorted ascending by timestamp and
    have the same length.  Each element is (timestamp, value).
    """
    if len(prices) != len(volumes):
        raise ValueError("prices and volumes must be same length")
    if len(prices) <= lookback_points:
        return []

    avg_vol = sum(v for _, v in volumes) / len(volumes) if volumes else 1.0

    results: list[DACResult] = []
    for i in range(lookback_points, len(prices)):
        ts_now, p_now = prices[i]
        _, p_prev = prices[i - lookback_points]
        _, v_now = volumes[i]

        results.append(
            compute_dac(
                price_now=p_now,
                price_prev=p_prev,
                current_volume=v_now,
                avg_volume=avg_vol,
                end_date=end_date,
                now=ts_now,
                params=params,
            )
        )

    return results
