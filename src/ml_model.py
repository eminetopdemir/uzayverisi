"""
ml_model.py  —  Fizik-Destekli SNR Tahmin Modeli
================================================================
Mimari: Physics-Informed Regression

    Fiziksel gürültü pipeline'ı  →  physics_snr  (hedef)
    RTSW / GOES ölçümleri        →  mühendislik özellikleri
    Ridge Regression              →  öğrenilmiş SNR tahmini

Neden Ridge (yorumlanabilir)?
    - Her katsayı doğrudan bir fiziksel büyüklüğe bağlanabilir.
    - L2 regularizasyon çoklu doğrusallığı (Dens × Speed korelasyonu)
      kararlı biçimde çözer.
    - GradientBoosting da desteklenir (--model gb) fakat katsayı çıktısı
      olmaz.

Referanslar:
    Hoerl & Kennard (1970). "Ridge Regression." Technometrics, 12(1).
    Newell et al. (2008). JGR — Kp iletim fonksiyonu.
    Ippolito (2017). Satellite Communications Systems Engineering.
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Optional, Union

import numpy as np
import pandas as pd

from sklearn.linear_model import Ridge
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import r2_score, mean_absolute_error

from config import CFG

log = logging.getLogger(__name__)

# ── Varsayılan model kayıt yolu ──────────────────────────────
_MODEL_PATH = CFG.paths.outputs / "snr_model.pkl"

# ── SNR → veri kaybı eğrisi parametreleri ───────────────────
# Lojistik eğri: loss% = 100 / (1 + exp(k · (SNR_dB − SNR_mid)))
# SNR_mid = -8 dB → %50 kayıp (mevcut ortalama SNR civarı)
# k       =  0.45 → geçiş eğimi (her 5 dB'de ~%30 değişim)
_LOSS_K   = 0.45
_LOSS_MID = -8.0


# ═══════════════════════════════════════════════════════════════
# 1.  ÖZELLIK MÜHENDİSLİĞİ
# ═══════════════════════════════════════════════════════════════

# Ham sütunlar ve fiziksel gerekçeleri
_BASE_COLS = ["Bz", "Dens", "Speed", "Temp", "Pdyn", "flux"]

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fizik destekli özellik matrisi oluştur.

    Ham ölçümler + türetilmiş nonlineer terimler.
    Hiçbir değer uydurulmaz; yalnızca mevcut sütunlardan hesaplanır.

    Özellikler ve fiziksel gerekçeleri
    -----------------------------------
    Bz          : Güney IMF bileşeni [nT]  — doğrudan fırtına itici
    Bz_south    : clip(Bz, −∞, 0)         — birincil fırtına kaynağı
    |Bz|        : abs(Bz)                  — gürültü büyüklüğü
    Dens        : proton yoğunluğu [cm⁻³] — sintilasyon gücü
    Speed       : güneş rüzgarı hızı [km/s]
    Pdyn        : 1.67e−6·n·v²  [nPa]     — toplam dinamik baskı (RTSW yerel)
    Temp        : plazma sıcaklığı [K]     — doğrudan N_thermal'i belirler
    log_Temp    : log10(Temp)              — gürültü log ölçeğinde çalışır
    log_Dens    : log10(Dens + ε)          — yoğunluk yayılımı sağa çarpık
    v2          : Speed²                   — N_scint ∝ ρ·v²
    flux        : GOES proton flux [pfu]
    log_flux    : log10(flux + ε)          — Xapsos spike dağılımı
    storm_flag  : Bz+Pdyn yerel fırtına maskesi (0/1)
    """
    f = pd.DataFrame(index=df.index)

    # Doğrudan ölçümler
    f["Bz"]         = df["Bz"]
    f["Bz_south"]   = df["Bz"].clip(upper=0.0)
    f["abs_Bz"]     = df["Bz"].abs()
    f["Dens"]       = df["Dens"]
    f["Speed"]      = df["Speed"]
    f["Pdyn"]       = df["Pdyn"]
    f["Temp"]       = df["Temp"]
    f["flux"]       = df["flux"]

    # Fizik-motivasyonlu nonlineer dönüşümler
    f["log_Temp"]   = np.log10(df["Temp"].clip(lower=1.0))
    f["log_Dens"]   = np.log10(df["Dens"].clip(lower=1e-6))
    f["v2"]         = df["Speed"] ** 2
    f["log_flux"]   = np.log10(df["flux"].clip(lower=1e-15))

    # Fırtına maskesi (RTSW yerel, proxy yok)
    if "storm_flag" in df.columns:
        f["storm_flag"] = df["storm_flag"].astype(float)
    else:
        bz_south = df["Bz"].clip(upper=0.0).abs()
        f["storm_flag"] = (
            (df["Bz"]   < CFG.phys.STORM_BZ_THRESH)
            & (df["Pdyn"] > CFG.phys.STORM_PDYN_THRESH)
        ).astype(float)

    # Kp: yalnızca gerçek OMNI verisi varsa dahil et
    if "Kp" in df.columns and df["Kp"].notna().any():
        f["Kp"] = df["Kp"].fillna(df["Kp"].median())
    # Kp tamamen NaN ise sütun ekleme — model bu durumda sessizce devam eder.

    return f


