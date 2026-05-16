from __future__ import annotations

from scenario_db.sim.perf_calc import calc_processing_time


def test_isp_fhd30_processing_time() -> None:
    """Golden: 2073600 / (533e6 * 4) * 1.05 * 1000 = 1.021 ms."""
    pixels = 1920 * 1080  # = 2073600
    result = calc_processing_time(
        pixels=pixels,
        set_clock_mhz=533.0,
        ppc=4.0,
        h_blank_margin=0.05,
    )
    assert abs(result - 1.021) < 0.05, f"Expected ~1.021 ms, got {result}"


def test_processing_time_no_blank() -> None:
    """h_blank_margin=0 이면 순수 픽셀/클럭 시간."""
    pixels = 1000000
    clock_mhz = 500.0
    ppc = 4.0
    result = calc_processing_time(pixels=pixels, set_clock_mhz=clock_mhz, ppc=ppc, h_blank_margin=0.0)
    expected = pixels / (clock_mhz * 1e6 * ppc) * 1000.0  # ms
    assert abs(result - expected) < 1e-9


def test_processing_time_feasibility() -> None:
    """FHD30: hw_time=1.021ms < frame_interval=33.33ms → feasible."""
    hw_time_ms = calc_processing_time(
        pixels=1920 * 1080, set_clock_mhz=533.0, ppc=4.0, h_blank_margin=0.05
    )
    frame_interval_ms = 1000.0 / 30.0  # 33.33 ms
    assert hw_time_ms < frame_interval_ms, f"hw_time={hw_time_ms} should be < {frame_interval_ms}"
