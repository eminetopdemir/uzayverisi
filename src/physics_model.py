"""
physics_model.py  —  RF Link Budget + Space Weather SNR Model
================================================================
Physics-based, deterministic SNR computation for satellite
communications.  All results are derived from first-principles
equations; no machine learning or black-box approximations are used.

Equation chain
--------------
  1. Thermal noise (Nyquist 1928):    Pn = k_B · T · B
  2. Free-space path loss (Friis):    L_fs = 20·log10(d·f) + 32.44
  3. Received power (link budget):    Pr = Pt + Gt + Gr − L_fs
  4. Space-weather noise:             N_sw = a|Bz| + b(v·n) + c·Kp² + d·flux
  5. Total noise:                     N_total = Pn + N_sw
  6. SNR:                             SNR = 10·log10(Pr / N_total)
  7. Data loss (calibrated sigmoid):  Loss = 100 / (1 + exp((SNR − 0) / 3))
  8. Risk classification:             ≥10 dB→none | 5–10→low | 0–5→moderate
                                      −5–0→high | <−5→severe

References
----------
[1] Nyquist, H. (1928). Physical Review, 32(1), 110–113.
[2] Ippolito, L.J. (2017). Satellite Communications Systems
    Engineering. Wiley-IEEE Press, 3rd Ed.
[3] Dungey, J.W. (1961). Phys. Rev. Lett. 6(2), 47–48.
[4] Parker, E.N. (1958). Astrophysical Journal, 128:664.
[5] Secan, J.A. et al. (1997). Radio Science, 32(4), 1523–1540.
[6] Xapsos, M.A. et al. (2000). IEEE TNS, 47(6).
[7] Klobuchar, J.A. (1987). IEEE TAES, 23(3), 325–331.
"""

import json
import logging
import math
from pathlib import Path
from typing import Optional, Union

import numpy as np
import pandas as pd
from scipy.special import erfc

from config import CFG

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────
# PHYSICAL CONSTANTS  (SI units throughout)
# ─────────────────────────────────────────────────────────────────
k_B = 1.380649e-23   # Boltzmann constant  [J/K]
c   = 2.998e8        # Speed of light      [m/s]
R_E = 6_371.0        # Earth mean radius   [km]


# ─────────────────────────────────────────────────────────────────
# 1.  ORBIT SUPPORT — LEO / GEO slant range
# ─────────────────────────────────────────────────────────────────

def detect_orbit_type(altitude_km: float) -> str:
    """
    Auto-detect orbit type from satellite altitude.

    Returns 'GEO' for geostationary altitudes (>= 35,000 km),
    'LEO' for all lower orbits (typically 200–2,000 km).

    Parameters
    ----------
    altitude_km : float — satellite altitude above Earth surface [km]

    Returns
    -------
    str — 'GEO' or 'LEO'
    """
    return "GEO" if altitude_km >= 35_000.0 else "LEO"


def leo_slant_range_km(altitude_km: float, elevation_deg: float = 30.0) -> float:
    """
    Compute slant range from ground station to LEO satellite.

    Uses the geometric formula for an oblate-free spherical Earth
    (Ippolito 2017, §3.2):

        R_slant = −R_E·sin(θ) + √[(R_E·sin(θ))² + h² + 2·R_E·h]

    where θ is the elevation angle, h the orbital altitude, and R_E
    Earth's mean radius (6,371 km).  At θ = 90° (nadir) R_slant = h.
    At θ = 0° (horizon) R_slant = √(h² + 2·R_E·h) ≈ √(2·R_E·h).

    Parameters
    ----------
    altitude_km   : float — satellite altitude above surface [km]
    elevation_deg : float — ground station elevation angle [deg],
                            default 30° (typical mid-elevation pass)

    Returns
    -------
    float — slant range [km]

    Reference: Ippolito (2017) [2], §3.2
    """
    el_rad = math.radians(max(elevation_deg, 0.1))
    term   = (R_E * math.sin(el_rad)) ** 2 + altitude_km ** 2 + 2.0 * R_E * altitude_km
    return -R_E * math.sin(el_rad) + math.sqrt(term)


def orbit_slant_range_km(altitude_km: float, elevation_deg: float = 30.0) -> float:
    """
    Return slant range for GEO or LEO orbit, auto-detected from altitude.

    GEO (>= 35,000 km) → fixed canonical 35,786 km.
    LEO (<  35,000 km) → dynamically computed via leo_slant_range_km().

    Parameters
    ----------
    altitude_km   : float — satellite altitude [km]
    elevation_deg : float — elevation angle for LEO calculation [deg]

    Returns
    -------
    float — slant range [km]
    """
    if detect_orbit_type(altitude_km) == "GEO":
        return 35_786.0
    return leo_slant_range_km(altitude_km, elevation_deg)


# ─────────────────────────────────────────────────────────────────
# 2.  FREE-SPACE PATH LOSS  —  Friis (1946) / Ippolito (2017) [2]
# ─────────────────────────────────────────────────────────────────

def fspl_db(distance_km: float, freq_mhz: float) -> float:
    """
    Free-Space Path Loss (FSPL):

        L_fs [dB] = 20·log10(d_km) + 20·log10(f_MHz) + 32.44

    Valid in the far-field condition (d >> λ).  The constant 32.44
    results from unit conversion with c = 3×10⁸ m/s, d in km, f in MHz.

    Parameters
    ----------
    distance_km : float — propagation distance [km]
    freq_mhz    : float — carrier frequency [MHz]

    Returns
    -------
    float — FSPL [dB]

    Raises
    ------
    ValueError — if distance or frequency are non-positive.

    Reference: Ippolito (2017) [2], §4.2
    """
    if distance_km <= 0 or freq_mhz <= 0:
        raise ValueError(
            f"distance and frequency must be > 0, got d={distance_km}, f={freq_mhz}"
        )
    return 20.0 * np.log10(distance_km) + 20.0 * np.log10(freq_mhz) + 32.44


# ─────────────────────────────────────────────────────────────────
# 3.  ATMOSPHERIC ABSORPTION — oxygen absorption + rain fade
# ─────────────────────────────────────────────────────────────────

