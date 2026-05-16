from __future__ import annotations


def calc_processing_time(
    pixels: int,
    set_clock_mhz: float,
    ppc: float,
    h_blank_margin: float = 0.05,
) -> float:
    """IP 처리시간(ms) 계산.

    공식 (설계 문서 §2.2):
        hw_time_ms = pixels / (set_clock_mhz * 1e6 * ppc) * (1 + h_blank_margin) * 1000

    Args:
        pixels: 처리할 픽셀 수 (width * height), int 타입
        set_clock_mhz: DVFS로 결정된 IP 클럭 (MHz), float
        ppc: pixels-per-clock (IP 처리 폭), float
        h_blank_margin: 수평 블랭킹 여유 비율 (default 0.05 = 5%)
                        SimGlobalConfig.h_blank_margin 값을 전달

    Returns:
        처리시간 (ms), float. feasible 판정: hw_time_ms <= (1000.0 / fps)
    """
    return pixels / (set_clock_mhz * 1e6 * ppc) * (1.0 + h_blank_margin) * 1000.0