# ═══════════════════════════════════════════════════════════════
# 2.  MODEL EĞİTİMİ
# ═══════════════════════════════════════════════════════════════

def train(df_result: pd.DataFrame,
          model_type: str = "ridge",
          alpha: float = 1.0,
          save_path: Optional[Path] = None) -> dict:
    """
    Fiziksel SNR pipeline çıktısını hedef alarak regresyon modeli eğit.

    Parametreler
    ------------
    df_result  : run_noise_pipeline() çıktısı (SNR_dB sütunu içermeli)
    model_type : "ridge" (varsayılan, yorumlanabilir) | "gb" (GradientBoosting)
    alpha      : Ridge L2 regularizasyon gücü
    save_path  : None → outputs/snr_model.pkl

    Döndürür
    --------
    dict:
        model      : eğitilmiş sklearn Pipeline
        features   : özellik adları listesi
        metrics    : {r2_train, r2_test, mae_test, cv_r2_mean, cv_r2_std}
        coef_df    : Ridge katsayıları (model_type="ridge" ise)
    """
    if "SNR_dB" not in df_result.columns:
        raise ValueError("df_result 'SNR_dB' sütununu içermiyor.")

    X = build_features(df_result)
    y = df_result["SNR_dB"].values

    feature_names = list(X.columns)
    X_arr = X.values

    # Zaman serisi bölme: son %20 test, geri kalanı eğitim
    split = int(len(X_arr) * 0.80)
    X_train, X_test = X_arr[:split], X_arr[split:]
    y_train, y_test = y[:split],     y[split:]

    # Model seçimi
    if model_type == "ridge":
        estimator = Ridge(alpha=alpha, fit_intercept=True)
    elif model_type == "gb":
        estimator = GradientBoostingRegressor(
            n_estimators=200, max_depth=3, learning_rate=0.05,
            subsample=0.8, random_state=42
        )
    else:
        raise ValueError(f"Bilinmeyen model_type: {model_type!r}. 'ridge' veya 'gb' kullanın.")

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("model",  estimator),
    ])

    pipe.fit(X_train, y_train)

    # Metrikler
    y_pred_train = pipe.predict(X_train)
    y_pred_test  = pipe.predict(X_test)
    r2_train = r2_score(y_train, y_pred_train)
    r2_test  = r2_score(y_test,  y_pred_test)
    mae_test = mean_absolute_error(y_test, y_pred_test)

    # Zaman serisi çapraz doğrulama (eğitim seti üzerinde, 5 katman)
    tscv = TimeSeriesSplit(n_splits=5)
    cv_scores = cross_val_score(pipe, X_train, y_train, cv=tscv,
                                scoring="r2", n_jobs=1)

    metrics = {
        "r2_train":   round(r2_train,  4),
        "r2_test":    round(r2_test,   4),
        "mae_test_dB": round(mae_test, 4),
        "cv_r2_mean": round(cv_scores.mean(), 4),
        "cv_r2_std":  round(cv_scores.std(),  4),
    }

    log.info("[ML]  Eğitim R²  : %.4f", r2_train)
    log.info("[ML]  Test R²    : %.4f", r2_test)
    log.info("[ML]  Test MAE   : %.4f dB", mae_test)
    log.info("[ML]  CV R²      : %.4f ± %.4f", cv_scores.mean(), cv_scores.std())

    # Ridge katsayılarını logla
    coef_df = None
    if model_type == "ridge":
        coefs = pipe.named_steps["model"].coef_
        coef_df = (
            pd.DataFrame({"feature": feature_names, "coefficient": coefs})
            .reindex(pd.Series(np.abs(coefs)).sort_values(ascending=False).index)
            .reset_index(drop=True)
        )
        log.info("[ML]  Ridge katsayıları (mutlak değerle sıralı):")
        for _, row in coef_df.iterrows():
            log.info("        %-15s  %+.4f", row["feature"], row["coefficient"])

    # Modeli kaydet
    out = save_path or _MODEL_PATH
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as fh:
        pickle.dump({"pipe": pipe, "features": feature_names}, fh)
    log.info("[ML]  Model kaydedildi → %s", out)

    return {"model": pipe, "features": feature_names,
            "metrics": metrics, "coef_df": coef_df}