def atmospheric_absorption_db(freq_ghz: float,
                               elevation_deg: float = 30.0,
                               rain_rate_mm_h: float = 0.0) -> float:
    """
    Total atmospheric path loss combining oxygen absorption and rain fade.

    Oxygen absorption (Ulaby 1981 empirical approximation, 1–60 GHz):

        γ_O2 [dB/km] ≈ 0.0069 · f_GHz² / (f_GHz² + 1.0)

    Effective path length through the atmosphere, scaled by elevation:

        L_path [km] = 8.0 / sin(θ)    (zenith atmospheric depth ~ 8 km)

    Rain fade (ITU-R P.838 simplified, horizontal polarisation):

        L_rain [dB] = k_r · R^α · L_path

    Parameters
    ----------
    freq_ghz      : float — carrier frequency [GHz]
    elevation_deg : float — elevation angle [deg], default 30°
    rain_rate_mm_h: float — rain rate [mm/h], default 0 (clear sky)

    Returns
    -------
    float — total atmospheric absorption loss [dB]
    """
    el_rad   = math.radians(max(elevation_deg, 1.0))   # guard against horizon
    path_len = 8.0 / math.sin(el_rad)                  # effective path length [km]

    f2       = freq_ghz ** 2
    gamma_O2 = 0.0069 * f2 / (f2 + 1.0)               # [dB/km]
    L_oxygen = gamma_O2 * path_len

    if rain_rate_mm_h > 0.0:
        k_rain = 0.0001 * freq_ghz ** 1.6              # ITU-R P.838 approx
        a_rain = 1.05
        L_rain = k_rain * (rain_rate_mm_h ** a_rain) * path_len
    else:
        L_rain = 0.0

    return L_oxygen + L_rain


# ─────────────────────────────────────────────────────────────────
# 4.  LINK BUDGET — received power  (Ippolito 2017, Ch. 4)  [2]
# ─────────────────────────────────────────────────────────────────

def compute_received_power_W(pt_dbw: float,
                              gt_dbi: float,
                              gr_dbi: float,
                              distance_km: float,
                              freq_mhz: float,
                              extra_loss_db: float = 0.0) -> float:
    """
    General Friis transmission equation (parametric form):

        P_r [dBW] = P_t + G_t + G_r − L_fs − L_extra

    Used by process_single_record() for arbitrary telemetry inputs.

    Parameters
    ----------
    pt_dbw        : float — transmit power [dBW]
    gt_dbi        : float — transmit antenna gain [dBi]
    gr_dbi        : float — receive antenna gain [dBi]
    distance_km   : float — slant range [km]
    freq_mhz      : float — carrier frequency [MHz]
    extra_loss_db : float — additional losses (scintillation,
                            atmospheric, pointing etc.) [dB]

    Returns
    -------
    float — received signal power [W]

    Reference: Ippolito (2017) [2]
    """
    l_fs   = fspl_db(distance_km, freq_mhz)
    pr_dbw = pt_dbw + gt_dbi + gr_dbi - l_fs - extra_loss_db
    return 10.0 ** (pr_dbw / 10.0)


def received_power_W() -> float:
    """
    Received power for the default GEO / Ku-band scenario from CFG.

    GEO / Ku-band scenario (config.LinkBudget):
        Distance : 35,786 km  | Frequency : 12,000 MHz
        Pt = 20 dBW (100 W)   | Gt = 33 dBi | Gr = 52 dBi
        Nominal P_r ≈ 9.8×10⁻¹¹ W (−100 dBW)

    Returns
    -------
    float — received signal power [W]

    Reference: Ippolito (2017) [2]
    """
    lb = CFG.link
    return compute_received_power_W(
        lb.PT_DBW, lb.GT_DBI, lb.GR_DBI, lb.DISTANCE_KM, lb.FREQ_MHZ
    )


# ─────────────────────────────────────────────────────────────────
# 5.  DYNAMIC NOISE TEMPERATURE
# ─────────────────────────────────────────────────────────────────

def space_weather_noise_temperature(kp: float,
                                     tec: float,
                                     electron_density: float) -> float:
    """
    Space-weather contribution to effective system noise temperature.

    Empirical model accounting for three disturbance mechanisms that
    elevate the sky noise temperature perceived by the receiver:

        T_space [K] = A·Kp + B·TEC + C·log10(Ne)

    where:
        A·Kp         — geomagnetic heating raises background emission
                        (~50 K per Kp unit, empirical).
        B·TEC        — enhanced ionospheric plasma increases thermal
                        self-emission along the RF path.
        C·log10(Ne)  — electron density contribution to effective sky
                        temperature (Klobuchar 1987 [7]).

    Parameters
    ----------
    kp              : float — Kp geomagnetic index [0–9]
    tec             : float — Total Electron Content [TECU]
    electron_density: float — electron number density [m⁻³]

    Returns
    -------
    float — additional noise temperature contribution [K], ≥ 0
    """
    kp_safe  = max(float(kp), 0.0) if math.isfinite(float(kp)) else 0.0
    tec_safe = max(float(tec), 0.0)
    ne_safe  = max(float(electron_density), 1.0)

    t_kp  = 50.0  * kp_safe
    t_tec = 0.5   * tec_safe
    t_ne  = 100.0 * math.log10(ne_safe)

    return max(t_kp + t_tec + t_ne, 0.0)


def compute_noise_temperature(base_t_k: float,
                               kp: float = 0.0,
                               tec: float = 0.0,
                               electron_density: float = 1e6) -> float:
    """
    Total system noise temperature combining hardware baseline and
    space-weather disturbance:

        T_total = T_base + T_space(Kp, TEC, Ne)

    Parameters
    ----------
    base_t_k        : float — hardware system noise temperature [K]
    kp              : float — Kp index [0–9]
    tec             : float — Total Electron Content [TECU]
    electron_density: float — electron density [m⁻³]

    Returns
    -------
    float — effective system noise temperature [K]
    """
    return base_t_k + space_weather_noise_temperature(kp, tec, electron_density)


