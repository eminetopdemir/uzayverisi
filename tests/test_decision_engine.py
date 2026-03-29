from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from decision_engine import (
    build_data_rate_profile,
    generate_recommendation,
    plot_data_rate_over_time,
    recommended_data_rate_mbps,
)


def test_generate_recommendation_safe_mode():
    out = generate_recommendation(snr=12.3, loss=3.1)

    assert out["mode"] == "SAFE"
    assert out["risk_level"] == "LOW"
    assert out["modulation"] == "256-QAM"
    assert out["power_adjustment"] == "0%"
    assert "explanation" in out
    assert 0.0 <= out["confidence"] <= 1.0


def test_generate_recommendation_adaptive_mode_boundaries():
    out_low = generate_recommendation(snr=0.0, loss=49.8)
    out_high = generate_recommendation(snr=10.0, loss=9.0)

    assert out_low["mode"] == "ADAPTIVE"
    assert out_high["mode"] == "ADAPTIVE"
    assert out_low["risk_level"] == "MEDIUM"
    assert "QPSK" in out_low["modulation"]


def test_generate_recommendation_protection_mode():
    out = generate_recommendation(snr=-2.5, loss=69.6)

    assert out["mode"] == "PROTECTION"
    assert out["risk_level"] == "HIGH"
    assert out["modulation"] == "BPSK"
    assert out["power_adjustment"] == "+30%"
    assert "critical telemetry" in out["recommended_action"].lower()


def test_recommended_data_rate_mapping():
    assert recommended_data_rate_mbps(12.0, nominal_rate_mbps=100.0) == 100.0
    assert recommended_data_rate_mbps(-3.0, nominal_rate_mbps=100.0) == 15.0

    adaptive_val = recommended_data_rate_mbps(5.0, nominal_rate_mbps=100.0)
    assert 35.0 <= adaptive_val <= 100.0


def test_build_data_rate_profile_and_plot(tmp_path):
    times = [
        "2026-03-29T10:00:00",
        "2026-03-29T10:01:00",
        "2026-03-29T10:02:00",
    ]
    snr_values = [12.0, 4.0, -1.0]

    df = build_data_rate_profile(times, snr_values, nominal_rate_mbps=120.0)
    assert list(df.columns) == ["time", "snr", "data_rate_mbps", "mode"]
    assert len(df) == 3

    out_file = tmp_path / "guidance_plot.png"
    path = plot_data_rate_over_time(times, snr_values, 120.0, out_file)
    assert path.exists()
