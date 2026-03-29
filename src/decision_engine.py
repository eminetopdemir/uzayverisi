"""
decision_engine.py  -  User Guidance Decision Support for SatCom
================================================================
This module provides recommendation logic for satellite communication
operators under space weather conditions. It does not control hardware.
It only produces decision-support outputs for human operators.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd


def _clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def _confidence_from_snr(snr: float, loss: float, mode: str) -> float:
    """
    Estimate confidence in the recommendation from SNR/Loss context.

    Higher absolute margin from decision boundaries increases confidence.
    Data loss contributes a small adjustment to represent consistency.
    """
    if mode == "SAFE":
        base = 0.72 + min(max((snr - 10.0) / 20.0, 0.0), 0.22)
    elif mode == "ADAPTIVE":
        # Confidence is strongest around the center of adaptive band.
        center_strength = 1.0 - min(abs(snr - 5.0) / 5.0, 1.0)
        base = 0.64 + 0.22 * center_strength
    else:  # PROTECTION
        base = 0.78 + min(abs(min(snr, 0.0)) / 15.0, 0.18)

    loss_adjust = _clip((loss - 50.0) / 300.0, -0.04, 0.06)
    confidence = _clip(base + loss_adjust, 0.55, 0.99)
    return round(confidence, 2)


def _operator_guidance(snr: float, loss: float) -> dict:
    """
    Create operator guidance from communication quality metrics.

    Parameters
    ----------
    snr : float
        Signal-to-noise ratio in dB.
    loss : float
        Data loss percentage.

    Returns
    -------
    dict
        Structured recommendation for a dashboard.
    """
    snr_v = float(snr)
    loss_v = float(loss)

    if snr_v > 10.0:
        mode = "SAFE"
        risk_level = "LOW"
        recommended_action = "Maintain high data rate and continue nominal operations"
        modulation = "256-QAM"
        power_adjustment = "0%"
        explanation = (
            "SNR is comfortably above the reliability threshold. "
            "Link quality is stable and current communication settings can be maintained."
        )
    elif snr_v >= 0.0:
        mode = "ADAPTIVE"
        risk_level = "MEDIUM"
        recommended_action = (
            "Reduce data rate gradually, increase FEC, and monitor the link in real time"
        )
        modulation = "QPSK / 16-QAM"
        power_adjustment = "0% to +10% (if margin continues to drop)"
        explanation = (
            "SNR is within a degradable operating region where packet errors can increase. "
            "Adaptive coding/modulation helps preserve service continuity."
        )
    else:
        mode = "PROTECTION"
        risk_level = "HIGH"
        recommended_action = (
            "Suspend non-critical transmissions and prioritize critical telemetry only"
        )
        modulation = "BPSK"
        power_adjustment = "+30%"
        explanation = (
            "Low SNR indicates severe noise conditions likely related to space weather. "
            "Communication reliability is compromised and protective operation is recommended."
        )

    confidence = _confidence_from_snr(snr_v, loss_v, mode)

    return {
        "snr": round(snr_v, 2),
        "loss": round(loss_v, 3),
        "mode": mode,
        "risk_level": risk_level,
        "recommended_action": recommended_action,
        "modulation": modulation,
        "power_adjustment": power_adjustment,
        "confidence": confidence,
        "explanation": explanation,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Public decision-layer entry point  (deterministic, rule-based, no ML)
# ─────────────────────────────────────────────────────────────────────────────

_RISK_TABLE: dict[str, tuple[str, int, str, str]] = {
    # risk → (action, datarate_mbps, message, explanation)
    "none": (
        "KEEP_NORMAL",
        100,
        "Nominal space weather. Maintain current data rate.",
        "No ionospheric disturbance detected. Link operating at full capacity.",
    ),
    "low": (
        "MONITOR",
        80,
        "Minor space weather activity. Monitor link quality.",
        "Slight ionospheric irregularities observed. Marginal SNR reduction expected.",
    ),
    "moderate": (
        "ADAPTIVE_REDUCTION",
        50,
        "Moderate space weather disturbance. Reduce data rate to preserve link quality.",
        "Elevated ionospheric activity causing measurable signal degradation.",
    ),
    "high": (
        "AGGRESSIVE_REDUCTION",
        20,
        "Severe space weather event in progress. Aggressive data-rate reduction required.",
        "Significant ionospheric disturbance causing serious signal degradation.",
    ),
    "severe": (
        "REDUCE_DATARATE",
        10,
        "Solar storm detected. Reduce data rate to maintain link stability.",
        "High ionospheric disturbance causing severe signal degradation.",
    ),
}


def generate_recommendation(model_output: dict) -> dict:
    """
    Deterministic, rule-based decision layer for satellite communication operators.

    Parameters
    ----------
    model_output : dict
        Must contain:
            snr  (float) – Signal-to-noise ratio in dB.
            loss (float) – Data loss percentage (0–100).
            risk (str)   – Risk level: "none" | "low" | "moderate" | "high" | "severe".

    Returns
    -------
    dict
        Structured operational recommendation with action, data-rate, priority,
        alert flag and human-readable explanation.
    """
    snr: float  = float(model_output["snr"])
    loss: float = float(model_output["loss"])
    risk: str   = str(model_output.get("risk", "none")).lower()

    # ── Risk → action mapping ────────────────────────────────────────────────
    if risk not in _RISK_TABLE:
        # Treat unknown risk values defensively as "moderate"
        risk = "moderate"

    action, datarate, message, explanation = _RISK_TABLE[risk]

    # ── Override: SNR < -5 forces minimum data rate ──────────────────────────
    if snr < -5.0:
        datarate = 10

    # ── Priority from loss percentage ────────────────────────────────────────
    if loss > 90.0:
        priority = "critical"
    elif loss >= 50.0:
        priority = "high"
    elif loss >= 20.0:
        priority = "medium"
    else:
        priority = "low"

    # ── Alert flag ───────────────────────────────────────────────────────────
    alert: bool = risk in ("high", "severe")

    return {
        "snr":                      round(snr, 2),
        "loss":                     round(loss, 2),
        "risk":                     risk,
        "action":                   action,
        "recommended_datarate_mbps": datarate,
        "message":                  message,
        "explanation":              explanation,
        "priority":                 priority,
        "alert":                    alert,
    }


def recommended_data_rate_mbps(snr: float, nominal_rate_mbps: float = 120.0) -> float:
    """
    Map SNR to an operator-recommended data rate profile (Mbps).

    SAFE        (SNR > 10 dB): 100% nominal rate
    ADAPTIVE    (0 to 10 dB):  linearly reduce from 100% to 35%
    PROTECTION  (SNR < 0 dB):  hold at 15% nominal (critical telemetry profile)
    """
    nominal = max(float(nominal_rate_mbps), 1.0)
    snr_v = float(snr)

    if snr_v > 10.0:
        ratio = 1.0
    elif snr_v >= 0.0:
        ratio = 0.35 + 0.65 * (snr_v / 10.0)
    else:
        ratio = 0.15

    return round(nominal * ratio, 3)


def build_data_rate_profile(
    times: Sequence,
    snr_values: Iterable[float],
    nominal_rate_mbps: float = 120.0,
) -> pd.DataFrame:
    """
    Build a time-indexed data-rate recommendation table from SNR values.
    """
    snr_arr = np.asarray(list(snr_values), dtype=float)
    if len(times) != len(snr_arr):
        raise ValueError("times and snr_values must have the same length")

    t_idx = pd.to_datetime(pd.Index(times), errors="coerce")
    if t_idx.isna().any():
        raise ValueError("times contains values that cannot be parsed as datetime")

    rates = [recommended_data_rate_mbps(v, nominal_rate_mbps) for v in snr_arr]
    modes = [_operator_guidance(v, 0.0)["mode"] for v in snr_arr]

    return pd.DataFrame(
        {
            "time": t_idx,
            "snr": snr_arr,
            "data_rate_mbps": rates,
            "mode": modes,
        }
    )


def plot_data_rate_over_time(
    times: Sequence,
    snr_values: Iterable[float],
    nominal_rate_mbps: float = 120.0,
    out_path: str | Path = "outputs/data_rate_guidance.png",
) -> Path:
    """
    Plot recommended data rate vs time based on SNR time series.

    The function only visualizes operator guidance and does not perform
    any autonomous control action.
    """
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    profile = build_data_rate_profile(times, snr_values, nominal_rate_mbps)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(12, 4.8))
    ax.plot(profile["time"], profile["data_rate_mbps"], color="#1d4ed8", lw=2.0)

    safe_mask = profile["mode"] == "SAFE"
    adaptive_mask = profile["mode"] == "ADAPTIVE"
    protection_mask = profile["mode"] == "PROTECTION"

    ax.scatter(profile.loc[safe_mask, "time"], profile.loc[safe_mask, "data_rate_mbps"],
               s=16, color="#16a34a", label="SAFE", alpha=0.9)
    ax.scatter(profile.loc[adaptive_mask, "time"], profile.loc[adaptive_mask, "data_rate_mbps"],
               s=16, color="#d97706", label="ADAPTIVE", alpha=0.9)
    ax.scatter(profile.loc[protection_mask, "time"], profile.loc[protection_mask, "data_rate_mbps"],
               s=16, color="#dc2626", label="PROTECTION", alpha=0.9)

    ax.set_title("Recommended Data Rate Over Time (Decision Support)")
    ax.set_xlabel("Time")
    ax.set_ylabel("Data Rate [Mbps]")
    ax.grid(alpha=0.3)
    ax.legend(frameon=False)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    fig.autofmt_xdate(rotation=25)

    plt.tight_layout()
    plt.savefig(out, dpi=150)
    plt.close(fig)

    return out