def system_thermal_noise(t_sys_k: Optional[float] = None) -> float:
    """
    Johnson–Nyquist receiver noise power:

        N_th = k_B · T_sys · B

    T_sys defaults to CFG.link.T_SYS_K (hardware baseline, no space weather).
    Pass a pre-computed T_sys to include space-weather contributions.

    Parameters
    ----------
    t_sys_k : float, optional — system noise temperature [K].
              Uses CFG.link.T_SYS_K if not provided.

    Returns
    -------
    float — thermal noise power [W]

    Reference: Nyquist (1928) [1]
    """
    t = t_sys_k if t_sys_k is not None else CFG.link.T_SYS_K
    return k_B * t * CFG.phys.BANDWIDTH_HZ


# ─────────────────────────────────────────────────────────────────
# 6.  IONOSPHERIC MODEL — TEC delay, scintillation, plasma cutoff
# ─────────────────────────────────────────────────────────────────

def tec_group_delay_s(tec_tecu: float, freq_hz: float) -> float:
    """
    TEC-induced ionospheric group delay on an RF signal.

    Standard first-order dispersive delay (Klobuchar 1987 [7]):

        Δt [s] = 40.3 · TEC_el/m² / f²

    where TEC_el/m² = tec_tecu × 10¹⁶  (1 TECU = 10¹⁶ el/m²).

    Parameters
    ----------
    tec_tecu : float — Total Electron Content [TECU]
    freq_hz  : float — carrier frequency [Hz]

    Returns
    -------
    float — ionospheric group delay [s]
    """
    if freq_hz <= 0:
        return 0.0
    tec_m2 = tec_tecu * 1e16                    # TECU → el/m²
    return 40.3 * tec_m2 / (freq_hz ** 2 * c)   # divide by c → seconds


def scintillation_loss_db(tec_tecu: float, freq_ghz: float) -> float:
    """
    Ionospheric amplitude scintillation fade loss.

    Empirical model based on Secan et al. (1997) [5]:

        L_scint [dB] = 0.5 · TEC · f_GHz^(−1.5)

    Higher TEC and lower frequencies produce stronger fading.

    Parameters
    ----------
    tec_tecu : float — Total Electron Content [TECU]
    freq_ghz : float — carrier frequency [GHz]

    Returns
    -------
    float — scintillation fade loss [dB], ≥ 0
    """
    if freq_ghz <= 0 or tec_tecu <= 0:
        return 0.0
    return 0.5 * tec_tecu * (freq_ghz ** -1.5)


def plasma_frequency_hz(electron_density_m3: float) -> float:
    """
    Electron plasma frequency of the ionosphere.

    The plasma frequency sets a lower cutoff for RF propagation:

        f_plasma [Hz] = 9 · √Ne

    where Ne is free electron density in m⁻³.  Signals below this
    frequency cannot propagate through the ionospheric plasma.

    Parameters
    ----------
    electron_density_m3 : float — electron number density [m⁻³]

    Returns
    -------
    float — plasma frequency [Hz]
    """
    return 9.0 * math.sqrt(max(float(electron_density_m3), 0.0))


def check_plasma_blockage(carrier_freq_hz: float,
                           electron_density_m3: float) -> tuple:
    """
    Check whether the carrier frequency is blocked by the ionospheric plasma.

    A signal is blocked when carrier_freq < f_plasma.  In that case
    total signal loss (100 %) must be applied.

    Parameters
    ----------
    carrier_freq_hz     : float — carrier frequency [Hz]
    electron_density_m3 : float — peak ionospheric electron density [m⁻³]

    Returns
    -------
    (blocked: bool, f_plasma_hz: float)
    """
    f_p = plasma_frequency_hz(electron_density_m3)
    return (carrier_freq_hz < f_p, f_p)


# ─────────────────────────────────────────────────────────────────
# 7.  SPACE WEATHER NOISE  —  multi-term additive model
# ─────────────────────────────────────────────────────────────────

def space_weather_noise(bz_nt: np.ndarray,
                        speed_kmps: np.ndarray,
                        dens_cm3: np.ndarray,
                        kp: np.ndarray,
                        flux_pfu: np.ndarray) -> np.ndarray:
    """
    Space-weather-driven effective additive noise power:

        N_sw = a·|Bz| + b·(v·n) + c·Kp² + d·flux

    Physical terms
    --------------
    a·|Bz_nT|     — IMF southward reconnection (Dungey 1961) [3]:
                    strong |Bz| drives  magnetospheric convection →
                    ring current growth → ionospheric irregularities
                    → signal scintillation.  Units: W/nT

    b·(v·n)       — Solar wind mass flux (Parker 1958) [4]:
                    n·v at magnetopause represents particle influx →
                    magnetospheric compression → plasma heating →
                    particle injection → absorption.  Units: W·s·cm³/km

    c·Kp²         — Kp nonlinear TEC irregularity growth (Secan 1997) [5].
                    Kp = NaN (no OMNI data) → treated as 0. Units: W

    d·flux        — Polar cap absorption by energetic protons (Xapsos 2000) [6].
                    GOES >55 MeV protons can degrade HF/UHF 10–20 dB. Units: W/pfu

    Coefficient calibration: G3–G5 storms (|Bz|≈30–50 nT, Kp=8–9,
    flux≈100 pfu) push SNR below 0 dB (> 50 % data loss).

    Parameters
    ----------
    bz_nt     : ndarray — Bz GSM component [nT]
    speed_kmps: ndarray — solar wind speed [km/s]
    dens_cm3  : ndarray — proton density [cm⁻³]
    kp        : ndarray — Kp index [0–9]; NaN → 0
    flux_pfu  : ndarray — proton flux [pfu]

    Returns
    -------
    ndarray — N_sw [W], ≥ 0
    """
    lb = CFG.link

    lb = CFG.link
    kp_safe = np.where(np.isfinite(kp), kp, 0.0)   # NaN Kp → 0 (conservative)

    n_bz   = lb.SW_A * np.abs(bz_nt)                             # IMF reconnection
    n_vn   = lb.SW_B * (np.abs(speed_kmps) * np.abs(dens_cm3))  # solar wind flux
    n_kp   = lb.SW_C * (kp_safe ** 2)                            # Kp nonlinear term
    n_flux = lb.SW_D * np.abs(flux_pfu)                          # PCA proton absorption

    return n_bz + n_vn + n_kp + n_flux


