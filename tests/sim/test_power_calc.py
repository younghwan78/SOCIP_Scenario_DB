from __future__ import annotations

from scenario_db.sim.power_calc import calc_active_power


def test_isp_fhd30_active_power() -> None:
    """Golden: 10.5 * (1920*1080/1e6) * (780/710)^2 * (30/30) = 26.28 mW."""
    result = calc_active_power(
        unit_power_mw_mp=10.5,
        width=1920,
        height=1080,
        set_voltage_mv=780.0,
        fps=30.0,
    )
    assert abs(result - 26.28) < 0.5, f"Expected ~26.28 mW, got {result}"


def test_power_reference_voltage_scaling() -> None:
    """set_voltage=710mV (REFERENCE_VOLTAGE_MV) → voltage_scale=1.0."""
    result_ref = calc_active_power(
        unit_power_mw_mp=10.0, width=1000, height=1000,
        set_voltage_mv=710.0, fps=30.0,
    )
    expected = 10.0 * (1000 * 1000 / 1e6) * 1.0 * 1.0  # = 10.0 mW
    assert abs(result_ref - expected) < 0.001


def test_power_fps_scaling_half() -> None:
    """fps를 절반으로 줄이면 power도 절반."""
    result_30 = calc_active_power(
        unit_power_mw_mp=10.0, width=1920, height=1080,
        set_voltage_mv=710.0, fps=30.0,
    )
    result_15 = calc_active_power(
        unit_power_mw_mp=10.0, width=1920, height=1080,
        set_voltage_mv=710.0, fps=15.0,
    )
    assert abs(result_15 - result_30 / 2.0) < 0.001


def test_power_voltage_squared_scaling() -> None:
    """전압 2배 → power 4배 (V² 스케일링)."""
    result_710 = calc_active_power(
        unit_power_mw_mp=1.0, width=1000, height=1000,
        set_voltage_mv=710.0, fps=30.0,
    )
    result_1420 = calc_active_power(
        unit_power_mw_mp=1.0, width=1000, height=1000,
        set_voltage_mv=1420.0, fps=30.0,
    )
    # (1420/710)^2 = 4.0
    assert abs(result_1420 / result_710 - 4.0) < 0.001
