"""
visualizer.py  —  Görselleştirme Modülü
================================================================
Simülasyon sonuçlarını 6 panelli profesyonel bir Matplotlib
grafiğinde gösterir.  Karanlık uzay teması.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.dates as mdates
from pathlib import Path
from typing import Optional, Union
import pandas as pd
import logging

from config import CFG

log = logging.getLogger(__name__)

# ── Küresel stil ─────────────────────────────────────────────────
plt.rcParams.update({
    "figure.facecolor":  CFG.colors.BG,
    "axes.facecolor":    CFG.colors.AX_BG,
    "axes.edgecolor":    "#1e2d4a",
    "axes.labelcolor":   "#8ba8cc",
    "xtick.color":       "#4a6280",
    "ytick.color":       "#4a6280",
    "text.color":        "#c8d8ea",
    "grid.color":        "#1a2538",
    "grid.linewidth":    0.6,
    "font.family":       "monospace",
})

_C = CFG.colors


def _fmt_axis(ax, title: str, ylabel: str):
    ax.set_title(title, color="#e8f4fd", fontsize=9, pad=5, fontweight="bold")
    ax.set_ylabel(ylabel, fontsize=8)
    ax.grid(True, alpha=0.4)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=20, ha="right", fontsize=7)


def plot_results(df: pd.DataFrame,
                 out_path: Union[Path, str, None] = None) -> Path:
    """
    6 panelli SNR/Gürültü grafiği oluştur ve kaydet.

    Parametreler
    ------------
    df       : run_noise_pipeline() çıktısı
    out_path : kayıt yolu; None ise outputs/ klasörüne yazar.

    Döndürür
    --------
    Path  —  kaydedilen dosyanın yolu
    """
    if out_path is None:
        out_path = CFG.paths.outputs / "uzayveri.png"
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    t = df.index

    fig = plt.figure(figsize=(17, 14))
    fig.patch.set_facecolor(_C.BG)

    gs = gridspec.GridSpec(
        4, 2, figure=fig,
        hspace=0.60, wspace=0.38,
        left=0.08, right=0.97, top=0.91, bottom=0.07
    )

    # ══ P1: SNR (tam genişlik) ═════════════════════════════════
    ax1 = fig.add_subplot(gs[0, :])
    ax1.fill_between(t, df["SNR_dB"], alpha=0.15, color=_C.SNR)
    ax1.plot(t, df["SNR_dB"], color=_C.SNR, lw=1.6, label="SNR (dB)")

    if df["storm_flag"].any():
        ylo = df["SNR_dB"].min() - 2
        yhi = df["SNR_dB"].max() + 2
        ax1.fill_between(t, ylo, yhi,
                         where=df["storm_flag"].values,
                         alpha=0.15, color=_C.STORM,
                         label=f"Fırtına  (Bz<0 & Kp>5)")

    ax1.axhline(0, color="#ff3366", lw=0.8, ls="--", alpha=0.55)
    ax1.annotate("SNR = 0 dB  (eşit sinyal-gürültü)",
                 xy=(t[len(t)//2], 0.5), color="#ff7799",
                 fontsize=7, ha="center")
    ax1.legend(fontsize=7, loc="upper right", framealpha=0.2)
    _fmt_axis(ax1,
              "Toplam SNR  ·  Ippolito (2017) Storm Scaling",
              "SNR [dB]")

    # ══ P2: Gürültü Bileşenleri  (log ölçek) ══════════════════
    ax2 = fig.add_subplot(gs[1, :])
    ax2.semilogy(t, df["N_thermal"],        color=_C.THERMAL, lw=1.4,
                 label="N_thermal  (Nyquist 1928)")
    ax2.semilogy(t, df["N_scint"],          color=_C.SCINT,   lw=1.4,
                 label="N_sw = a·|Bz|+b·vn+c·Kp²+d·flux  (Dungey/Parker)")
    ax2.semilogy(t, df["N_rad"] + 1e-30,   color=_C.RAD,     lw=1.4,
                 label="N_rad → N_sw·d·flux'a dahil", alpha=0.9)
    ax2.semilogy(t, df["N_total"],          color="white",    lw=2.0,
                 ls="--", alpha=0.8, label="N_total = N_th + N_sw")
    ax2.legend(fontsize=7, loc="upper right", framealpha=0.2, ncol=2)
    _fmt_axis(ax2, "Gürültü Bileşenleri [W]  (logaritmik)  ·  Fizik Modeli", "Güç [W]")

    # ══ P3: Plazma Sıcaklığı ═══════════════════════════════════
    ax3 = fig.add_subplot(gs[2, 0])
    ax3.plot(t, df["Temp"] / 1e3, color=_C.THERMAL, lw=1.2)
    ax3.fill_between(t, df["Temp"] / 1e3, alpha=0.10, color=_C.THERMAL)
    _fmt_axis(ax3,
              "Plazma Sıcaklığı [kK]  →  N_thermal",
              "T [kK]")

    # ══ P4: ρ·v²  (Rickett girdisi) ════════════════════════════
    ax4 = fig.add_subplot(gs[2, 1])
    proxy = (df["Dens"] * df["Speed"] ** 2) / 1e6
    ax4.plot(t, proxy, color=_C.SCINT, lw=1.2)
    ax4.fill_between(t, proxy, alpha=0.10, color=_C.SCINT)
    _fmt_axis(ax4,
              "ρ·v²  [×10⁶ cm⁻³·(km/s)²]  →  N_sw b·(v·n) terimi",
              "ρv² proxy")

    # ══ P5: Proton Flux ════════════════════════════════════════
    ax5 = fig.add_subplot(gs[3, 0])
    ax5.semilogy(t, df["flux"] + 1e-12, color=_C.RAD, lw=1.3)
    ax5.axhline(CFG.phys.PROTON_THRESH,
                color="white", lw=0.8, ls="--", alpha=0.6,
                label=f"Eşik = {CFG.phys.PROTON_THRESH:.0e}")
    ax5.fill_between(t, 1e-12, df["flux"] + 1e-12,
                     where=(df["flux"] > CFG.phys.PROTON_THRESH).values,
                     alpha=0.25, color=_C.RAD, label="Spike bölgesi")
    ax5.legend(fontsize=6, framealpha=0.2)
    _fmt_axis(ax5,
              "GOES Proton Flux  →  N_rad  (Xapsos 2000)",
              "Flux [pfu]")

    # ══ P6: Kp & Bz ════════════════════════════════════════════
    ax6      = fig.add_subplot(gs[3, 1])
    ax6_twin = ax6.twinx()

    ax6.plot(t, df["Kp"], color=_C.KP, lw=1.4, label="Kp indeksi")
    ax6.axhline(5, color=_C.KP, lw=0.7, ls="--", alpha=0.5)

    ax6_twin.plot(t, df["Bz"], color=_C.BZ, lw=1.1,
                  ls=":", label="Bz [nT]")
    ax6_twin.axhline(0, color=_C.BZ, lw=0.6, ls="--", alpha=0.5)

    ax6.set_ylabel("Kp", fontsize=8, color=_C.KP)
    ax6_twin.set_ylabel("Bz [nT]", fontsize=8, color=_C.BZ)
    ax6.tick_params(axis="y", labelcolor=_C.KP)
    ax6_twin.tick_params(axis="y", labelcolor=_C.BZ)

    lines = (ax6.get_legend_handles_labels()[0]
             + ax6_twin.get_legend_handles_labels()[0])
    labels = (ax6.get_legend_handles_labels()[1]
              + ax6_twin.get_legend_handles_labels()[1])
    ax6.legend(lines, labels, fontsize=6, framealpha=0.2)
    _fmt_axis(ax6,
              "Kp & Bz  →  Fırtına Ölçekleme  (Ippolito 2017)",
              "Kp")

    # ── Ana başlık ────────────────────────────────────────────
    fig.text(0.5, 0.965,
             "UZAY HAVASI → RADYO SİNYAL BOZULMA SİMÜLASYONU",
             ha="center", fontsize=13, fontweight="bold",
             color="#e8f4fd", fontfamily="monospace")
    fig.text(0.5, 0.945,
             "FSPL + Nyquist (1928)  ·  Dungey (1961)  ·  Parker (1958)  ·  Secan (1997)  ·  Ippolito (2017)",
             ha="center", fontsize=8, color="#4a6280",
             fontfamily="monospace")

    plt.savefig(out_path, dpi=150, bbox_inches="tight",
                facecolor=_C.BG, edgecolor="none")
    log.info(f"[PLOT]  Grafik kaydedildi → {out_path}")
    return out_path