# ─────────────────────────────────────────────────────────────────
# 8.  SNR COMPUTATION — full link budget
# ─────────────────────────────────────────────────────────────────

def compute_snr_physics(pr_w: float,
                        n_th_w: float,
                        n_sw_w: np.ndarray) -> tuple:
    """
    SNR from full link budget:

        N_total    = N_th + N_sw
        SNR_linear = P_r / N_total
        SNR_dB     = 10 · log10(SNR_linear)

    Parameters
    ----------
    pr_w   : float   — received signal power [W]
    n_th_w : float   — system thermal noise [W]
    n_sw_w : ndarray — space weather noise [W]

    Returns
    -------
    (snr_linear, snr_dB) — both ndarray
    """
    n_total = n_th_w + n_sw_w
    snr_lin = pr_w / np.maximum(n_total, 1e-40)
    snr_dB  = 10.0 * np.log10(np.maximum(snr_lin, 1e-20))
    return snr_lin, snr_dB


# ─────────────────────────────────────────────────────────────────
# 9.  CALIBRATED DATA LOSS MODEL  —  nonlinear sigmoid mapping
# ─────────────────────────────────────────────────────────────────

# Sigmoid calibration constants
_LOSS_SHIFT = 0.0   # midpoint: Loss = 50 % at SNR = SHIFT [dB]
_LOSS_SCALE = 3.0   # slope:    shallower for larger scale
#
# Verification at nominal operating points:
#   SNR = +10 dB  →  Loss ≈  3.4 %   (≲0 %)
#   SNR =   0 dB  →  Loss = 50.0 %   (≈30–50 % range)
#   SNR = -10 dB  →  Loss ≈ 96.5 %   (≈95–100 % range)


def data_loss_pct(snr_db: Union[float, np.ndarray],
                  shift: float = _LOSS_SHIFT,
                  scale: float = _LOSS_SCALE) -> Union[float, np.ndarray]:
    """
    Data loss percentage via calibrated nonlinear sigmoid:

        Loss(%) = 100 / (1 + exp((SNR_dB − shift) / scale))

    Physical rationale
    ------------------
    The logistic function models the sharp transition between
    error-free and fully disrupted link performance observed in
    real digital satellite links.  The inflection point
    (Loss = 50 %) is placed at SNR = shift [dB].

    Calibration (shift = 0 dB, scale = 3):

        SNR = +10 dB  →  Loss ≈  3.4 %          (operational)
        SNR =   0 dB  →  Loss =  50.0 %          (threshold)
        SNR = −10 dB  →  Loss ≈  96.5 %          (link failure)

    Parameters
    ----------
    snr_db : float or ndarray — SNR [dB]
    shift  : float            — midpoint [dB], default 0
    scale  : float            — slope divisor, default 3

    Returns
    -------
    float or ndarray — data loss [%] ∈ [0, 100]
    """
    x = np.asarray(snr_db, dtype=float)
    return 100.0 / (1.0 + np.exp((x - shift) / scale))


