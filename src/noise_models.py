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
from typing import Optional
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
                  total_noise: np.ndarray,
                  pdyn: Optional[np.ndarray] = None,
                  ) -> tuple[np.ndarray, np.ndarray]:
    """
    Jeomanyetik fırtına sırasında tüm gürültü bileşenlerini ölçekle.

    Birincil kriter (Kp gerçek OMNI verisi mevcutsa):
        Bz < 0  VE  Kp > 5  (Ippolito 2017, Bölüm 9.3)

    RTSW-yerel yedek kriter (OMNI kapsamı yoksa, Kp NaN):
        Bz < STORM_BZ_THRESH  VE  Pdyn > STORM_PDYN_THRESH
        (Newell et al. 2008 â€“ sürekli iletim fonksiyonundan türetilmiş;
         proxy/sabit değerler içermez, yalnızca ölçülen RTSW büyüklükler kullanılır)

    Parametreler
    ------------
    bz          : np.ndarray  —  Bz bileşeni  [nT GSM]
    kp          : np.ndarray  —  Kp indeksi   [0–9], NaN = OMNI mevcut değil
    total_noise : np.ndarray  —  ham toplam gürültü  [W]
    pdyn        : np.ndarray | None  —  dinamik basınç  [nPa] (RTSW'den)

    Döndürür
    --------
    scaled_noise : np.ndarray  —  ölçeklenmiş gürültü [W]
    storm_flag   : np.ndarray (bool)  —  fırtına anı maskesi
    """
    kp_available = np.isfinite(kp)

    # Birincil kriter: gerçek Kp varsa kullan
    storm_primary = kp_available & (bz < 0) & (kp > 5)

    # RTSW-yerel yedek kriter: Kp NaN olduğunda devreye girer
    if pdyn is not None:
        storm_fallback = (
            (~kp_available)
            & (bz  < CFG.phys.STORM_BZ_THRESH)
            & (pdyn > CFG.phys.STORM_PDYN_THRESH)
        )
    else:
        storm_fallback = np.zeros(len(bz), dtype=bool)

    storm_flag   = storm_primary | storm_fallback
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
    Fizik tabanlı SNR pipeline'ına yönlendirici.

    Bağlantı bütçesi (FSPL + Pt + Gt + Gr), uzay havası gürültüsü
    (N_sw = a·|Bz| + b·v·n + c·Kp² + d·flux) ve sigmoid veri kaybı
    modeli için physics_model.run_physics_pipeline() kullanılır.

    Referans: physics_model.py belge dizisi.
    """
    from physics_model import run_physics_pipeline
    return run_physics_pipeline(df)