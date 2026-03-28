"""
main.py  —  Uzay Havası SNR Simülatörü — Ana Giriş Noktası
================================================================
Kullanım:
    python3 main.py
    python3 main.py --csv
    python3 main.py --rtsw data/raw/rtsw_2026-03-27.json
    python3 main.py --omni data/raw/OMNIWeb_Results.json
    python3 main.py --help
"""

import argparse
import logging
import sys
import os
from pathlib import Path

# ── Proje kök dizinini bul ve src/ klasörünü yola ekle ────────
ROOT = Path(__file__).resolve().parent
SRC  = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)   # çalışma dizinini her zaman proje köküne al

from sw_config import CFG
from data_loader import load_omni, load_rtsw, load_goes, merge_all
from noise_models import run_noise_pipeline
from visualizer import plot_results

# ── Loglama kurulumu ──────────────────────────────────────────
CFG.paths.outputs.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(CFG.paths.outputs / "simulation.log",
                            mode="w", encoding="utf-8"),
    ]
)
log = logging.getLogger(__name__)


def parse_args():
    p = argparse.ArgumentParser(
        description="Uzay Havası Kaynaklı Sinyal Bozulma Simülatörü"
    )
    p.add_argument("--omni", type=Path,
                   default=CFG.paths.raw / "OMNIWeb_Results.json",
                   help="OMNI JSON veri dosyası")
    p.add_argument("--rtsw", type=Path,
                   default=None,
                   help="RTSW JSON veri dosyası (belirtilmezse otomatik bulunur)")
    p.add_argument("--goes", type=Path,
                   default=None,
                   help="GOES proton flux JSON dosyası (opsiyonel)")
    p.add_argument("--out",  type=Path, default=None,
                   help="Grafik çıktı yolu (.png)")
    p.add_argument("--csv",  action="store_true",
                   help="Sonuçları CSV olarak da kaydet")
    return p.parse_args()


def main():
    args = parse_args()

    log.info("=" * 60)
    log.info("  UZAY HAVASI SNR SİMÜLATÖRÜ BAŞLATILIYOR")
    log.info("=" * 60)

    # ── 1. Veri Yükleme ──────────────────────────────────────
    log.info("▶ Veri yükleniyor...")
    df_omni = load_omni(args.omni)
    df_rtsw = load_rtsw(args.rtsw)
    df_goes = load_goes(args.goes)

    # ── 2. Birleştirme ───────────────────────────────────────
    log.info("▶ Veri birleştiriliyor...")
    df_merged = merge_all(df_rtsw, df_omni, df_goes)

    # ── 3. Gürültü Modeli ────────────────────────────────────
    log.info("▶ Fiziksel gürültü modelleri çalıştırılıyor...")
    df_result = run_noise_pipeline(df_merged)

    # ── 4. Özet ──────────────────────────────────────────────
    log.info("-" * 55)
    log.info(f"  Ortalama SNR  : {df_result['SNR_dB'].mean():.2f} dB")
    log.info(f"  Min SNR       : {df_result['SNR_dB'].min():.2f} dB")
    log.info(f"  Max SNR       : {df_result['SNR_dB'].max():.2f} dB")
    log.info(f"  Fırtına süresi: {df_result['storm_flag'].sum()} dakika")
    log.info("-" * 55)

    # ── 5. Görselleştirme ────────────────────────────────────
    log.info("▶ Grafik oluşturuluyor...")
    plot_path = plot_results(df_result, out_path=args.out)
    log.info(f"  Grafik → {plot_path}")

    # ── 6. Opsiyonel CSV ─────────────────────────────────────
    if args.csv:
        csv_path = CFG.paths.outputs / "snr_results.csv"
        df_result.to_csv(csv_path)
        log.info(f"  CSV   → {csv_path}")

    log.info("✓ Simülasyon tamamlandı.")
    return df_result


if __name__ == "__main__":
    main()