def qpsk_ber(snr_linear: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
    """
    Theoretical QPSK Bit Error Rate (supplementary):

        BER = 0.5 · erfc(√SNR_linear)

    Kept as a supplementary physics function for detailed BER
    analysis; not used by the main data_loss_pct pipeline.

    Parameters
    ----------
    snr_linear : float or ndarray — linear SNR (not dB)

    Returns
    -------
    float or ndarray — BER ∈ [0, 0.5]
    """
    return 0.5 * erfc(np.sqrt(np.maximum(snr_linear, 0.0)))


def fec_effective_snr(snr_linear: Union[float, np.ndarray],
                      fec_gain_db: float = 5.0) -> Union[float, np.ndarray]:
    """
    Apply FEC coding gain to linear SNR (supplementary):

        SNR_eff = SNR_linear · 10^(FEC_gain_dB / 10)

    Parameters
    ----------
    snr_linear  : float or ndarray — raw linear SNR
    fec_gain_db : float            — FEC coding gain [dB]

    Returns
    -------
    float or ndarray — effective linear SNR
    """
    return snr_linear * (10.0 ** (fec_gain_db / 10.0))


def ber_packet_loss(snr_linear: Union[float, np.ndarray],
                    fec_gain_db: float = 5.0,
                    packet_bits: int = 8192) -> Union[float, np.ndarray]:
    """
    QPSK + FEC packet error rate (supplementary):

        SNR_eff = SNR_linear · 10^(FEC_gain_dB / 10)
        BER     = 0.5 · erfc(√SNR_eff)
        Loss    = 1 − (1 − BER)^packet_bits

    Parameters
    ----------
    snr_linear  : float or ndarray
    fec_gain_db : float  — [dB]
    packet_bits : int

    Returns
    -------
    float or ndarray — packet loss fraction ∈ [0, 1]
    """
    ber_c = np.clip(qpsk_ber(fec_effective_snr(snr_linear, fec_gain_db)),
                    0.0, 1.0 - 1e-15)
    return 1.0 - (1.0 - ber_c) ** packet_bits


# ─────────────────────────────────────────────────────────────────
# 10. RISK CLASSIFICATION
# ─────────────────────────────────────────────────────────────────

def classify_risk(snr_db: float) -> str:
    """
    Classify communications risk level from SNR [dB].

    Thresholds (dB)::

        >= 10  → 'none'      (operational, Loss < 5 %)
        >=  5  → 'low'       (minor degradation)
        >=  0  → 'moderate'  (noticeable packet loss)
        >= -5  → 'high'      (significant disruption)
        <  -5  → 'severe'    (link effectively lost)

    Calibrated against the sigmoid data_loss_pct model
    (shift = 0 dB, scale = 3):

        SNR = 10 dB → Loss ≈  3.4 % (none threshold)
        SNR =  5 dB → Loss ≈ 15.9 % (low threshold)
        SNR =  0 dB → Loss = 50.0 % (moderate threshold)
        SNR = -5 dB → Loss ≈ 84.1 % (high threshold)

    Parameters
    ----------
    snr_db : float — SNR value [dB]

    Returns
    -------
    str — risk label: 'none' | 'low' | 'moderate' | 'high' | 'severe'
    """
    if   snr_db >= 10.0: return "none"
    elif snr_db >=  5.0: return "low"
    elif snr_db >=  0.0: return "moderate"
    elif snr_db >= -5.0: return "high"
    else:                return "severe"


# ─────────────────────────────────────────────────────────────────
# 11. INTERNAL STORM FLAG
# ─────────────────────────────────────────────────────────────────

def _storm_flag(bz: np.ndarray,
                kp: np.ndarray,
                pdyn: Optional[np.ndarray]) -> np.ndarray:
    """
    Dual-path storm detection (Ippolito 2017 + Newell 2008).

    Path A — measured Kp (OMNI): Bz < 0 AND Kp > 5
    Path B — RTSW local (Kp NaN): Bz < STORM_BZ_THRESH
                                  AND Pdyn > STORM_PDYN_THRESH
    """
    kp_finite = np.isfinite(kp)
    flag_a = kp_finite & (bz < 0.0) & (kp > 5.0)
    if pdyn is not None:
        flag_b = (
            (~kp_finite)
            & (bz   < CFG.phys.STORM_BZ_THRESH)
            & (pdyn > CFG.phys.STORM_PDYN_THRESH)
        )
    else:
        flag_b = np.zeros(len(bz), dtype=bool)
    return flag_a | flag_b


# ─────────────────────────────────────────────────────────────────
# 12. FULL DATAFRAME PIPELINE  (backward-compatible)
# ─────────────────────────────────────────────────────────────────

def run_physics_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply physics model to a merged space weather DataFrame.

    Required input columns: Bz, Dens, Speed, Temp, Kp, flux
    Optional:               Pdyn

    Output columns added (visualizer.py compatible)::

        N_thermal    — system thermal noise [W]  (Nyquist 1928)
        N_scint      — N_sw [W]  (mapped for visualizer compatibility)
        N_rad        — 0.0  (proton absorption in SW d·flux term)
        N_total      — N_thermal + N_sw [W]
        SNR_lin      — linear SNR
        SNR_dB       — SNR [dB]
        storm_flag   — bool storm mask (Ippolito 2017 / Newell 2008)
        data_loss_pct— estimated data loss [%] (calibrated sigmoid)
    """
    out = df.copy()

    pr_w = received_power_W()
    n_th = system_thermal_noise()

    bz    = out["Bz"].fillna(0.0).values
    speed = out["Speed"].fillna(400.0).values
    dens  = out["Dens"].fillna(5.0).values
    kp    = out["Kp"].values                 # NaN = data unavailable
    flux  = out["flux"].fillna(0.0).values
    pdyn  = out["Pdyn"].values if "Pdyn" in out.columns else None

    n_sw            = space_weather_noise(bz, speed, dens, kp, flux)
    n_tot           = n_th + n_sw
    snr_lin, snr_dB = compute_snr_physics(pr_w, n_th, n_sw)
    loss            = data_loss_pct(snr_dB)
    flags           = _storm_flag(bz, kp, pdyn)

    out["N_thermal"]     = n_th
    out["N_scint"]       = n_sw
    out["N_rad"]         = 0.0
    out["N_total"]       = n_tot
    out["SNR_lin"]       = snr_lin
    out["SNR_dB"]        = snr_dB
    out["storm_flag"]    = flags
    out["data_loss_pct"] = loss

    l_fs = fspl_db(CFG.link.DISTANCE_KM, CFG.link.FREQ_MHZ)
    log.info(f"[PHYSICS]  FSPL       = {l_fs:.2f} dB  "
             f"(d={CFG.link.DISTANCE_KM:.0f} km, f={CFG.link.FREQ_MHZ:.0f} MHz)")
    log.info(f"[PHYSICS]  Pr         = {pr_w:.4e} W  ({10.0*np.log10(pr_w):.1f} dBW)")
    log.info(f"[PHYSICS]  N_thermal  = {n_th:.4e} W  (T_sys={CFG.link.T_SYS_K:.0f} K)")
    log.info(f"[PHYSICS]  SNR mean   = {snr_dB.mean():.2f} dB")
    log.info(f"[PHYSICS]  SNR min    = {snr_dB.min():.2f} dB")
    log.info(f"[PHYSICS]  Loss mean  = {loss.mean():.3f} %")
    log.info(f"[PHYSICS]  Storm time = {int(flags.sum())} min")

    return out


# ─────────────────────────────────────────────────────────────────
# 13. REAL-TIME PREDICTION  (backward-compatible)
# ─────────────────────────────────────────────────────────────────

def predict_realtime(bz: float,
                     speed: float,
                     density: float,
                     kp: float = float("nan"),
                     flux: float = 0.0) -> dict:
    """
    SNR and data loss estimate from instantaneous space weather inputs.

    Parameters
    ----------
    bz      : float — Bz GSM component [nT]
    speed   : float — solar wind speed [km/s]
    density : float — proton density [cm⁻³]
    kp      : float — Kp index [0–9]; float('nan') if unknown
    flux    : float — GOES proton flux [pfu]; default 0.0

    Returns
    -------
    dict:
        snr_dB        — receiver SNR [dB]
        data_loss_pct — estimated data loss [%]
        storm_risk    — 'low'|'moderate'|'high'|'severe'|'critical'
        N_space_W     — total space weather noise [W]
        N_thermal_W   — thermal noise floor [W]
        Pr_W          — received signal power [W]
        fspl_dB       — free-space path loss [dB]
    """
    pr_w = received_power_W()
    n_th = system_thermal_noise()
    l_fs = fspl_db(CFG.link.DISTANCE_KM, CFG.link.FREQ_MHZ)

    n_sw       = space_weather_noise(
        np.array([bz]), np.array([speed]),
        np.array([density]), np.array([kp]), np.array([flux])
    )
    _, snr_arr = compute_snr_physics(pr_w, n_th, n_sw)
    loss_arr   = data_loss_pct(snr_arr)

    snr_val  = float(snr_arr[0])
    loss_val = float(loss_arr[0])

    return {
        "snr_dB":        round(snr_val, 2),
        "data_loss_pct": round(loss_val, 3),
        "storm_risk":    classify_risk(snr_val),
        "N_space_W":     float(n_sw[0]),
        "N_thermal_W":   n_th,
        "Pr_W":          pr_w,
        "fspl_dB":       round(l_fs, 2),
    }


# ─────────────────────────────────────────────────────────────────
# 14. TIME-SERIES TELEMETRY PROCESSING
# ─────────────────────────────────────────────────────────────────

_DEFAULTS: dict = {
    "latitude_deg":         0.0,
    "longitude_deg":        0.0,
    "solar_flux_F107":      150.0,
    "geomagnetic_index_Kp": 0.0,
    "ionospheric_TEC":      10.0,
    "electron_density":     1e10,
    "plasma_temperature_K": 300.0,
    "bandwidth_MHz":        10.0,
    "path_loss_dB":         0.0,
    "event_type":           "nominal",
    "satellite_id":         "UNKNOWN",
}


def _safe_get(record: dict, key: str, default=None):
    """Return field value with fallback; coerces NaN/None to default."""
    val = record.get(key, default if default is not None else _DEFAULTS.get(key))
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return default if default is not None else _DEFAULTS.get(key, 0.0)
    except TypeError:
        pass
    return val


def process_single_record(record: dict) -> dict:
    """
    Compute full link budget and SNR for one telemetry record.

    Model chain applied per record:

    1. Orbit detection → slant range (LEO or GEO)
    2. Plasma frequency blockage check
    3. Dynamic noise temperature (hardware T_sys + space-weather term)
    4. Ionospheric scintillation loss and TEC group delay
    5. Atmospheric absorption
    6. Received power via Friis equation
    7. SNR computation
    8. BER-based QPSK + FEC + packet loss

    Parameters
    ----------
    record : dict — telemetry record; see TELEMETRY DATA FORMAT in module docs

    Returns
    -------
    dict containing: timestamp, SNR_dB, data_loss_pct, risk_level,
                     scintillation_loss_dB, plasma_blocked, event_type,
                     and additional diagnostic fields.
    """
    ts       = _safe_get(record, "timestamp", "unknown")
    alt_km   = float(_safe_get(record, "altitude_km", 400.0))
    freq_ghz = float(_safe_get(record, "carrier_frequency_GHz", 2.25))
    pt_dbw   = float(_safe_get(record, "transmit_power_dBW", 20.0))
    ant_dbi  = float(_safe_get(record, "antenna_gain_dBi", 20.0))
    bw_mhz   = float(_safe_get(record, "bandwidth_MHz", 10.0))
    base_t_k = float(_safe_get(record, "noise_temperature_K", 300.0))
    kp       = float(_safe_get(record, "geomagnetic_index_Kp", 0.0))
    tec      = float(_safe_get(record, "ionospheric_TEC", 10.0))
    ne       = float(_safe_get(record, "electron_density", 1e10))
    event    = str(_safe_get(record, "event_type", "nominal"))
    # path_loss_dB: if > 0, treated as pre-computed total path loss
    # (replaces FSPL); if 0, FSPL is computed from slant range + frequency
    pre_path_loss = float(_safe_get(record, "path_loss_dB", 0.0))

    freq_mhz = freq_ghz * 1e3
    freq_hz  = freq_ghz * 1e9
    bw_hz    = bw_mhz   * 1e6

    # ── 1. Orbit: slant range ──────────────────────────────────────
    orbit_type = detect_orbit_type(alt_km)
    slant_km   = orbit_slant_range_km(alt_km)

    # ── 2. Plasma blockage check ───────────────────────────────────
    plasma_blocked, f_plasma = check_plasma_blockage(freq_hz, ne)
    f_plasma_mhz = f_plasma / 1e6

    if plasma_blocked:
        notes = (f"SIGNAL BLOCKED: f_carrier={freq_ghz:.3f} GHz "
                 f"< f_plasma={f_plasma_mhz:.2f} MHz")
        return {
            "timestamp":             ts,
            "satellite_id":          _safe_get(record, "satellite_id", "UNKNOWN"),
            "event_type":            event,
            "orbit_type":            orbit_type,
            "altitude_km":           alt_km,
            "SNR_dB":                -999.0,
            "data_loss_pct":         100.0,
            "risk_level":            "critical",
            "scintillation_loss_dB": 0.0,
            "delay_ns":              0.0,
            "plasma_blocked":        True,
            "f_plasma_MHz":          round(f_plasma_mhz, 3),
            "T_sys_K":               base_t_k,
            "slant_range_km":        round(slant_km, 1),
            "notes":                 notes,
        }

    # ── 3. Dynamic noise temperature ──────────────────────────────
    t_sys = compute_noise_temperature(base_t_k, kp, tec, ne)
    n_th  = k_B * t_sys * bw_hz

    # ── 4. Ionospheric effects ─────────────────────────────────────
    l_scint  = scintillation_loss_db(tec, freq_ghz)
    delay_ns = tec_group_delay_s(tec, freq_hz) * 1e9  # convert s → nanoseconds

    # ── 5. Atmospheric absorption ──────────────────────────────────
    l_atm = atmospheric_absorption_db(freq_ghz)

    # ── 6. Received power ──────────────────────────────────────────
    if pre_path_loss > 0.0:
        # pre_path_loss is total path loss (FSPL + system losses already);
        # add ionospheric scintillation and atmospheric absorption on top
        pr_dbw = pt_dbw + ant_dbi + ant_dbi - pre_path_loss - l_scint - l_atm
        pr_w   = 10.0 ** (pr_dbw / 10.0)
    else:
        pr_w = compute_received_power_W(
            pt_dbw, ant_dbi, ant_dbi, slant_km, freq_mhz,
            extra_loss_db=l_scint + l_atm
        )

    # ── 7. SNR ────────────────────────────────────────────────────
    snr_lin = pr_w / max(n_th, 1e-40)
    snr_db  = 10.0 * math.log10(max(snr_lin, 1e-20))

    # ── 8. BER-based data loss ────────────────────────────────────
    loss_pct = float(data_loss_pct(np.array([snr_db]))[0])
    risk     = classify_risk(snr_db)

    notes_parts = []
    if l_scint > 1.0:
        notes_parts.append(f"scint={l_scint:.1f}dB")
    if kp >= 7.0:
        notes_parts.append(f"Kp={kp:.1f}(storm)")
    if plasma_blocked:
        notes_parts.append("plasma-blocked")
    notes = "; ".join(notes_parts) if notes_parts else "nominal"

    return {
        "timestamp":             ts,
        "satellite_id":          _safe_get(record, "satellite_id", "UNKNOWN"),
        "event_type":            event,
        "orbit_type":            orbit_type,
        "altitude_km":           alt_km,
        "SNR_dB":                round(snr_db, 3),
        "data_loss_pct":         round(loss_pct, 3),
        "risk_level":            risk,
        "scintillation_loss_dB": round(l_scint, 3),
        "delay_ns":              round(delay_ns, 3),
        "plasma_blocked":        False,
        "f_plasma_MHz":          round(f_plasma_mhz, 3),
        "T_sys_K":               round(t_sys, 1),
        "slant_range_km":        round(slant_km, 1),
        "notes":                 notes,
    }


def process_telemetry_json(filepath: Union[str, Path],
                            export_csv: bool = True) -> pd.DataFrame:
    """
    Process a JSON telemetry file (array of records) through the physics model.

    Each record is passed to process_single_record().  Results are
    returned as a pandas DataFrame and optionally exported to CSV.

    Parameters
    ----------
    filepath   : str or Path — path to JSON telemetry file
    export_csv : bool        — write results to outputs/telemetry_results.csv

    Returns
    -------
    pd.DataFrame with columns:
        [timestamp, SNR_dB, data_loss_pct, risk_level,
         scintillation_loss_dB, plasma_blocked, event_type]
        plus diagnostic columns (orbit_type, T_sys_K, slant_range_km, etc.)

    Raises
    ------
    FileNotFoundError — if the JSON file does not exist.
    ValueError        — if the file does not contain a list or single dict.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Telemetry file not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    if isinstance(raw, dict):
        records = [raw]
    elif isinstance(raw, list):
        records = raw
    else:
        raise ValueError(f"Expected JSON array or object, got {type(raw).__name__}")

    results = []
    for i, rec in enumerate(records):
        try:
            results.append(process_single_record(rec))
        except Exception as exc:
            log.warning(f"[TELEMETRY]  Record {i} skipped: {exc}")

    df = pd.DataFrame(results)

    if export_csv and len(df):
        out_path = CFG.paths.outputs / "telemetry_results.csv"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=False)
        log.info(f"[TELEMETRY]  Exported {len(df)} records → {out_path}")

    return df


