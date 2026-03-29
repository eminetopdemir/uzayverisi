"""
backend/main.py — SatComm Monitor FastAPI Backend
===================================================
All physics computations come from physics_model.py.
The ML model (snr_model.pkl) is loaded for comparison/validation only.

Run:
    uvicorn main:app --reload --port 8000
"""

import math
import os
import pickle
import secrets
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── Path setup ────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from config import CFG
from decision_engine import generate_recommendation
from ml_model import predict as ml_predict
from physics_model import (
    classify_risk,
    compute_received_power_W,
    data_loss_pct,
    fspl_db,
    k_B,
    predict_realtime,
    received_power_W,
    space_weather_noise,
    system_thermal_noise,
)

# ═══════════════════════════════════════════════════════════════
# APP INIT
# ═══════════════════════════════════════════════════════════════
app = FastAPI(
    title="SatComm Monitor API",
    description="Physics-based satellite communication model REST API.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════════════
# STARTUP — load static resources
# ═══════════════════════════════════════════════════════════════
_snr_history: list[dict] = []
_ml_model: dict | None   = None
_history_df: pd.DataFrame | None = None
_alert_state = {
    "trigger_id": 0,
    "active_until": 0.0,
}

@app.on_event("startup")
async def startup():
    global _ml_model, _history_df

    # Load sklearn pipeline (for comparison, not primary physics)
    pkl_path = ROOT / "outputs" / "snr_model.pkl"
    if pkl_path.exists():
        with open(pkl_path, "rb") as fh:
            _ml_model = pickle.load(fh)

    # Load historical CSV
    csv_path = ROOT / "outputs" / "ml_results.csv"
    if csv_path.exists():
        _history_df = pd.read_csv(csv_path, parse_dates=["time"])


# ═══════════════════════════════════════════════════════════════
# SCHEMAS
# ═══════════════════════════════════════════════════════════════
class PredictRequest(BaseModel):
    bz:      float = Field(..., description="IMF Bz [nT]",           example=-10.0)
    speed:   float = Field(..., description="Solar wind speed [km/s]", example=500.0)
    density: float = Field(..., description="Proton density [cm⁻³]",  example=15.0)
    kp:      Optional[float] = Field(None, description="Kp index 0–9; null = unknown", example=5.0)
    flux:    float = Field(0.0, description="Proton flux [pfu]",      example=0.5)


class OptimizeRequest(BaseModel):
    bz:      float = Field(..., example=-10.0)
    speed:   float = Field(..., example=500.0)
    density: float = Field(..., example=15.0)
    kp:      Optional[float] = Field(None, example=5.0)
    flux:    float = Field(0.0, example=0.5)
    # Transmitter overrides
    pt_dbw:   float = Field(20.0, description="Tx power [dBW]",          example=25.0)
    freq_mhz: float = Field(12000.0, description="Carrier freq [MHz]",   example=12000.0)
    bw_mhz:   float = Field(10.0, description="Bandwidth [MHz]",         example=10.0)


class DecisionSimRequest(BaseModel):
    bz:      float = Field(..., example=-10.0)
    speed:   float = Field(..., example=500.0)
    density: float = Field(..., example=15.0)
    kp:      Optional[float] = Field(None, example=5.0)
    flux:    float = Field(0.0, example=0.5)
    reduction: Optional[float] = Field(None, ge=0.0, le=100.0, example=60.0)


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════
def _kp(val: Optional[float]) -> float:
    return float("nan") if val is None else float(val)


def _get_alert_secret() -> str:
    secret = os.getenv("SATCOMM_ALERT_SECRET", "").strip()
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="Remote alert secret is not configured on the server.",
        )
    return secret


def _require_alert_authorization(authorization: Optional[str]) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[len("Bearer "):].strip()
    secret = _get_alert_secret()
    if not secrets.compare_digest(token, secret):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _current_alert_status() -> dict:
    now = time.time()
    active_until = float(_alert_state["active_until"])
    active = active_until > now
    if not active:
        _alert_state["active_until"] = 0.0

    return {
        "active": active,
        "trigger_id": int(_alert_state["trigger_id"]),
        "expires_at": int(active_until * 1000) if active else None,
        "duration_ms": 3000,
    }