# ═══════════════════════════════════════════════════════════════
# 3.  SNR → VERİ KAYBI %
# ═══════════════════════════════════════════════════════════════

def snr_to_data_loss(snr_db: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
    """
    SNR değerini gerçekçi veri kaybı yüzdesine dönüştür.

    Formül (lojistik / sigmoid eğrisi):

        loss% = 100 / (1 + exp(k · (SNR_dB − SNR_mid)))

    Parametreler
    ------------
    k       = 0.45   → eğim: her ~5 dB'de ≈%30 değişim
    SNR_mid = −8 dB  → %50 kayıp noktası (mevcut ortalama SNR)

    SNR referans noktaları:
        SNR = −17 dB  → ≈ 98 % kayıp  (en kötü durum)
        SNR =  −8 dB  → ≈ 50 % kayıp  (ortalama)
        SNR =  −3 dB  → ≈ 30 % kayıp  (görece iyi)
        SNR =   0 dB  → ≈ 22 % kayıp  (eşit sinyal-gürültü)
        SNR = +10 dB  → ≈  8 % kayıp  (iyi alım)

    Kaynak: sigmoid link-budget degradation modeli,
            Ippolito (2017) Bölüm 3 / BER-SNR eğrisi.

    Parametreler
    ------------
    snr_db : scalar veya np.ndarray  —  SNR değeri [dB]

    Döndürür
    --------
    float veya np.ndarray  —  veri kaybı yüzdesi [0, 100]
    """
    return 100.0 / (1.0 + np.exp(_LOSS_K * (np.asarray(snr_db) - _LOSS_MID)))


# ═══════════════════════════════════════════════════════════════
# 4.  GERÇEK ZAMANLI TAHMİN
# ═══════════════════════════════════════════════════════════════

def load_model(model_path: Optional[Path] = None) -> dict:
    """Kaydedilmiş modeli yükle."""
    path = model_path or _MODEL_PATH
    if not Path(path).exists():
        raise FileNotFoundError(
            f"Model dosyası bulunamadı: {path}\n"
            "  Önce train() çağırın veya main.py --ml ile eğitin."
        )
    with open(path, "rb") as fh:
        return pickle.load(fh)


def predict(
    observation: Union[pd.Series, pd.DataFrame, dict],
    model_path: Optional[Path] = None,
    _cached_model: Optional[dict] = None,
) -> dict:
    """
    Tek bir gözlem (veya gözlem dizisi) için SNR ve veri kaybı tahmin et.

    Parametreler
    ------------
    observation  : Beklenen anahtarlar/sütunlar:
                       Bz [nT], Dens [cm⁻³], Speed [km/s],
                       Temp [K], Pdyn [nPa], flux [pfu]
                   Opsiyonel: Kp, storm_flag
    model_path   : Kaydedilmiş model dosyası yolu (yoksa varsayılan)
    _cached_model: Zaten yüklenmiş model sözlüğü (döngü içi kullanım için)

    Döndürür
    --------
    dict:
        snr_db_predicted  : tahmin edilen SNR [dB]
        data_loss_pct     : veri kaybı yüzdesi [0–100]
        storm_risk        : "NONE" | "LOW" | "MODERATE" | "HIGH"

    Örnek kullanım:
        result = predict({"Bz": -4.2, "Dens": 8.5, "Speed": 480,
                          "Temp": 65000, "Pdyn": 3.4, "flux": 1e-8})
        print(result["data_loss_pct"])
    """
    mdl = _cached_model or load_model(model_path)
    pipe: Pipeline = mdl["pipe"]
    feature_names: list = mdl["features"]

    # Girdiyi tek-satırlık DataFrame'e normalize et
    if isinstance(observation, dict):
        df_in = pd.DataFrame([observation])
    elif isinstance(observation, pd.Series):
        df_in = observation.to_frame().T
    else:
        df_in = observation.copy()

    # Özellik matrisini oluştur (eğitimdekiyle aynı fonksiyon)
    X_feat = build_features(df_in)

    # Eğitimde olmayan sütunları sıfırla; eksik sütunları 0 ile doldur
    for col in feature_names:
        if col not in X_feat.columns:
            X_feat[col] = 0.0
    X_feat = X_feat[feature_names]

    snr_pred = pipe.predict(X_feat.values)
    loss_pct  = snr_to_data_loss(snr_pred)

    # Fırtına risk seviyesi
    def _risk(loss: float) -> str:
        if loss >= 80:  return "HIGH"
        if loss >= 55:  return "MODERATE"
        if loss >= 30:  return "LOW"
        return "NONE"

    if len(snr_pred) == 1:
        result = {
            "snr_db_predicted": float(snr_pred[0]),
            "data_loss_pct":    float(loss_pct[0]),
            "storm_risk":       _risk(float(loss_pct[0])),
        }
    else:
        result = {
            "snr_db_predicted": snr_pred,
            "data_loss_pct":    loss_pct,
            "storm_risk":       np.vectorize(_risk)(loss_pct),
        }

    return result


# ═══════════════════════════════════════════════════════════════
# 5.  TAM DATAFRAME'E TAHMİN UYGULA
# ═══════════════════════════════════════════════════════════════

def predict_dataframe(df: pd.DataFrame,
                      model_path: Optional[Path] = None) -> pd.DataFrame:
    """
    Tüm birleştirilmiş veri çerçevesine toplu tahmin uygula.
    df_result'a 'SNR_dB_ml' ve 'data_loss_pct' sütunları ekler.
    """
    mdl     = load_model(model_path)
    results = predict(df, _cached_model=mdl)

    out = df.copy()
    out["SNR_dB_ml"]    = results["snr_db_predicted"]
    out["data_loss_pct"] = results["data_loss_pct"]
    out["storm_risk"]   = results["storm_risk"]

    log.info("[ML]  Tahmin tamamlandı:")
    log.info("       Ortalama SNR (ML)   : %.2f dB", out["SNR_dB_ml"].mean())
    log.info("       Ortalama veri kaybı : %.1f %%", out["data_loss_pct"].mean())
    log.info("       Max veri kaybı      : %.1f %%", out["data_loss_pct"].max())
    storm_rows = (out["storm_risk"].isin(["MODERATE", "HIGH"])).sum()
    log.info("       Orta/Yüksek risk    : %d dakika", storm_rows)

    return out
