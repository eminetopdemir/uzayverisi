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

from config import CFG
from data_loader import load_omni, load_rtsw, load_goes, merge_all
from noise_models import run_noise_pipeline
from physics_model import predict_realtime
from visualizer import plot_results
from ml_model import train as ml_train, predict_dataframe, snr_to_data_loss

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
    p.add_argument("--ml",   action="store_true",
                   help="ML modeli eğit ve SNR tahmin et")
    p.add_argument("--model-type", choices=["ridge", "gb"], default="ridge",
                   help="ML regresör tipi: ridge (varsayılan) | gb (GradientBoosting)")
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
    snr   = df_result["SNR_dB"]
    loss  = df_result["data_loss_pct"]
    storm = int(df_result["storm_flag"].sum())
    lb    = CFG.link

    from physics_model import fspl_db, received_power_W, system_thermal_noise
    l_fs = fspl_db(lb.DISTANCE_KM, lb.FREQ_MHZ)
    pr_w = received_power_W()
    n_th = system_thermal_noise()

    DIV  = "═" * 62
    DIV2 = "─" * 62

    log.info(DIV)
    log.info("  RF LINK BUDGET")
    log.info(DIV2)
    log.info("  %-22s  %s", "Scenario",
             "GEO satellite · Ku-band downlink")
    log.info("  %-22s  %s km",        "Distance",  f"{lb.DISTANCE_KM:,.0f}")
    log.info("  %-22s  %s MHz  (%.1f GHz)",
             "Frequency", f"{lb.FREQ_MHZ:,.0f}", lb.FREQ_MHZ / 1e3)
    log.info("  %-22s  %.1f dBW  (%g W)",
             "Tx Power", lb.PT_DBW, 10 ** (lb.PT_DBW / 10))
    log.info("  %-22s  %.1f dBi", "Tx Gain", lb.GT_DBI)
    log.info("  %-22s  %.1f dBi", "Rx Gain", lb.GR_DBI)
    log.info("  %-22s  %.0f K  (cooled LNA)", "T_sys", lb.T_SYS_K)
    log.info(DIV2)
    log.info("  %-22s  %.2f dB", "FSPL", l_fs)
    log.info("  %-22s  %.4e W  (%.2f dBW)",
             "Pr (received)", pr_w, 10 * __import__("math").log10(pr_w))
    log.info("  %-22s  %.4e W  (Johnson–Nyquist 1928)",
             "N_thermal", n_th)
    log.info(DIV)
    log.info("  SIMULATION RESULTS  —  %d samples  (%s → %s)",
             len(df_result),
             df_result.index[0].strftime("%Y-%m-%d %H:%M"),
             df_result.index[-1].strftime("%Y-%m-%d %H:%M"))
    log.info(DIV2)
    log.info("  %-22s  %+.2f dB", "Average SNR", snr.mean())
    log.info("  %-22s  %+.2f dB", "Min SNR",     snr.min())
    log.info("  %-22s  %+.2f dB", "Max SNR",     snr.max())
    log.info("  %-22s  %.4f %%",  "Avg data loss", loss.mean())
    log.info("  %-22s  %.4f %%",  "Max data loss", loss.max())
    log.info("  %-22s  %d min",   "Storm duration", storm)
    log.info(DIV)

    # ── Gerçek zamanlı tahmin demosu ─────────────────────────────
    log.info("  REAL-TIME DEMO  —  predict_realtime()")
    log.info(DIV2)
    log.info("  %-16s  %6s  %5s  %5s  %5s  %8s  %8s  %s",
             "Scenario", "Bz", "v", "n", "Kp",
             "SNR", "Loss", "Risk")
    log.info("  %-16s  %6s  %5s  %5s  %5s  %8s  %8s",
             "", "[nT]", "km/s", "cm⁻³", "", "[dB]", "[%]")
    log.info("  " + DIV2)
    scenarios = [
        ("Quiet Sun",  0.0,   380,  4,  1.0,          0.0),
        ("Mild",      -5.0,   450,  8,  float("nan"), 0.0),
        ("G1 Storm",  -10.0,  500, 15,  5.0,          0.5),
        ("G2 Storm",  -20.0,  600, 20,  6.5,          2.0),
        ("G3 Storm",  -30.0,  680, 25,  7.5,         10.0),
        ("G4 Storm",  -40.0,  750, 35,  8.5,         50.0),
        ("G5 Storm",  -50.0,  850, 50,  9.0,        200.0),
    ]
    import math
    for label, bz, speed, dens, kp, flux in scenarios:
        r = predict_realtime(bz=bz, speed=speed, density=dens,
                             kp=kp, flux=flux)
        kp_str = f"{kp:.1f}" if math.isfinite(kp) else " N/A"
        log.info("  %-16s  %+6.1f  %5.0f  %5.1f  %5s  %+8.2f  %7.3f%%  %s",
                 label, bz, speed, dens, kp_str,
                 r["snr_dB"], r["data_loss_pct"], r["storm_risk"])
    log.info(DIV2)
    log.info("  Loss(X) = 100 / (1 + exp(SNR_dB))   "
             "-- inflection at SNR = 0 dB  ->  Loss = 50 X"
             .replace("X", "%"))
    log.info(DIV)

    # ── 5. Görselleştirme ────────────────────────────────────
    log.info("▶ Grafik oluşturuluyor...")
    plot_path = plot_results(df_result, out_path=args.out)
    log.info(f"  Grafik → {plot_path}")

    # ── 6. Opsiyonel CSV ─────────────────────────────────────
    if args.csv:
        csv_path = CFG.paths.outputs / "snr_results.csv"
        df_result.to_csv(csv_path)
        log.info(f"  CSV   → {csv_path}")
    # ── 7. ML Modeli (opsiyonel) ──────────────────────────────────
    if args.ml:
        log.info("► ML modeli eğitiliyor...")
        ml_result = ml_train(
            df_result,
            model_type=args.model_type,
        )
        metrics = ml_result["metrics"]
        log.info("-" * 55)
        log.info("  [ML] Eğitim R²       : %.4f", metrics["r2_train"])
        log.info("  [ML] Test R²         : %.4f", metrics["r2_test"])
        log.info("  [ML] Test MAE        : %.4f dB", metrics["mae_test_dB"])
        log.info("  [ML] CV R²           : %.4f ± %.4f",
                 metrics["cv_r2_mean"], metrics["cv_r2_std"])
        log.info("-" * 55)

        log.info("► Tahmin hesaplanıyor...")
        df_ml = predict_dataframe(df_result)

        log.info("► SNR → Veri kaybı örnek noktaları:")
        for snr_val in [-17, -12, -8, -5, -3, 0, 5]:
            loss = snr_to_data_loss(float(snr_val))
            log.info("       SNR = %+5.0f dB  →  Veri kaybı = %.1f %%", snr_val, loss)

        if args.csv:
            ml_csv = CFG.paths.outputs / "ml_results.csv"
            df_ml.to_csv(ml_csv)
            log.info("  ML CSV → %s", ml_csv)

        df_result = df_ml
    log.info("✓ Simülasyon tamamlandı.")
    return df_result


if __name__ == "__main__":
    main()