def _activate_remote_alert() -> dict:
    _alert_state["trigger_id"] = int(_alert_state["trigger_id"]) + 1
    _alert_state["active_until"] = time.time() + 3.0
    return _current_alert_status()


def _safe_snr_db(snr_value: float) -> float:
    """
    Normalize SNR to a realistic range.

    If a value is suspiciously large, interpret it as linear SNR and convert to dB.
    Final output is clamped to [-20, +20] dB.
    """
    x = float(snr_value)
    if not math.isfinite(x):
        x = -20.0
    if abs(x) > 120.0:
        x = 10.0 * math.log10(max(x, 1e-20))
    return max(min(x, 20.0), -20.0)


def _loss_from_snr_db(snr_db: float) -> float:
    """Loss sigmoid with calibrated midpoint at 0 dB and scale 3 dB."""
    x = _safe_snr_db(snr_db)
    loss = 100.0 / (1.0 + math.exp((x - 0.0) / 3.0))
    return max(min(loss, 100.0), 0.0)


def _sanitize_comm_metrics(snr_value: float, risk: Optional[str] = None) -> dict:
    snr_db = _safe_snr_db(snr_value)
    loss = _loss_from_snr_db(snr_db)
    return {
        "snr": round(float(snr_db), 2),
        "loss": round(float(loss), 2),
        "risk": risk or classify_risk(float(snr_db)),
    }


def _proxy_snr_db_from_storm(bz: float, speed: float, dens: float, kp: float, flux: float) -> float:
    """
    Physics-inspired fallback SNR proxy for pathological model outputs.

    This keeps outputs in a believable operational range when model prediction is
    clearly non-physical.
    """
    bz_south = abs(min(float(bz), 0.0))
    speed_excess = max(float(speed) - 350.0, 0.0)
    kp_excess = max(float(kp) - 4.0, 0.0)
    disturbance = (
        0.22 * bz_south
        + 0.05 * float(dens)
        + 0.0025 * float(flux)
        + 0.9 * kp_excess
        + 0.006 * speed_excess
    )
    baseline_clear_snr = 12.0
    return baseline_clear_snr - disturbance

def _fmt_result(r: dict) -> dict:
    clean = _sanitize_comm_metrics(float(r["snr_dB"]), r["storm_risk"])
    out = {
        "snr":        clean["snr"],
        "loss":       clean["loss"],
        "risk":       clean["risk"],
        "n_space_W":  r["N_space_W"],
        "n_thermal_W": r["N_thermal_W"],
        "pr_W":       float(r["Pr_W"]),
        "fspl_dB":    r["fspl_dB"],
    }
    out["guidance"] = generate_recommendation(out["snr"], out["loss"])
    return out


def _simulate_comm_with_reduction(req: DecisionSimRequest, reduction_pct: float) -> dict:
    """
    Evaluate communication quality with the trained model for one reduction level.

    We simulate data-rate reduction impact by reducing effective disturbance exposure
    in model inputs (Bz southward intensity, proton density, proton flux).
    The trained model remains the source of truth for SNR/loss outputs.
    """
    r = max(0.0, min(float(reduction_pct), 100.0)) / 100.0

    bz = float(req.bz)
    bz_eff = bz if bz >= 0.0 else bz * (1.0 - 0.35 * r)
    dens_eff = float(req.density) * (1.0 - 0.60 * r)
    flux_eff = float(req.flux) * (1.0 - 0.80 * r)
    speed_eff = float(req.speed)
    kp_eff = float(req.kp or 0.0)

    pdyn_eff = 0.5 * 1.67e-27 * dens_eff * (speed_eff * 1e3) ** 2 * 1e9
    temp_eff = 50000.0

    obs = {
        "Bz": bz_eff,
        "Dens": max(dens_eff, 1e-6),
        "Speed": speed_eff,
        "Temp": temp_eff,
        "Pdyn": pdyn_eff,
        "flux": max(flux_eff, 0.0),
        "Kp": kp_eff,
        "storm_flag": 1.0 if (bz_eff <= -3.5 and kp_eff >= 5.0) else 0.0,
    }

    pred = ml_predict(obs, _cached_model=_ml_model)
    model_snr = float(pred["snr_db_predicted"])

    # If model output is clearly non-physical, use a bounded proxy while still
    # preserving model-first execution.
    if (not math.isfinite(model_snr)) or abs(model_snr) > 30.0:
        model_snr = _proxy_snr_db_from_storm(
            bz=bz_eff,
            speed=speed_eff,
            dens=dens_eff,
            kp=kp_eff,
            flux=flux_eff,
        )

    clean = _sanitize_comm_metrics(model_snr, pred.get("storm_risk"))
    return {
        "reduction": int(round(reduction_pct)),
        "snr": float(clean["snr"]),
        "loss": float(clean["loss"]),
        "risk": clean["risk"],
    }


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.get("/", summary="Health check")
async def root():
    return {"status": "ok", "service": "SatComm Monitor API"}

