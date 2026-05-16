from __future__ import annotations

from scenario_db.sim.constants import REFERENCE_FPS, REFERENCE_VOLTAGE_MV


def calc_active_power(
    unit_power_mw_mp: float,
    width: int,
    height: int,
    set_voltage_mv: float,
    fps: float,
) -> float:
    """IP Active Power(mW) 계산.

    공식 (설계 문서 §2.2):
        power = unit_power_mw_mp * resolution_MP * (set_voltage_mv / 710.0)^2 * (fps / 30.0)

    Args:
        unit_power_mw_mp: IP 단위 전력 [mW/MP] (IPSimParams.unit_power_mw_mp)
        width: 처리 해상도 너비 (픽셀)
        height: 처리 해상도 높이 (픽셀)
        set_voltage_mv: DVFS 결정 전압 (mV)
        fps: 목표 프레임레이트

    Returns:
        Active power (mW), float
    """
    resolution_mp: float = (width * height) / 1e6
    voltage_scale: float = (set_voltage_mv / REFERENCE_VOLTAGE_MV) ** 2
    fps_scale: float = fps / REFERENCE_FPS
    return unit_power_mw_mp * resolution_mp * voltage_scale * fps_scale
