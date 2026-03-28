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
    NASA OMNI saatlik veri dosyasını yükle.

    Sütunlar:
        Scalar_B [nT], BZ [nT GSM], Temp [K], Dens [N/cm³],
        Speed [km/s], FlowP [nPa], Kp [×10]

    Döndürür:
        pd.DataFrame  — DatetimeIndex, temizlenmiş değerler
    """
    records = []
    with open(filepath, "r") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("YEAR"):
                continue
            parts = line.split()
            if len(parts) < 11:
                continue
            try:
                year, doy, hr = int(parts[0]), int(parts[1]), int(parts[2])
                dt = (pd.Timestamp(f"{year}-01-01")
                      + pd.Timedelta(days=doy - 1, hours=hr))
                records.append({
                    "time":     dt,
                    "Scalar_B": float(parts[3]),
                    "BZ":       float(parts[4]),
                    "Temp":     float(parts[5]),
                    "Dens":     float(parts[6]),
                    "Speed":    float(parts[7]),
                    "FlowP":    float(parts[8]),
                    "Kp":       float(parts[9]) / 10.0,   # → 0-9 skalası
                    "PF1":      float(parts[10]),
                })
            except (ValueError, IndexError):
                continue

    df = pd.DataFrame(records).set_index("time").sort_index()
    df = df[~df.index.duplicated(keep="first")]

    # Hatalı değerleri temizle
    for col in ["Scalar_B", "BZ", "Temp", "Dens", "Speed", "FlowP"]:
        df[col] = _replace_fill(df[col])
    df["Kp"]  = df["Kp"].where(df["Kp"] <= 9.0, np.nan)
    df["PF1"] = _replace_fill(df["PF1"])

    df = _interpolate(df)
    log.info(f"[OMNI]  {len(df)} satır yüklendi: {df.index[0]} → {df.index[-1]}")
    return df


# ═══════════════════════════════════════════════════════════════
# RTSW YÜKLEYİCİ  (1-Dakikalık)
# ═══════════════════════════════════════════════════════════════

def load_rtsw(filepath: Path = CFG.paths.rtsw_file) -> pd.DataFrame:
    """
    SWPC/NOAA RTSW (Real-Time Solar Wind) veri dosyasını yükle.
    Başlık satırları otomatik atlanır.

    Sütunlar:
        Bt, Bx, By, Bz [nT], Phi [°], Theta [°],
        Dens [N/cm³], Speed [km/s], Temp [K]
    """
    col_names = [
        "Timestamp", "Source",
        "Bt", "Bx", "By", "Bz",
        "Phi", "Theta",
        "Dens", "Speed", "Temp"
    ]
    records = []
    with open(filepath, "r", encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            # Başlık / yorum satırlarını atla
            if (not line
                    or line.startswith("#")
                    or line.startswith("RTSW")
                    or line.startswith("More")
                    or line.startswith("Start")
                    or line.startswith("End")
                    or line.startswith("Source")
                    or line.startswith("Resolution")
                    or line.startswith("Phi")
                    or line.startswith("Timestamp")):
                continue
            parts = line.split()
            if len(parts) < 11:
                continue
            try:
                dt = pd.Timestamp(f"{parts[0]} {parts[1]}")
                records.append({
                    "time":  dt,
                    "Bt":    float(parts[2]),
                    "Bx":    float(parts[3]),
                    "By":    float(parts[4]),
                    "Bz":    float(parts[5]),
                    "Phi":   float(parts[6]),
                    "Theta": float(parts[7]),
                    "Dens":  float(parts[8]),
                    "Speed": float(parts[9]),
                    "Temp":  float(parts[10]),
                })
            except (ValueError, IndexError):
                continue

    df = pd.DataFrame(records).set_index("time").sort_index()
    df = df[~df.index.duplicated(keep="first")]

    # -99999 → NaN
    for col in df.columns:
        df[col] = _replace_fill(df[col],
                                upper_thresh=9e4,
                                lower_thresh=CFG.fill.RTSW_FLAG)

    df = _interpolate(df)
    log.info(f"[RTSW]  {len(df)} satır yüklendi: {df.index[0]} → {df.index[-1]}")
    return df


# ═══════════════════════════════════════════════════════════════
# GOES YÜKLEYİCİ  (JSON, opsiyonel)
# ═══════════════════════════════════════════════════════════════

def load_goes(filepath: Path = CFG.paths.goes_file) -> pd.DataFrame:
    """
    GOES proton flux JSON dosyasını yükle.
    Yalnızca yüksek enerji kanalı (A5 / >55 MeV) kullanılır.
    Dosya bulunamazsa boş DataFrame döndürür.
    """
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
              df_goes: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    OMNI (saatlik) ve GOES (dakikalık) verilerini RTSW'nin
    1-dakikalık çözünürlüğüne yeniden örnekler ve birleştirir.

    Çıktı sütunları:
        Bz, Dens, Speed, Temp,      (RTSW'den)
        Kp, Scalar_B,               (OMNI'den, resampled)
        flux                        (GOES'tan)
    """
    # OMNI → dakikalık lineer interpolasyon
    omni_1min = df_omni.resample("1min").interpolate(method="time")

    df = df_rtsw[["Bz", "Dens", "Speed", "Temp"]].copy()
    df = df.join(omni_1min[["Kp", "Scalar_B", "BZ"]], how="left")

    # BZ: RTSW öncelikli, eksikse OMNI
    df["Kp"]       = df["Kp"].fillna(2.0)
    df["Scalar_B"] = df["Scalar_B"].fillna(df["Scalar_B"].median())
    df.rename(columns={"BZ": "BZ_omni"}, inplace=True)

    # GOES flux ekle
    if df_goes is not None and len(df_goes) > 0:
        df = df.join(df_goes[["flux"]], how="left")
        df["flux"] = df["flux"].fillna(0.0)
    else:
        df["flux"] = 0.0

    df = df.ffill().bfill()
    log.info(f"[MERGE] Birleşik tablo: {len(df)} satır, sütunlar: {list(df.columns)}")
    return df