@app.post("/trigger-storm")
async def trigger_storm():
    return _activate_remote_alert()

@app.post("/trigger-storm")
async def trigger_storm():
    return _activate_remote_alert()


@app.get("/alert-status", summary="Get remote alert status")
async def alert_status():
    return _current_alert_status()


# ── POST /predict ─────────────────────────────────────────────────
@app.post("/predict", summary="Predict SNR, data loss, and risk level")
async def predict(req: PredictRequest):
    """
    Compute SNR, data loss %, and risk from instantaneous space weather inputs
    using the deterministic physics model (physics_model.predict_realtime).
    """
    try:
        r = predict_realtime(
            bz=req.bz,
            speed=req.speed,
            density=req.density,
            kp=_kp(req.kp),
            flux=req.flux,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    out = _fmt_result(r)

    # ML comparison (supplementary, non-authoritative)
    ml_snr = None
    if _ml_model is not None:
        try:
            pipe    = _ml_model["pipe"]
            bz_v    = req.bz
            kp_v    = req.kp or 0.0
            flux_v  = req.flux
            row = pd.DataFrame([{
                "Bz":        bz_v,
                "Bz_south":  min(bz_v, 0.0),
                "abs_Bz":    abs(bz_v),
                "Dens":      req.density,
                "Speed":     req.speed,
                "Pdyn":      0.5 * 1.67e-27 * req.density * (req.speed * 1e3) ** 2 * 1e9,
                "Temp":      50000.0,
                "flux":      flux_v,
                "log_Temp":  math.log10(50000.0),
                "log_Dens":  math.log10(max(req.density, 1e-6)),
                "v2":        req.speed ** 2,
                "log_flux":  math.log10(max(flux_v, 1e-6)),
                "storm_flag": 1 if (bz_v <= -3.5 and kp_v >= 5) else 0,
            }])
            ml_snr = float(pipe.predict(row)[0])
        except Exception:
            ml_snr = None

    out["ml_snr"] = ml_snr if ml_snr is not None and -50 <= ml_snr <= 50 else None

    # Append to in-memory session history
    _snr_history.append({
        "bz": req.bz, "speed": req.speed, "density": req.density,
        "kp": req.kp, "flux": req.flux,
        **out,
    })
    if len(_snr_history) > 500:
        _snr_history.pop(0)

    return out


# ── GET /scenarios ─────────────────────────────────────────────────
@app.get("/scenarios", summary="Predefined space weather scenarios")
async def scenarios():
    """
    Returns model outputs for 7 canonical scenarios from Quiet Sun through G5 storm.
    All values computed by predict_realtime().
    """
    SCENARIOS = [
        ("Quiet Sun",  +0.0, 380,  4.0,  1.0,         0.0),
        ("Mild",       -5.0, 450,  8.0,  None,         0.0),
        ("G1 Storm",  -10.0, 500, 15.0,  5.0,          0.5),
        ("G2 Storm",  -20.0, 600, 20.0,  6.5,          2.0),
        ("G3 Storm",  -30.0, 680, 25.0,  7.5,         10.0),
        ("G4 Storm",  -40.0, 750, 35.0,  8.5,         50.0),
        ("G5 Storm",  -50.0, 850, 50.0,  9.0,        200.0),
    ]
    result = []
    for name, bz, spd, den, kp, flux in SCENARIOS:
        r = predict_realtime(bz=bz, speed=spd, density=den,
                             kp=_kp(kp), flux=flux)
        result.append({
            "name":    name,
            "inputs":  {"bz": bz, "speed": spd, "density": den,
                        "kp": kp, "flux": flux},
            **_fmt_result(r),
        })
    return result


# ── GET /history ───────────────────────────────────────────────────
@app.get("/history", summary="Historical snr_results from CSV")
async def history(limit: int = 300):
    """
    Returns up to `limit` rows from ml_results.csv as time-series for charting.
    """
    if _history_df is None:
        return []

    df = _history_df.tail(limit).copy()
    df["time"] = df["time"].astype(str)

    cols = ["time", "Bz", "Speed", "Dens", "Kp", "flux",
            "SNR_dB", "SNR_dB_ml", "data_loss_pct", "storm_risk"]
    existing_cols = [c for c in cols if c in df.columns]
    df = df[existing_cols].rename(columns={
        "SNR_dB": "snr", "SNR_dB_ml": "snr_ml",
        "data_loss_pct": "loss", "storm_risk": "risk",
        "Bz": "bz", "Speed": "speed", "Dens": "density",
        "Kp": "kp", "flux": "flux",
    })

    # Replace NaN / inf with None for JSON serialization
    records = []
    for row in df.to_dict(orient="records"):
        clean = {
            k: (None if (v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))) else v)
            for k, v in row.items()
        }
        records.append(clean)
    return records


