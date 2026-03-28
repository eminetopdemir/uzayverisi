"""
data_loader.py  —  Veri Yükleme ve Temizleme Modülü
================================================================
Üç veri kaynağını (OMNI, RTSW, GOES) okur, hatalı değerleri
temizler ve ortak bir zaman damgasına hizalar.

Akademik Referans:
    Ippolito (2017): Satellite Communications Systems Engineering
    → Veri kalite kontrolü ve resampling standardı için.
"""

import numpy as np
import pandas as pd
import json
import logging
from pathlib import Path
from typing import Optional
from config import CFG

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════

def _replace_fill(series: pd.Series,
                  upper_thresh: float = CFG.fill.OMNI_LARGE,
                  lower_thresh: float = CFG.fill.RTSW_FLAG) -> pd.Series:
    """
    Dolgu değerlerini (fill values) NaN ile değiştir.
    OMNI'de büyük pozitif sayılar (99999…), RTSW'de -99999 kullanılır.
    """
    s = series.copy().astype(float)
    s[s >= upper_thresh] = np.nan
    s[s <= lower_thresh] = np.nan
    return s


def _interpolate(df: pd.DataFrame) -> pd.DataFrame:
    """Lineer zaman interpolasyonu + başlangıç/bitiş forward/backward fill."""
    return df.interpolate(method="time").ffill().bfill()


# ═══════════════════════════════════════════════════════════════
# OMNI YÜKLEYİCİ  (Saatlik)
# ═══════════════════════════════════════════════════════════════

