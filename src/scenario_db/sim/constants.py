from __future__ import annotations

# ---------------------------------------------------------------------------
# BPP Map: samples-per-pixel (bitwidth는 별도 인수로 bit count 담당)
# 출처: docs/simulation-engine-integration.md §6.2 + SimEngine constants.py 검증
# ---------------------------------------------------------------------------
BPP_MAP: dict[str, float] = {
    "NV12":   1.5,    # YUV420 semi-planar (1 Y + 0.5 UV per pixel)
    "YUV420": 1.5,    # NV12 동일
    "RAW10":  1.25,   # Bayer 10-bit packed (10/8 samples per byte)
    "ARGB":   4.0,    # 32-bit RGBA (4 bytes per pixel)
    "BAYER":  1.0,    # 1 sample/pixel; bitwidth 인수가 bit count 담당 (예: bitwidth=12)
}

BW_POWER_COEFF_DEFAULT: float = 80.0   # mW/(GB/s) — DRAM BW당 전력 계수
REFERENCE_VOLTAGE_MV: float = 710.0    # 0.71V — power V² 스케일링 기준 전압
REFERENCE_FPS: float = 30.0            # 30fps — power fps 스케일링 기준