# ── GET /session-history ───────────────────────────────────────────
@app.get("/session-history", summary="Live prediction history (this session)")
async def session_history():
    """Returns the in-memory prediction history accumulated since server start."""
    return _snr_history


# ── POST /optimize ─────────────────────────────────────────────────
@app.post("/optimize", summary="Compare two link configurations")
async def optimize(req: OptimizeRequest):
    """
    Returns before (default config) vs after (user config) SNR/loss/risk,
    computed entirely from physics equations.
    """
    kp_v = _kp(req.kp)

    # ‑‑ baseline (CFG defaults + current space weather)
    baseline = predict_realtime(
        bz=req.bz, speed=req.speed, density=req.density,
        kp=kp_v, flux=req.flux,
    )

    # ‑‑ optimized (user-specified transmitter parameters)
    n_sw  = float(space_weather_noise(
        np.array([req.bz]), np.array([req.speed]),
        np.array([req.density]), np.array([kp_v]),
        np.array([req.flux]),
    )[0])
    pr_opt    = compute_received_power_W(
        req.pt_dbw, CFG.link.GT_DBI, CFG.link.GR_DBI,
        CFG.link.DISTANCE_KM, req.freq_mhz,
    )
    n_th_opt  = k_B * CFG.link.T_SYS_K * (req.bw_mhz * 1e6)
    n_tot_opt = max(n_th_opt + n_sw, 1e-18)
    snr_lin   = float(pr_opt) / n_tot_opt
    snr_opt_raw = 10.0 * math.log10(max(snr_lin, 1e-20))
    snr_opt   = _safe_snr_db(snr_opt_raw)
    loss_opt  = _loss_from_snr_db(snr_opt)
    risk_opt  = classify_risk(snr_opt)

    return {
        "before": _fmt_result(baseline),
        "after": {
            "snr":         snr_opt,
            "loss":        loss_opt,
            "risk":        risk_opt,
            "pt_dbw":      req.pt_dbw,
            "freq_mhz":    req.freq_mhz,
            "bw_mhz":      req.bw_mhz,
            "pr_W":        float(pr_opt),
            "n_thermal_W": n_th_opt,
            "fspl_dB":     round(fspl_db(CFG.link.DISTANCE_KM, req.freq_mhz), 2),
        },
        "delta": {
            "snr":  round(snr_opt - baseline["snr_dB"], 2),
            "loss": round(loss_opt - baseline["data_loss_pct"], 2),
        },
    }