def load_omni(filepath: Path = CFG.paths.omni_file) -> pd.DataFrame:
    """
    NASA OMNI saatlık JSON veri dosyasını yükle.

    Beklenen JSON alan adları (OMNIWeb JSON schema):
        year, doy, hour,
        scalar_B_nT, Bz_nT_GSM, sw_plasma_temperature_K,
        sw_proton_density_N_cm3, sw_plasma_speed_km_s,
        flow_pressure, Kp_index, proton_flux_gt1MeV

    Döndürür:
        pd.DataFrame  — DatetimeIndex, temizlenmiş değerler
    """
    if filepath is None:
        filepath = CFG.paths.omni_file

    with open(filepath, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    records = []
    for entry in data:
        try:
            year = int(entry["year"])
            doy  = int(entry["doy"])
            hr   = int(entry["hour"])
            dt = (pd.Timestamp(f"{year}-01-01")
                  + pd.Timedelta(days=doy - 1, hours=hr))
            records.append({
                "time":     dt,
                "Scalar_B": float(entry.get("scalar_B_nT",                np.nan)),
                "BZ":       float(entry.get("Bz_nT_GSM",                 np.nan)),
                "Temp":     float(entry.get("sw_plasma_temperature_K",   np.nan)),
                "Dens":     float(entry.get("sw_proton_density_N_cm3",   np.nan)),
                "Speed":    float(entry.get("sw_plasma_speed_km_s",      np.nan)),
                "FlowP":    float(entry.get("flow_pressure",             np.nan)),
                # Kp_index in OMNIWeb is stored as Kp×10 (e.g. 27 = Kp 2.7)
                "Kp":       float(entry.get("Kp_index",                  np.nan)) / 10.0,
                "PF1":      float(entry.get("proton_flux_gt1MeV",        np.nan)),
            })
        except (ValueError, KeyError, TypeError):
            continue

    df = pd.DataFrame(records).set_index("time").sort_index()
    df = df[~df.index.duplicated(keep="first")]

    # Hatalı değerleri temizle
    for col in ["Scalar_B", "BZ", "Temp", "Dens", "Speed", "FlowP"]:
        df[col] = _replace_fill(df[col])
    df["Kp"]  = df["Kp"].where(df["Kp"] <= 9.0, np.nan)
    df["PF1"] = _replace_fill(df["PF1"])

    df = _interpolate(df)
    if len(df):
        log.info(f"[OMNI]  {len(df)} satır yüklendi: {df.index[0]} → {df.index[-1]}")
    else:
        log.warning("[OMNI]  Hiç satır yüklenemedi — dosya formatını kontrol edin.")
    return df


# ═══════════════════════════════════════════════════════════════
# RTSW YÜKLEYİCİ  (1-Dakikalık)
# ═══════════════════════════════════════════════════════════════

def load_rtsw(filepath: Optional[Path] = CFG.paths.rtsw_file) -> pd.DataFrame:
    """
    SWPC/NOAA RTSW JSON veri dosyasını yükle.

    Beklenen JSON alan adları (RTSW plot-data schema):
        timestamp, source,
        Bt, Bx, By, Bz [nT], Phi [°], Theta [°],
        Dens [N/cm³], Speed [km/s], Temp [K]
    """
    if filepath is None:
        filepath = CFG.paths.rtsw_file

    with open(filepath, "r", encoding="utf-8-sig") as fh:
        data = json.load(fh)

    records = []
    for entry in data:
        try:
            dt = pd.Timestamp(entry["timestamp"]).tz_localize(None)
            records.append({
                "time":  dt,
                "Bt":    float(entry.get("Bt",    np.nan)),
                "Bx":    float(entry.get("Bx",    np.nan)),
                "By":    float(entry.get("By",    np.nan)),
                "Bz":    float(entry.get("Bz",    np.nan)),
                "Phi":   float(entry.get("Phi",   np.nan)),
                "Theta": float(entry.get("Theta", np.nan)),
                "Dens":  float(entry.get("Dens",  np.nan)),
                "Speed": float(entry.get("Speed", np.nan)),
                "Temp":  float(entry.get("Temp",  np.nan)),
            })
        except (ValueError, KeyError, TypeError):
            continue

    df = pd.DataFrame(records).set_index("time").sort_index()
    df = df[~df.index.duplicated(keep="first")]

    # -99999 → NaN
    for col in df.columns:
        df[col] = _replace_fill(df[col],
                                upper_thresh=9e4,
                                lower_thresh=CFG.fill.RTSW_FLAG)

    df = _interpolate(df)
    if len(df):
        log.info(f"[RTSW]  {len(df)} satır yüklendi: {df.index[0]} → {df.index[-1]}")
    else:
        log.warning("[RTSW]  Hiç satır yüklenemedi — dosya formatını kontrol edin.")
    return df


# ═══════════════════════════════════════════════════════════════
# GOES YÜKLEYİCİ  (JSON, opsiyonel)
# ═══════════════════════════════════════════════════════════════

def load_goes(filepath: Optional[Path] = CFG.paths.goes_file) -> pd.DataFrame:
    """
    GOES proton flux JSON dosyasını yükle.
    Yalnızca yüksek enerji kanalı (A5 / >55 MeV) kullanılır.
    Dosya bulunamazsa boş DataFrame döndürür.
    """
    if filepath is None:
        filepath = CFG.paths.goes_file
    if not Path(filepath).exists():
        log.warning(f"[GOES]  Dosya bulunamadı: {filepath} — sıfır flux varsayılıyor.")
        return pd.DataFrame(columns=["flux"])

    with open(filepath, "r") as fh:
        data = json.load(fh)

    records = []
    for entry in data:
        if entry.get("channel") in ("A5", "A6"):
            records.append({
                "time": pd.Timestamp(entry["time_tag"]).tz_localize(None),
                "flux": float(entry.get("flux", 0.0)),
            })

    if not records:
        return pd.DataFrame(columns=["flux"])

    df = pd.DataFrame(records).set_index("time")
    df = df[~df.index.duplicated(keep="first")].sort_index()
    df["flux"] = df["flux"].clip(lower=0.0)
    log.info(f"[GOES]  {len(df)} satır yüklendi.")
    return df


# ═══════════════════════════════════════════════════════════════
# BİRLEŞTİRME
# ═══════════════════════════════════════════════════════════════

def merge_all(df_rtsw: pd.DataFrame,
              df_omni: pd.DataFrame,
              df_goes: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    OMNI (saatlik) ve GOES (dakikalık) verilerini RTSW'nin
    1-dakikalık çözünürlüğüne hizalar ve birleştirir.

    Strateji:
        pd.merge_asof(tolerance=CFG.phys.OMNI_TOLERANCE)  →  OMNI alanları yalnızca
        gerçek zaman örtüşmesi olan satırlara eklenir; örtüşme yoksa NaN kalır
        (asla proxy/sabit dolgu yapılmaz).
        Kp NaN kaldığında storm_scaling RTSW-yerel Bz+Pdyn kriterini kullanır.

    Çıktı sütunları:
        Bz, Dens, Speed, Temp, Pdyn    (RTSW'den — her zaman gerçek veri)
        Kp, Scalar_B, BZ_omni          (OMNI'den — yalnızca zaman örtüşmesi varsa)
        flux                           (GOES'tan)
    """
    # ── RTSW tabanı + fiziksel türetilmiş sütun ──────────────
    df = df_rtsw[["Bz", "Dens", "Speed", "Temp"]].copy()
    # Dinamik basınç: Pdyn [nPa] = 1.67e-6 × n [cm⁻³] × v² [km/s]²
    # (tamamen RTSW'den, proxy değil)
    df["Pdyn"] = 1.67e-6 * df["Dens"] * df["Speed"] ** 2

    # ── OMNI → merge_asof ile katı zaman toleransı ───────────
    # Tolerans dışındaki satırlar NaN döner (proxy enjeksiyonu olmaz).
    omni_cols = (df_omni[["Kp", "Scalar_B", "BZ"]]
                 .rename(columns={"BZ": "BZ_omni"})
                 .reset_index()
                 .sort_values("time"))

    merged = pd.merge_asof(
        df.reset_index().sort_values("time"),
        omni_cols,
        on="time",
        direction="nearest",
        tolerance=pd.Timedelta(CFG.phys.OMNI_TOLERANCE),
    ).set_index("time").sort_index()

    # ── Örtüşme raporu ───────────────────────────────────────
    n_matched = merged["Kp"].notna().sum()
    n_total   = len(merged)
    if n_matched == 0:
        log.error(
            "[MERGE] OMNI ve RTSW'nin zaman aralıkları hiç örtüşmüyor!\n"
            f"         OMNI : {df_omni.index[0]}  →  {df_omni.index[-1]}\n"
            f"         RTSW : {df_rtsw.index[0]}  →  {df_rtsw.index[-1]}\n"
            f"         Tolerans : {CFG.phys.OMNI_TOLERANCE}\n"
            "         → Kp ve BZ_omni sütunları NaN olarak bırakıldı.\n"
            "           Fırtına algılama otomatik olarak RTSW-yerel\n"
            "           Bz + Pdyn kriterine geçecek (proxy yok).\n"
            "           Gerçek Kp verisi için OMNI dosyasını RTSW dönemiyle\n"
            "           örtüşen bir tarih aralığı için güncelleyin."
        )
    elif n_matched < n_total * 0.5:
        log.warning(
            f"[MERGE] OMNI yalnızca %{100*n_matched/n_total:.0f} RTSW satırıyla "
            f"eşleşti ({n_matched}/{n_total}). Zaman örtüşmesini doğrulayın."
        )
    else:
        log.info(f"[MERGE] OMNI {n_matched}/{n_total} satırla eşleşti.")

    # ── Scalar_B: gerçek medyan, tümü NaN ise standart değer ─
    scalar_b_median = merged["Scalar_B"].median()
    merged["Scalar_B"] = merged["Scalar_B"].fillna(
        scalar_b_median if pd.notna(scalar_b_median) else 5.0
    )
    # Kp'yi asla sabit/proxy değerle doldurmuyoruz — NaN olarak kalır,
    # storm_scaling bunu RTSW kriterinin kullanılması gerektiği sinyal olarak okur.

    # ── GOES flux — 1-dakikalık ızgaraya yeniden örnekle ─────
    if df_goes is not None and len(df_goes) > 0:
        goes_1min = df_goes[["flux"]].resample("1min").interpolate(method="time")
        merged = merged.join(goes_1min, how="left")
        merged["flux"] = merged["flux"].fillna(0.0)
    else:
        merged["flux"] = 0.0

    merged = merged.ffill().bfill()
    log.info(
        f"[MERGE] Birleşik tablo: {len(merged)} satır, "
        f"sütunlar: {list(merged.columns)}"
    )
    return merged