"""
noise_models.py  —  Fiziksel Gürültü Modelleri
================================================================
Her fonksiyon kendi akademik referansıyla belgelenmiştir.

Referanslar:
    [1] Nyquist, H. (1928). "Thermal Agitation of Electric Charge
        in Conductors." Physical Review, 32(1), 110-113.
    [2] Rickett, B.J. (1977). "Interplanetary Scintillation."
        Annual Review of Astronomy and Astrophysics, 15, 479-504.
    [3] Xapsos, M.A. et al. (2000). "Proton Test Data for Space
        Environment Effects Modeling." IEEE TNS 47(6).
    [4] Ippolito, L.J. (2017). "Satellite Communications Systems
        Engineering." Wiley-IEEE Press, 3rd Ed.
"""

import numpy as np
import pandas as pd
from config import CFG

rng = np.random.default_rng(seed=42)


# ───────────────────────────────────────────────────────────────
# 1. TERMAL GÜRÜLTÜ  —  Nyquist-Johnson (1928)                [1]
# ───────────────────────────────────────────────────────────────

def thermal_noise(temp_K: np.ndarray) -> np.ndarray:
    """
    Nyquist-Johnson ısıl gürültü gücü:

        N_th = k_B · T · B

    Parametreler
    ------------
    temp_K : np.ndarray
        Plazma sıcaklığı [K]

    Döndürür
    --------
    np.ndarray  —  gürültü gücü [W]

    Referans: Nyquist (1928) [1]
    """
    T = np.clip(temp_K, 1e2, 1e8)           # fiziksel sınır
    return CFG.phys.kB * T * CFG.phys.BANDWIDTH_HZ


# ───────────────────────────────────────────────────────────────
# 2. PLAZMA SİNTİLASYONU  —  Rickett (1977)                   [2]
# ───────────────────────────────────────────────────────────────

def scintillation_noise(dens: np.ndarray,
                        speed: np.ndarray) -> np.ndarray:
    """
    Interplanetary sintilasyon (IPS) modeli:

        N_scint = α · ρ · v²

    α = 1e-30  (emprik ölçekleme, bkz. Rickett 1977 Eq. 2.4)

    Parametreler
    ------------
    dens  : np.ndarray  — proton yoğunluğu  [N/cm³]
    speed : np.ndarray  — güneş rüzgarı hızı [km/s]

    Döndürür
    --------
    np.ndarray  —  gürültü gücü [W]

    Referans: Rickett (1977) [2]
    """
    rho = np.abs(dens)
    v   = np.abs(speed)
    return CFG.phys.SCINT_ALPHA * (rho * v ** 2)


# ───────────────────────────────────────────────────────────────
# 3. RADYASYON IMPULSE GÜRÜLTÜSÜ  —  Xapsos (2000)            [3]
# ───────────────────────────────────────────────────────────────

def radiation_noise(flux: np.ndarray) -> np.ndarray:
    """
    Yüksek enerjili protonların elektroniklerde oluşturduğu
    anlık (impulse) gürültü:

        flux > eşik  →  Spike ~ Exp(λ · P_signal · 50)

    Eşik altında gürültü sıfırdır; bu SEU (Single-Event Upset)
    modelinin basitleştirilmiş halidir.

    Parametreler
    ------------
    flux : np.ndarray  —  GOES proton akısı [pfu / (cm²·sr·s·MeV)]

    Döndürür
    --------
    np.ndarray  —  gürültü gücü [W]

    Referans: Xapsos (2000) [3]
    """
    noise      = np.zeros(len(flux))
    spike_mask = flux > CFG.phys.PROTON_THRESH
    n_spikes   = spike_mask.sum()
    if n_spikes > 0:
        scale = CFG.phys.SIGNAL_POWER * 50.0
        noise[spike_mask] = rng.exponential(scale=scale, size=n_spikes)
    return noise


# ───────────────────────────────────────────────────────────────
# 4. FIRTINA ÖLÇEKLEMESİ  —  Ippolito (2017)                  [4]
# ───────────────────────────────────────────────────────────────

def storm_scaling(bz: np.ndarray,
                  kp: np.ndarray,
                  total_noise: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Jeomanyetik fırtına sırasında tüm gürültü bileşenlerini ölçekle.

    Kriter (Ippolito 2017, Bölüm 9.3):
        Bz < 0  VE  Kp > 5  →  N_total × STORM_COEFF

    Parametreler
    ------------
    bz          : np.ndarray  —  Bz bileşeni  [nT GSM]
    kp          : np.ndarray  —  Kp indeksi   [0–9]
    total_noise : np.ndarray  —  ham toplam gürültü  [W]

    Döndürür
    --------
    scaled_noise : np.ndarray  —  ölçeklenmiş gürültü [W]
    storm_flag   : np.ndarray (bool)  —  fırtına anı maskesi
    """
    storm_flag   = (bz < 0) & (kp > 5)
    scaled_noise = total_noise.copy()
    scaled_noise[storm_flag] *= CFG.phys.STORM_COEFF
    return scaled_noise, storm_flag


# ───────────────────────────────────────────────────────────────
# 5. SNR HESAPLAMA
# ───────────────────────────────────────────────────────────────

def compute_snr(total_noise: np.ndarray,
                signal_power: float = CFG.phys.SIGNAL_POWER
                ) -> tuple[np.ndarray, np.ndarray]:
    """
    Sinyal-Gürültü Oranı:

        SNR_linear = P_signal / N_total
        SNR_dB     = 10 · log10(SNR_linear)

    Döndürür
    --------
    snr_linear, snr_dB  (her ikisi de np.ndarray)
    """
    snr_lin = signal_power / np.maximum(total_noise, 1e-30)
    snr_dB  = 10.0 * np.log10(np.maximum(snr_lin, 1e-10))
    return snr_lin, snr_dB


# ───────────────────────────────────────────────────────────────
# 6. ANA SİMÜLASYON PİPELINE
# ───────────────────────────────────────────────────────────────

def run_noise_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    """
    Birleştirilmiş veri çerçevesini alır; tüm gürültü bileşenlerini
    ve SNR'yi hesaplar; sonuçları yeni sütunlar olarak döndürür.

    Beklenen giriş sütunları: Temp, Dens, Speed, Bz, Kp, flux
    """
    out = df.copy()

    out["N_thermal"] = thermal_noise(out["Temp"].values)
    out["N_scint"]   = scintillation_noise(out["Dens"].values,
                                           out["Speed"].values)
    out["N_rad"]     = radiation_noise(out["flux"].values)

    out["N_total_raw"] = (out["N_thermal"]
                          + out["N_scint"]
                          + out["N_rad"])

    out["N_total"], out["storm_flag"] = storm_scaling(
        out["Bz"].values,
        out["Kp"].values,
        out["N_total_raw"].values,
    )

    out["SNR_lin"], out["SNR_dB"] = compute_snr(out["N_total"].values)

    # Özet log
    n_storm = int(out["storm_flag"].sum())
    import logging
    log = logging.getLogger(__name__)
    log.info(f"[MODEL] Ortalama SNR : {out['SNR_dB'].mean():.2f} dB")
    log.info(f"[MODEL] Min SNR      : {out['SNR_dB'].min():.2f} dB")
    log.info(f"[MODEL] Max SNR      : {out['SNR_dB'].max():.2f} dB")
    log.info(f"[MODEL] Fırtına süresi: {n_storm} dakika")

    return out