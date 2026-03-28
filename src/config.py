"""
config.py  —  Proje genelinde sabitler ve yol tanımları
================================================================
Tüm fiziksel sabitler, dosya yolları ve model parametreleri
bu dosyada merkezileştirilmiştir.  Herhangi bir modülde
  from config import CFG
şeklinde içe aktarabilirsiniz.
"""

from pathlib import Path

# ── Proje kök dizini (bu dosyaya göre) ──────────────────────────
ROOT = Path(__file__).resolve().parent.parent

# ── Dizin yapısı ─────────────────────────────────────────────────
class Paths:
    raw       = ROOT / "data" / "raw"
    processed = ROOT / "data" / "processed"
    outputs   = ROOT / "outputs"

    omni_file  = raw / "OMNIWeb_Results.json"
    rtsw_file  = raw / "rtsw_plot_data_2026-03-27T12_00_00.json"
    goes_file  = raw / "goes_2026-03-27.json"

# ── Fiziksel sabitler ─────────────────────────────────────────────
class Physics:
    kB            = 1.38064852e-23   # Boltzmann sabiti  [J/K]
    BANDWIDTH_HZ  = 10e6             # Sistem band genişliği  [Hz]  — 10 MHz
    SIGNAL_POWER  = 1e-12            # Nominal sinyal gücü  [W]  — -90 dBm
    SCINT_ALPHA   = 1e-18            # Rickett (1977) ölçekleme faktörü
                                     # 1e-30 → 1e-18: speed km/s biriminde
                                     # N_scint ≈ %10 N_thermal (tipik güneş rüzgarı)
    STORM_COEFF   = 2.5              # Ippolito (2017) fırtına katsayısı (log ölçek)
    PROTON_THRESH = 1e-6             # Xapsos (2000) spike eşiği  [pfu]
                                     # 1e-4 → 1e-6: GOES A5/A6 gözlenen aralığına göre

    # ── RTSW-yerel fırtına kriteri (OMNI Kp mevcut değilse) ──
    # Kaynak: Newell et al. (2008) JGR — sürekli iletim fonksiyonu
    # Kp≥5 koşuluna yaklaşık olarak karşılık gelir.
    STORM_BZ_THRESH   = -3.5        # Güney IMF eşiği [nT]
    STORM_PDYN_THRESH =  0.5        # Dinamik basınç eşiği [nPa]
    OMNI_TOLERANCE    = "2h"        # merge_asof zaman toleransı

# ── RF Link Budget — GEO / Ku-band uy. senaryosu ────────────────
class LinkBudget:
    """
    Uydu haberleşme bağlantı bütçesi parametreleri.

    Senaryo: Geostationary (GEO) uydu, Ku-band (12 GHz) aşağı bağlantı.
    Referans: Ippolito, L.J. (2017) "Satellite Communications Systems
              Engineering." Wiley-IEEE Press, 3rd Ed., Bölüm 4.

    FSPL hesabı :  L_fs[dB] = 20·log10(d_km) + 20·log10(f_MHz) + 32.44
    Bağlantı bütçesi: Pr[dBW] = Pt + Gt + Gr − L_fs  →  Pr ≈ 9.8×10⁻¹¹ W
    """
    DISTANCE_KM  = 35_786.0   # GEO yörünge mesafesi [km]
    FREQ_MHZ     = 12_000.0   # Ku-band taşıyıcı frekans [MHz]
    PT_DBW       =    20.0    # Vericinin gücü [dBW]  — 100 W
    GT_DBI       =    33.0    # Verici anten kazancı [dBi] — spot ışın
    GR_DBI       =    52.0    # Alıcı anten kazancı [dBi] — 3 m çanak
    T_SYS_K      =   100.0    # Sistem gürültü sıcaklığı [K] — LNA soğutmalı

    # ── Uzay havası gürültü katsayıları (N_sw = a·|Bz| + b·v·n + c·Kp² + d·flux)
    # Kalibre: G3–G5 fırtınaları SNR'yi 0 dB altına iter (>%50 veri kaybı)
    SW_A = 5.0e-12   # W/nT          — IMF Bz yeniden bağlantı terimi
    SW_B = 2.0e-15   # W·s·cm³·km⁻¹ — Güneş rüzgarı akı terimi (n·v)
    SW_C = 8.0e-13   # W             — Jeomanyetik Kp² terimi (doğrusal olmayan)
    SW_D = 3.0e-12   # W/pfu         — Yeniden bağlantı proton flux terimi

# ── Veri temizleme eşikleri ───────────────────────────────────────
class FillValues:
    OMNI_LARGE   = 99900.0           # 999xx  →  NaN
    OMNI_BIG_INT = 9999              # 9999   →  NaN  (Kp, flux)
    RTSW_FLAG    = -99999.0          # -99999 →  NaN

# ── Çizim renkleri ───────────────────────────────────────────────
class Colors:
    THERMAL  = "#00d4ff"
    SCINT    = "#ff9f1c"
    RAD      = "#ff3366"
    SNR      = "#4fff91"
    STORM    = "#ff3366"
    KP       = "#b388ff"
    BZ       = "#ffd166"
    BG       = "#0a0e1a"
    AX_BG    = "#0d1220"

# ── Birleşik konfigürasyon nesnesi ───────────────────────────────
class CFG:
    paths  = Paths
    phys   = Physics
    fill   = FillValues
    colors = Colors
    link   = LinkBudget