def print_telemetry_table(df: pd.DataFrame) -> None:
    """
    Print a formatted summary table of telemetry processing results.

    Printed columns:
        timestamp | event_type | SNR_dB | data_loss_pct | risk | notes

    Parameters
    ----------
    df : pd.DataFrame — output of process_telemetry_json()
    """
    DIV = "─" * 96
    HDR = (f"  {'Timestamp':<22}  {'Event':<18}  {'SNR':>10}  "
           f"{'Loss':>8}  {'Risk':<10}  Notes")
    print(f"\n{DIV}")
    print("  TELEMETRY PROCESSING RESULTS")
    print(DIV)
    print(HDR)
    print(DIV)
    for _, row in df.iterrows():
        ts      = str(row.get("timestamp",    ""))[:22]
        ev      = str(row.get("event_type",   ""))[:18]
        snr     = row.get("SNR_dB",           0.0)
        loss    = row.get("data_loss_pct",    0.0)
        risk    = str(row.get("risk_level",   ""))[:10]
        notes   = str(row.get("notes",        ""))
        blocked = row.get("plasma_blocked",   False)
        snr_str = "  BLOCKED" if blocked else f"{snr:>+9.2f} dB"
        print(f"  {ts:<22}  {ev:<18}  {snr_str}  "
              f"{loss:>7.2f}%  {risk:<10}  {notes}")
    print(DIV)


