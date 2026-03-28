"""
physics_model.py  —  RF Bağlantı Bütçesi + Uzay Havası Gürültü Modeli
================================================================
Uydu haberleşmesi üzerindeki uzay havası etkilerini modellemek için
fizik tabanlı, eksiksiz bir SNR hesaplama sistemi.

Referans zinciri:
    [1] Nyquist, H. (1928). "Thermal Agitation of Electric Charge in
        Conductors." Physical Review, 32(1), 110–113.
    [2] Ippolito, L.J. (2017). "Satellite Communications Systems
        Engineering." Wiley-IEEE Press, 3rd Ed.  — FSPL & bağlantı bütçesi.
    [3] Dungey, J.W. (1961). "Interplanetary Magnetic Field and the
        Auroral Zones." Phys. Rev. Lett. 6(2), 47–48.
        → IMF Bz yeniden bağlantı terimi (a·|Bz|).
    [4] Parker, E.N. (1958). "Dynamics of the Interplanetary Gas and
        Magnetic Fields." Astrophysical Journal, 128:664.
        → Güneş rüzgarı kütle akısı (b·n·v).
    [5] Secan, J.A. et al. (1997). "Improved model of equatorial
        scintillation." Radio Science, 32(4), 1523–1540.
        → Kp doğrusal olmayan sintilasyon (c·Kp²).
    [6] Xapsos, M.A. et al. (2000). "Proton Test Data for Space
        Environment Effects Modeling." IEEE TNS, 47(6).
        → Kutup şapka soğurması (d·flux).
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from config import CFG

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# 1.  SERBEST UZAY YOL KAYBI  —  Friis (1946) / Ippolito (2017) [2]
# ─────────────────────────────────────────────────────────────────

def fspl_db(distance_km: float, freq_mhz: float) -> float:
    """
    Serbest Uzay Yol Kaybı (Free-Space Path Loss):

        L_fs [dB] = 20·log10(d_km) + 20·log10(f_MHz) + 32.44

    Uzak alan koşulunda geçerlidir (d >> λ).  Sabit 32.44,
    birim dönüşümünden gelir: c = 3×10⁸ m/s, d → km, f → MHz.

    Parametreler
    ------------
    distance_km : float  — yayılım mesafesi [km]
    freq_mhz    : float  — taşıyıcı frekans [MHz]

    Döndürür
    --------
    float  —  FSPL [dB]

    Referans: Ippolito (2017) [2], Bölüm 4.2
    """
    return 20.0 * np.log10(distance_km) + 20.0 * np.log10(freq_mhz) + 32.44


# ─────────────────────────────────────────────────────────────────
# 2.  BAĞLANTI BÜTÇESİ  —  Alınan Güç  (Ippolito 2017, Bl. 4)  [2]
# ─────────────────────────────────────────────────────────────────

def received_power_W() -> float:
    """
    Friis iletim denklemi:

        P_r [dBW] = P_t [dBW] + G_t [dBi] + G_r [dBi] − L_fs [dB]

    GEO / Ku-band uydu senaryosu (config.LinkBudget'ten):
        • Mesafe          : d  = 35 786 km  (GEO yörüngesi)
        • Frekans         : f  = 12 000 MHz (Ku-band)
        • Verici gücü     : Pt = 20 dBW (100 W)
        • Verici kazancı  : Gt = 33 dBi (spot ışın)
        • Alıcı kazancı   : Gr = 52 dBi (3 m Cassegrain çanak)
        • Sistem sıc.     : T_sys = 100 K (soğutmalı LNA)

    Nominal Pr ≈ 9.8×10⁻¹¹ W  (−100 dBW).

    Döndürür
    --------
    float  —  alınan sinyal gücü [W]

    Referans: Ippolito (2017) [2]
    """
    lb = CFG.link
    l_fs   = fspl_db(lb.DISTANCE_KM, lb.FREQ_MHZ)
    pr_dBW = lb.PT_DBW + lb.GT_DBI + lb.GR_DBI - l_fs
    return 10.0 ** (pr_dBW / 10.0)


# ─────────────────────────────────────────────────────────────────
# 3.  SİSTEM TERMAL GÜRÜLTÜSÜ  —  Nyquist-Johnson (1928)        [1]
# ─────────────────────────────────────────────────────────────────

def system_thermal_noise() -> float:
    """
    Johnson–Nyquist alıcı gürültü gücü:

        N_th = k_B · T_sys · B

    T_sys = sistem gürültü sıcaklığı (config.LinkBudget.T_SYS_K);
    anten gökyüzü sıcaklığını, besleme kayıplarını ve LNA gürültü
    sayısını içerir.  Plazma sıcaklığı (Temp RTSW sütunu) KULLANILMAZ
    — bu ayrı bir uzay havası terimi olup N_sw içinde modellenir.

    Döndürür
    --------
    float  —  termal gürültü tabanı [W]

    Referans: Nyquist (1928) [1]
    """
    return CFG.phys.kB * CFG.link.T_SYS_K * CFG.phys.BANDWIDTH_HZ


# ─────────────────────────────────────────────────────────────────
# 4.  UZAY HAVASI GÜRÜLTÜSÜ  —  çok terimli eklenebilir model
# ─────────────────────────────────────────────────────────────────

def space_weather_noise(bz_nt: np.ndarray,
                        speed_kmps: np.ndarray,
                        dens_cm3: np.ndarray,
                        kp: np.ndarray,
                        flux_pfu: np.ndarray) -> np.ndarray:
    """
    Uzay havası kaynaklı efektif eklenebilir gürültü gücü:

        N_sw = a·|Bz| + b·(v·n) + c·Kp² + d·flux

    Her terimin fiziksel yorumu
    ---------------------------
    a · |Bz_nT|
        IMF güney bileşeni gündüz tarafı yeniden bağlantısını (Dungey 1961) [3]
        tetikler: güçlü |Bz| → magnetosferik konveksiyon artışı → halka
        akımı gelişimi → iyonosferik düzensizlikler → sinyal sintilasyonu.
        Birim: W/nT

    b · (Speed_km/s × Dens_cm⁻³)
        Güneş rüzgarı kütle akısı n·v, magnetopoz geçişindeki parçacık
        akısını temsil eder (Parker 1958) [4].  Artmış akı → magnetosfer
        sıkışması → plazma ısınması → parçacık enjeksiyonu → sinyal
        soğurması.
        Birim: W·s·cm³·km⁻¹

    c · Kp²
        Kp küresel jeomanyetik bozulma düzeyini kodlar; kare bağımlılık
        Toplam Elektron İçeriği (TEC) düzensizliklerinin doğrusal olmayan
        büyümesini yansıtır (Secan 1997) [5].
        Kp = NaN (OMNI verisi yok) → Kp = 0 (muhafazakar).
        Birim: W (Kp birimsiz)

    d · flux_pfu
        Yüksek enerjili proton akısı (GOES > 55 MeV) D-katmanında
        Kutup Şapkası Soğurması'na (PCA) yol açar; HF/UHF sinyalleri
        10–20 dB zayıflayabilir (Xapsos 2000) [6].
        Birim: W/pfu

    Katsayı kalibrasyonu
    --------------------
    G3–G5 jeomanyetik fırtınaların (|Bz|≈30–50 nT, Kp=8–9,
    flux≈100 pfu) SNR'yi 0 dB altına taşıdığı durumlar hedeflenmiştir
    (veri kaybı > %50).

    Parametreler
    ------------
    bz_nt     : np.ndarray  — Bz GSM bileşeni [nT]
    speed_kmps: np.ndarray  — güneş rüzgarı hızı [km/s]
    dens_cm3  : np.ndarray  — proton yoğunluğu [cm⁻³]
    kp        : np.ndarray  — Kp indeksi [0–9]; NaN → 0 varsayılır
    flux_pfu  : np.ndarray  — proton akısı [pfu]

    Döndürür
    --------
    np.ndarray  —  N_sw [W], ≥ 0
    """
    lb = CFG.link

    # NaN Kp: OMNI verisi mevcut değil → 0 al (gürültüyü olduğundan az tahmin etme)
    kp_safe = np.where(np.isfinite(kp), kp, 0.0)

    n_bz   = lb.SW_A * np.abs(bz_nt)                        # IMF yeniden bağlantı
    n_vn   = lb.SW_B * (np.abs(speed_kmps) * np.abs(dens_cm3))  # güneş rüzgarı akısı
    n_kp   = lb.SW_C * (kp_safe ** 2)                       # Kp doğrusal olmayan terimi
    n_flux = lb.SW_D * np.abs(flux_pfu)                     # PCA proton soğurması

    return n_bz + n_vn + n_kp + n_flux


# ─────────────────────────────────────────────────────────────────
# 5.  SNR HESAPLAMA  —  tam bağlantı bütçesiyle
# ─────────────────────────────────────────────────────────────────

def compute_snr_physics(pr_w: float,
                        n_th_w: float,
                        n_sw_w: np.ndarray,
                        ) -> tuple:
    """
    Tam bağlantı bütçesiyle SNR:

        P_noise_total = N_th + N_sw
        SNR_linear    = P_r / P_noise_total
        SNR_dB        = 10 · log10(SNR_linear)

    Parametreler
    ------------
    pr_w   : float       — alınan sinyal gücü [W]
    n_th_w : float       — sistem termal gürültüsü [W]
    n_sw_w : np.ndarray  — uzay havası gürültüsü [W]

    Döndürür
    --------
    (snr_linear, snr_dB)  —  her ikisi de np.ndarray
    """
    n_total = n_th_w + n_sw_w
    snr_lin = pr_w / np.maximum(n_total, 1e-40)
    snr_dB  = 10.0 * np.log10(np.maximum(snr_lin, 1e-20))
    return snr_lin, snr_dB


# ─────────────────────────────────────────────────────────────────
# 6.  VERİ KAYBI MODELİ  —  sigmoid (lojistik) fonksiyon
# ─────────────────────────────────────────────────────────────────

def data_loss_pct(snr_db: np.ndarray) -> np.ndarray:
    """
    SNR'den veri kaybı yüzdesi tahmini — sigmoid (B-seçeneği):

        Loss(%) = 100 / (1 + exp(SNR_dB))

    Fiziksel gerekçe
    ----------------
    • Sınırlı: Loss ∈ (0 %, 100 %)
    • SNR ile monoton azalır.
    • Sigmoid şekli, FEC-kodlu dijital bağlantılarda gözlemlenen
      paket hata oranı (PER) vs. SNR eğrisini yansıtır.
    • Dönüm noktası SNR = 0 dB'de (sinyal ≡ gürültü): Loss = 50 %.
      0 dB SNR altında çoğu modülasyon şeması artık veri kurtaramaz.

    A-seçeneği (Loss ≈ exp(−SNR_linear)) KULLANILMAZ:
      pratik SNR değerlerinde (lineer >> 1) sıfıra yaklaşır ve
      anlamlı bir duyarlılık göstermez; ayrıca üst sınırı yoktur.

    Parametreler
    ------------
    snr_db : np.ndarray  — SNR değerleri [dB]

    Döndürür
    --------
    np.ndarray  —  veri kaybı [%]
    """
    # exp() taşmasını önlemek için kırp (np.exp ±709'da güvenli çalışır)
    x = np.clip(snr_db, -500.0, 500.0)
    return 100.0 / (1.0 + np.exp(x))


# ─────────────────────────────────────────────────────────────────
# 7.  DAHILI FIRTINA BAYRAGI
# ─────────────────────────────────────────────────────────────────

def _storm_flag(bz: np.ndarray,
                kp: np.ndarray,
                pdyn: Optional[np.ndarray]) -> np.ndarray:
    """
    Çift yollu fırtına tespiti (Ippolito 2017 + Newell 2008).

    Yol A — gerçek Kp (OMNI veritabanı):  Bz < 0 VE Kp > 5
    Yol B — RTSW yerel (Kp NaN):           Bz < STORM_BZ_THRESH
                                        VE Pdyn > STORM_PDYN_THRESH
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
# 8.  TAM DATAFRAME PIPELINE
# ─────────────────────────────────────────────────────────────────

def run_physics_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    """
    Birleştirilmiş uzay havası DataFrame'ine fizik modelini uygular.

    Gerekli giriş sütunları : Bz, Dens, Speed, Temp, Kp, flux
    Opsiyonel               : Pdyn

    Çıktıya eklenen sütunlar (visualizer.py uyumlu):
        N_thermal    — sistem termal gürültüsü [W]  (Nyquist 1928)
        N_scint      — N_sw [W]  (görselleştirici uyumluluğu için eşlendi)
        N_rad        — 0.0  (proton soğurması N_sw d·flux terimine dahil)
        N_total      — N_thermal + N_sw  [W]
        SNR_lin      — lineer SNR
        SNR_dB       — SNR [dB]
        storm_flag   — bool maskesi (Ippolito 2017 / Newell 2008)
        data_loss_pct— tahmini veri kaybı [%]
    """
    out = df.copy()

    # ── Sabit bağlantı bütçesi değerleri ─────────────────────────
    pr_w = received_power_W()          # alınan güç [W]
    n_th = system_thermal_noise()      # sistem termal gürültüsü [W]

    # ── Vektör girdileri ─────────────────────────────────────────
    bz    = out["Bz"].fillna(0.0).values
    speed = out["Speed"].fillna(400.0).values
    dens  = out["Dens"].fillna(5.0).values
    kp    = out["Kp"].values                      # NaN = veri yok
    flux  = out["flux"].fillna(0.0).values
    pdyn  = out["Pdyn"].values if "Pdyn" in out.columns else None

    # ── Uzay havası gürültüsü ve SNR ─────────────────────────────
    n_sw             = space_weather_noise(bz, speed, dens, kp, flux)
    n_tot            = n_th + n_sw
    snr_lin, snr_dB  = compute_snr_physics(pr_w, n_th, n_sw)
    loss             = data_loss_pct(snr_dB)
    flags            = _storm_flag(bz, kp, pdyn)

    # ── DataFrame sütunları ───────────────────────────────────────
    out["N_thermal"]     = n_th        # skaler → yayınlanır
    out["N_scint"]       = n_sw        # N_sw → görselleştirici N_scint sütunuyla uyumlu
    out["N_rad"]         = 0.0         # proton soğurması d·flux teriminde; artık ayrı 0
    out["N_total"]       = n_tot
    out["SNR_lin"]       = snr_lin
    out["SNR_dB"]        = snr_dB
    out["storm_flag"]    = flags
    out["data_loss_pct"] = loss

    # ── Tanı günlükleri ──────────────────────────────────────────
    l_fs = fspl_db(CFG.link.DISTANCE_KM, CFG.link.FREQ_MHZ)
    log.info(f"[PHYSICS]  FSPL       = {l_fs:.2f} dB  "
             f"(d={CFG.link.DISTANCE_KM:.0f} km, f={CFG.link.FREQ_MHZ:.0f} MHz)")
    log.info(f"[PHYSICS]  Pr         = {pr_w:.4e} W  "
             f"({10.0*np.log10(pr_w):.1f} dBW)")
    log.info(f"[PHYSICS]  N_thermal  = {n_th:.4e} W  "
             f"(T_sys = {CFG.link.T_SYS_K:.0f} K)")
    log.info(f"[PHYSICS]  SNR ortalama = {snr_dB.mean():.2f} dB")
    log.info(f"[PHYSICS]  SNR min      = {snr_dB.min():.2f} dB")
    log.info(f"[PHYSICS]  SNR maks     = {snr_dB.max():.2f} dB")
    log.info(f"[PHYSICS]  Veri kaybı ort. = {loss.mean():.3f} %")
    log.info(f"[PHYSICS]  Veri kaybı maks = {loss.max():.3f} %")
    log.info(f"[PHYSICS]  Fırtına süresi  = {int(flags.sum())} dakika")

    return out


# ─────────────────────────────────────────────────────────────────
# 9.  GERÇEK ZAMANLI TAHMİN FONKSİYONU
# ─────────────────────────────────────────────────────────────────

def predict_realtime(bz: float,
                     speed: float,
                     density: float,
                     kp: float = float("nan"),
                     flux: float = 0.0) -> dict:
    """
    Anlık uzay havası ölçümlerinden SNR ve veri kaybı tahmini.

    Parametreler
    ------------
    bz      : float  — Bz bileşeni [nT GSM]
    speed   : float  — güneş rüzgarı hızı [km/s]
    density : float  — proton yoğunluğu [cm⁻³]
    kp      : float  — Kp indeksi [0–9]; bilinmiyorsa float('nan')
    flux    : float  — GOES proton akısı [pfu]; varsayılan 0.0

    Döndürür
    --------
    dict:
        snr_dB        — alıcıdaki SNR [dB]
        data_loss_pct — tahmini veri kaybı [%]
        storm_risk    — niteleyici etiket: 'none'|'low'|'moderate'|'high'|'severe'
        N_space_W     — toplam uzay havası gürültüsü [W]
        N_thermal_W   — termal gürültü tabanı [W]
        Pr_W          — alınan sinyal gücü [W]
        fspl_dB       — serbest uzay yol kaybı [dB]

    Örnek
    ------
    >>> predict_realtime(bz=-20, speed=650, density=15, kp=7.0)
    {'snr_dB': -1.8, 'data_loss_pct': 85.8, 'storm_risk': 'high', ...}
    """
    pr_w  = received_power_W()
    n_th  = system_thermal_noise()
    l_fs  = fspl_db(CFG.link.DISTANCE_KM, CFG.link.FREQ_MHZ)

    bz_arr    = np.array([bz])
    speed_arr = np.array([speed])
    dens_arr  = np.array([density])
    kp_arr    = np.array([kp])
    flux_arr  = np.array([flux])

    n_sw         = space_weather_noise(bz_arr, speed_arr, dens_arr, kp_arr, flux_arr)
    _, snr_arr   = compute_snr_physics(pr_w, n_th, n_sw)
    loss_arr     = data_loss_pct(snr_arr)

    snr_val  = float(snr_arr[0])
    loss_val = float(loss_arr[0])

    # Risk kademelendirme — SNR eşiklerine göre
    if   snr_val >= 15.0:  risk = "none"
    elif snr_val >=  8.0:  risk = "low"
    elif snr_val >=  2.0:  risk = "moderate"
    elif snr_val >= -5.0:  risk = "high"
    else:                  risk = "severe"

    return {
        "snr_dB":        round(snr_val, 2),
        "data_loss_pct": round(loss_val, 3),
        "storm_risk":    risk,
        "N_space_W":     float(n_sw[0]),
        "N_thermal_W":   n_th,
        "Pr_W":          pr_w,
        "fspl_dB":       round(l_fs, 2),
    }


# ─────────────────────────────────────────────────────────────────
# ENTRY POINT  —  standalone demo / sanity check
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    DIV  = "═" * 62
    DIV2 = "─" * 62

    # ── 1. Link budget summary ────────────────────────────────────
    lb   = CFG.link
    l_fs = fspl_db(lb.DISTANCE_KM, lb.FREQ_MHZ)
    pr_w = received_power_W()
    n_th = system_thermal_noise()

    print(f"\n{DIV}")
    print("  RF LINK BUDGET  —  physics_model.py")
    print(DIV)
    print(f"  Scenario   : GEO satellite, Ku-band downlink")
    print(f"  Distance   : {lb.DISTANCE_KM:,.0f} km")
    print(f"  Frequency  : {lb.FREQ_MHZ:,.0f} MHz  ({lb.FREQ_MHZ/1e3:.1f} GHz)")
    print(f"  Tx Power   : {lb.PT_DBW:.1f} dBW  "
          f"({10**(lb.PT_DBW/10):.0f} W)")
    print(f"  Tx Gain    : {lb.GT_DBI:.1f} dBi")
    print(f"  Rx Gain    : {lb.GR_DBI:.1f} dBi")
    print(f"  T_sys      : {lb.T_SYS_K:.0f} K  (cooled LNA)")
    print(DIV2)
    print(f"  FSPL       : {l_fs:.2f} dB")
    print(f"  Pr         : {pr_w:.4e} W  ({10*np.log10(pr_w):.2f} dBW)")
    print(f"  N_thermal  : {n_th:.4e} W  (Johnson–Nyquist 1928)")
    print(f"  Bandwidth  : {CFG.phys.BANDWIDTH_HZ/1e6:.1f} MHz")
    print(DIV)

    # ── 2. Space weather scenarios ────────────────────────────────
    scenarios = [
        # label,        bz,    speed, dens, kp,    flux
        ("Quiet Sun",   0.0,   380,   4,    1.0,   0.0),
        ("Mild",       -5.0,   450,   8,    float("nan"), 0.0),
        ("G1 Storm",   -10.0,  500,   15,   5.0,   0.5),
        ("G2 Storm",   -20.0,  600,   20,   6.5,   2.0),
        ("G3 Storm",   -30.0,  680,   25,   7.5,   10.0),
        ("G4 Storm",   -40.0,  750,   35,   8.5,   50.0),
        ("G5 Storm",   -50.0,  850,   50,   9.0,   200.0),
    ]

    print(f"\n  {'Scenario':<16}  {'Bz':>6}  {'v':>5}  {'n':>5}  "
          f"{'Kp':>5}  {'SNR':>8}  {'Loss':>8}  {'Risk'}")
    print(f"  {'':─<16}  {'[nT]':>6}  {'km/s':>5}  {'cm⁻³':>5}  "
          f"{'':>5}  {'[dB]':>8}  {'[%]':>8}  ")
    print(f"  {DIV2}")

    for label, bz, speed, dens, kp, flux in scenarios:
        r = predict_realtime(bz=bz, speed=speed, density=dens,
                             kp=kp, flux=flux)
        kp_str = f"{kp:.1f}" if np.isfinite(kp) else " N/A"
        print(f"  {label:<16}  {bz:>+6.1f}  {speed:>5.0f}  {dens:>5.1f}  "
              f"{kp_str:>5}  {r['snr_dB']:>+8.2f}  "
              f"{r['data_loss_pct']:>7.3f}%  {r['storm_risk']}")

    print(f"\n  {DIV2}")
    print("  Data loss formula:  Loss(%) = 100 / (1 + exp(SNR_dB))")
    print("  Inflection at SNR = 0 dB  →  Loss = 50 %")
    print(f"{DIV}\n")

    # ── 3. Single real-time call  (usage example) ─────────────────
    print("  predict_realtime() — single call example:")
    print(DIV2)
    sample = predict_realtime(bz=-20.0, speed=650, density=15,
                              kp=7.0, flux=5.0)
    print(f"  SNR         : {sample['snr_dB']:+.2f} dB")
    print(f"  Data Loss   : {sample['data_loss_pct']:.3f} %")
    print(f"  Storm Risk  : {sample['storm_risk']}")
    print(f"  N_space     : {sample['N_space_W']:.4e} W")
    print(f"  N_thermal   : {sample['N_thermal_W']:.4e} W")
    print(f"  Pr (signal) : {sample['Pr_W']:.4e} W")
    print(f"  FSPL        : {sample['fspl_dB']:.2f} dB")
    print(f"{DIV}\n")

    sys.exit(0)
