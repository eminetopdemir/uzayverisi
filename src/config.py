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
    SCINT_ALPHA   = 1e-30            # Rickett (1977) ölçekleme faktörü
    STORM_COEFF   = 2.5              # Ippolito (2017) fırtına katsayısı (log ölçek)
    PROTON_THRESH = 1e-4             # Xapsos (2000) spike eşiği  [pfu]

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