# ─────────────────────────────────────────────────────────────────
# ENTRY POINT  —  standalone demo / sanity check
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    import sys
    import tempfile

    logging.basicConfig(level=logging.WARNING)

    DIV  = "═" * 66
    DIV2 = "─" * 66

    # ─────────────────────────────────────────────────────────────
    # DEMO 1: GEO / Ku-band link budget
    # ─────────────────────────────────────────────────────────────
    lb   = CFG.link
    l_fs = fspl_db(lb.DISTANCE_KM, lb.FREQ_MHZ)
    pr_w = received_power_W()
    n_th = system_thermal_noise()

    print(f"\n{DIV}")
    print(f"  RF LINK BUDGET  —  physics_model.py")
    print(f"  Deterministic physics model | No ML | SI units")
    print(f"  Scenario   : GEO satellite, Ku-band downlink")
    print(f"  Distance   : {lb.DISTANCE_KM:,.0f} km")
    print(f"  Frequency  : {lb.FREQ_MHZ:,.0f} MHz  ({lb.FREQ_MHZ/1e3:.1f} GHz)")
    print(f"  Tx Power   : {lb.PT_DBW:.1f} dBW  ({10**(lb.PT_DBW/10):.0f} W)")
    print(f"  Tx Gain    : {lb.GT_DBI:.1f} dBi")
    print(f"  Rx Gain    : {lb.GR_DBI:.1f} dBi")
    print(f"  T_sys      : {lb.T_SYS_K:.0f} K  (cooled LNA)")
    print(DIV2)
    print(f"  FSPL       : {l_fs:.2f} dB")
    print(f"  Pr         : {pr_w:.4e} W  ({10*np.log10(pr_w):.2f} dBW)")
    print(f"  N_thermal  : {n_th:.4e} W")
    print(f"  Bandwidth  : {CFG.phys.BANDWIDTH_HZ/1e6:.1f} MHz")
    print(DIV)

    scenarios = [
        # label,        bz,    speed, dens,  kp,    flux
        ("Quiet Sun",  +0.0,   380,   4.0,   1.0,    0.0),
        ("Mild",       -5.0,   450,   8.0,   float("nan"),  0.0),
        ("G1 Storm",  -10.0,   500,  15.0,   5.0,    0.5),
        ("G2 Storm",  -20.0,   600,  20.0,   6.5,    2.0),
        ("G3 Storm",  -30.0,   680,  25.0,   7.5,   10.0),
        ("G4 Storm",  -40.0,   750,  35.0,   8.5,   50.0),
        ("G5 Storm",  -50.0,   850,  50.0,   9.0,  200.0),
    ]

    print(f"\n  {'Scenario':<12}  {'Bz':>6}  {'v':>5}  {'n':>5}  "
          f"{'Kp':>5}  {'SNR':>8}  {'Loss':>9}  {'Risk'}")
    print(f"  {'':─<12}  {'[nT]':>6}  {'km/s':>5}  {'cm\u207b\u00b3':>5}  "
          f"{'':>5}  {'[dB]':>8}  {'[%]':>9}")
    print(f"  {DIV2}")
    for label, bz, speed, dens, kp, flux in scenarios:
        r    = predict_realtime(bz=bz, speed=speed, density=dens, kp=kp, flux=flux)
        kp_s = f"{kp:.1f}" if np.isfinite(kp) else " N/A"
        print(f"  {label:<12}  {bz:>+6.1f}  {speed:>5.0f}  {dens:>5.1f}  "
              f"{kp_s:>5}  {r['snr_dB']:>+8.2f}  "
              f"{r['data_loss_pct']:>8.3f}%  {r['storm_risk']}")
    print(f"\n  Equations:")
    print(f"    N_total = k_B·T·B + a|Bz| + b(v·n) + c·Kp² + d·flux")
    print(f"    SNR_dB  = 10·log10(Pr / N_total)")
    print(f"    Loss(%) = 100 / (1 + exp((SNR_dB − {_LOSS_SHIFT}) / {_LOSS_SCALE}))")
    print(f"    Risk: >=10 dB=none | 5–10=low | 0–5=moderate | −5–0=high | <−5=severe")
    print(f"{DIV}\n")

    # ─────────────────────────────────────────────────────────────
    # DEMO 2: LEO telemetry — single record
    # ─────────────────────────────────────────────────────────────
    sample_record = {
        "timestamp":             "2026-03-28T02:50:00Z",
        "satellite_id":          "ORBITAL-SIM-01",
        "altitude_km":           462.0,
        "latitude_deg":          -59.5,
        "longitude_deg":          80.5,
        "solar_flux_F107":       168.4,
        "geomagnetic_index_Kp":    7.0,
        "ionospheric_TEC":        85.2,
        "electron_density":      4.2e11,
        "plasma_temperature_K": 4100.0,
        "transmit_power_dBW":     30.5,
        "carrier_frequency_GHz":   2.25,
        "bandwidth_MHz":          10.0,
        "antenna_gain_dBi":       20.2,
        "path_loss_dB":          194.1,
        "noise_temperature_K":   680.0,
        "event_type":            "geomagnetic_storm",
    }

    print(f"{DIV}")
    print("  LEO TELEMETRY DEMO  —  Single Record (S-band, 462 km)")
    print(DIV)
    r2 = process_single_record(sample_record)
    print(f"  Timestamp       : {r2['timestamp']}")
    print(f"  Satellite       : {r2['satellite_id']}")
    print(f"  Orbit type      : {r2['orbit_type']}  ({r2['altitude_km']:.0f} km)")
    print(f"  Slant range     : {r2['slant_range_km']:.1f} km")
    print(f"  T_sys (dynamic) : {r2['T_sys_K']:.1f} K  (base + space-weather)")
    print(f"  Scintillation   : {r2['scintillation_loss_dB']:.2f} dB")
    print(f"  TEC delay       : {r2['delay_ns']:.2f} ns")
    print(f"  Plasma freq     : {r2['f_plasma_MHz']:.2f} MHz  → "
          f"blocked={r2['plasma_blocked']}")
    print(DIV2)
    print(f"  SNR             : {r2['SNR_dB']:>+.2f} dB")
    print(f"  Data Loss       : {r2['data_loss_pct']:.3f} %")
    print(f"  Risk Level      : {r2['risk_level']}")
    print(f"  Notes           : {r2['notes']}")
    print(DIV)

    # ─────────────────────────────────────────────────────────────
    # DEMO 3: Batch telemetry — synthetic time-series
    # ─────────────────────────────────────────────────────────────
    events = ["nominal", "nominal", "quiet", "mild_storm",
              "moderate_storm", "strong_storm", "severe_storm",
              "extreme_storm", "extreme_storm", "extreme_storm"]
    demo_records = [
        {**sample_record,
         "timestamp":             f"2026-03-28T0{i}:00:00Z",
         "geomagnetic_index_Kp":  float(i),
         "ionospheric_TEC":       20.0 + i * 10.0,
         "event_type":            events[i],
         }
        for i in range(min(10, len(events)))
    ]

    with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, dir="/tmp") as tf:
        json.dump(demo_records, tf)
        tmp_path = tf.name

    try:
        df_demo = process_telemetry_json(tmp_path, export_csv=False)
        print(f"\n{DIV}")
        print("  BATCH TELEMETRY DEMO  (10 synthetic records)")
        print_telemetry_table(df_demo)
    finally:
        os.unlink(tmp_path)

    # ─────────────────────────────────────────────────────────────
    # DEMO 4: predict_realtime()  single-call example
    # ─────────────────────────────────────────────────────────────
    print(f"\n{DIV}")
    print("  predict_realtime()  —  single call:")
    print(DIV2)
    s = predict_realtime(bz=-20.0, speed=650, density=15, kp=7.0, flux=5.0)
    print(f"  SNR         : {s['snr_dB']:>+.2f} dB")
    print(f"  Data Loss   : {s['data_loss_pct']:.3f} %")
    print(f"  Storm Risk  : {s['storm_risk']}")
    print(f"  FSPL        : {s['fspl_dB']:.2f} dB")
    print(DIV)

    sys.exit(0)