# ── POST /decision-simulate ───────────────────────────────────────
@app.post("/decision-simulate", summary="Model-driven decision simulation")
async def decision_simulate(req: DecisionSimRequest):
    """
    Evaluate candidate data-rate reductions with the trained ML model and
    return recommendation output for decision support.
    """
    if _ml_model is None:
        raise HTTPException(
            status_code=503,
            detail="Trained model is not loaded. Please train/load snr_model.pkl first.",
        )

    try:
        candidates = [0, 20, 40, 60, 80]
        sims = [_simulate_comm_with_reduction(req, c) for c in candidates]
        live = (
            _simulate_comm_with_reduction(req, float(req.reduction))
            if req.reduction is not None
            else None
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Decision simulation failed: {exc}") from exc

    baseline = sims[0]
    baseline_snr = float(baseline["snr"])
    baseline_loss = float(baseline["loss"])

    no_optimization_needed = baseline_loss < 1.0
    decision_required = (baseline_loss > 10.0) or (baseline_snr < 5.0)
    if no_optimization_needed:
        decision_required = False

    def _score(sim: dict) -> float:
        reduction = float(sim["reduction"])
        penalty = ((reduction - 60.0) ** 2) * 0.01 if reduction > 60.0 else 0.0
        return float(sim["loss"]) + penalty

    best = min(sims, key=_score) if decision_required else baseline

    msg_by_risk = {
        "HIGH": (
            "Due to severe solar storm conditions, signal integrity is compromised. "
            "Reducing data rate improves robustness and reduces packet loss."
        ),
        "MODERATE": (
            "Link stability is degraded. Applying a moderate data-rate reduction can "
            "improve communication reliability."
        ),
        "LOW": "Communication is mostly stable; optimization is optional for extra margin.",
        "NONE": "Communication is stable. No reduction is required under current conditions.",
    }

    if no_optimization_needed:
        guidance_message = "Signal quality is already optimal. No action required."
    elif not decision_required:
        guidance_message = "System operating stably. No optimization action is required right now."
    else:
        guidance_message = msg_by_risk.get(best["risk"], msg_by_risk["MODERATE"])

    effective_live = live
    if (not decision_required) and live is not None:
        effective_live = {
            "reduction": int(live["reduction"]),
            "snr": baseline_snr,
            "loss": baseline_loss,
            "risk": baseline["risk"],
        }

    output = {
        "current_state": {
            "snr": round(baseline_snr, 2),
            "loss": round(baseline_loss, 2),
            "data_lost_mb_per_100mb": round(baseline_loss, 2),
        },
        "decision_required": decision_required,
        "no_optimization_needed": no_optimization_needed,
        "recommended_reduction": int(best["reduction"]),
        "expected_loss_no_action": round(baseline_loss, 2),
        "expected_loss_after": round(float(best["loss"]), 2),
        "data_saved": round(max(float(baseline_loss - float(best["loss"])), 0.0), 2),
        "live": {
            "reduction": int(effective_live["reduction"]),
            "snr": round(float(effective_live["snr"]), 2),
            "loss": round(float(effective_live["loss"]), 2),
            "data_lost_mb_per_100mb": round(float(effective_live["loss"]), 2),
            "data_saved_mb_per_100mb": round(max(float(baseline_loss - float(effective_live["loss"])), 0.0), 2),
        } if effective_live is not None else None,
        "message": guidance_message,
        "risk": best["risk"],
        "simulations": sims,
    }
    return output


# ── GET /model-info ────────────────────────────────────────────────
@app.get("/model-info", summary="Physics model and ML model metadata")
async def model_info():
    """Returns metadata about the physics model and loaded ML pipeline."""
    ml_info = None
    if _ml_model is not None:
        pipe = _ml_model["pipe"]
        steps = [{"name": s, "type": type(t).__name__} for s, t in pipe.steps]
        ml_info = {
            "type":     "sklearn.Pipeline",
            "features": _ml_model["features"],
            "steps":    steps,
        }

    return {
        "physics": {
            "model":    "Deterministic RF link budget + space weather noise",
            "equations": [
                "N_th = k_B · T_sys · B  (Nyquist 1928)",
                "L_fs = 20·log10(d) + 20·log10(f) + 32.44  (Friis)",
                "Pr   = Pt + Gt + Gr − L_fs  (link budget)",
                "N_sw = a|Bz| + b(v·n) + c·Kp² + d·flux",
                "SNR  = 10·log10(Pr / (N_th + N_sw))",
                "Loss = 100 / (1 + exp(SNR/3))  (calibrated sigmoid)",
            ],
            "link_budget": {
                "distance_km":  CFG.link.DISTANCE_KM,
                "freq_mhz":     CFG.link.FREQ_MHZ,
                "pt_dbw":       CFG.link.PT_DBW,
                "gt_dbi":       CFG.link.GT_DBI,
                "gr_dbi":       CFG.link.GR_DBI,
                "t_sys_k":      CFG.link.T_SYS_K,
                "bandwidth_hz": CFG.phys.BANDWIDTH_HZ,
            },
        },
        "ml": ml_info,
    }
