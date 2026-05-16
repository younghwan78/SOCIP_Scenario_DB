from __future__ import annotations

import pytest

from scenario_db.models.capability.hw import PortType
from scenario_db.models.definition.usecase import PortInputConfig
from scenario_db.sim.bw_calc import calc_port_bw


def test_fhd30_wdma_be_golden(fhd30_wdma_port: PortInputConfig) -> None:
    """Golden: 1.0 * 30 * 1920 * 1080 * (8/8) * 1.5 / 1e6 = 93.312 MB/s."""
    result = calc_port_bw(
        port=fhd30_wdma_port,
        ip_name="ISP",
        port_type=PortType.DMA_WRITE,
        fps=30.0,
    )
    assert abs(result.bw_mbs - 93.312) / 93.312 < 0.01, (
        f"Expected ~93.312 MB/s, got {result.bw_mbs}"
    )
    assert result.direction == "write"
    assert result.ip == "ISP"
    assert result.port == "WDMA_BE"
    assert result.format == "NV12"
    assert result.compression == "disable"
    assert result.llc_enabled is False


def test_fhd30_rdma_fe_golden(fhd30_rdma_port: PortInputConfig) -> None:
    """Golden: 0.5 * 30 * 4000 * 2252 * (12/8) * 1.0 / 1e6 = 202.68 MB/s."""
    result = calc_port_bw(
        port=fhd30_rdma_port,
        ip_name="ISP",
        port_type=PortType.DMA_READ,
        fps=30.0,
    )
    assert abs(result.bw_mbs - 202.68) / 202.68 < 0.01, (
        f"Expected ~202.68 MB/s, got {result.bw_mbs}"
    )
    assert result.direction == "read"
    assert result.compression == "SBWC"


def test_otf_in_returns_zero(fhd30_wdma_port: PortInputConfig) -> None:
    """OTF_IN 포트는 DRAM 액세스 없음 — bw_mbs=0."""
    result = calc_port_bw(
        port=fhd30_wdma_port,
        ip_name="ISP",
        port_type=PortType.OTF_IN,
        fps=30.0,
    )
    assert result.bw_mbs == 0.0
    assert result.bw_power_mw == 0.0


def test_otf_out_returns_zero(fhd30_wdma_port: PortInputConfig) -> None:
    result = calc_port_bw(
        port=fhd30_wdma_port,
        ip_name="ISP",
        port_type=PortType.OTF_OUT,
        fps=30.0,
    )
    assert result.bw_mbs == 0.0
    assert result.bw_power_mw == 0.0


def test_direction_dma_read() -> None:
    port = PortInputConfig(port="RDMA", format="NV12", width=1920, height=1080)
    result = calc_port_bw(port=port, ip_name="ISP", port_type=PortType.DMA_READ, fps=30.0)
    assert result.direction == "read"


def test_direction_dma_write() -> None:
    port = PortInputConfig(port="WDMA", format="NV12", width=1920, height=1080)
    result = calc_port_bw(port=port, ip_name="ISP", port_type=PortType.DMA_WRITE, fps=30.0)
    assert result.direction == "write"


def test_compression_disable_uses_ratio_1() -> None:
    """compression=disable이면 comp_ratio=0.5 설정돼도 1.0 사용."""
    port_compress = PortInputConfig(
        port="WDMA", format="NV12", width=1920, height=1080,
        compression="disable", comp_ratio=0.5,
    )
    port_no_compress = PortInputConfig(
        port="WDMA", format="NV12", width=1920, height=1080,
        compression="disable", comp_ratio=1.0,
    )
    r1 = calc_port_bw(port=port_compress, ip_name="ISP", port_type=PortType.DMA_WRITE, fps=30.0)
    r2 = calc_port_bw(port=port_no_compress, ip_name="ISP", port_type=PortType.DMA_WRITE, fps=30.0)
    assert abs(r1.bw_mbs - r2.bw_mbs) < 0.001, "disable compression이면 comp_ratio 무시해야 함"


def test_llc_disabled_uses_weight_1() -> None:
    """llc_enabled=False이면 llc_weight 무시 (bw_power에 영향 없음)."""
    port = PortInputConfig(
        port="WDMA", format="NV12", width=1920, height=1080,
        llc_enabled=False, llc_weight=0.3,
    )
    result = calc_port_bw(port=port, ip_name="ISP", port_type=PortType.DMA_WRITE, fps=30.0)
    # llc_enabled=False → weight=1.0 적용, weight=0.3 아님
    expected_power = result.bw_mbs * 80.0 / 1000.0 * 1.0
    assert abs(result.bw_power_mw - expected_power) < 0.001


def test_bw_mbs_worst_when_comp_ratio_max_set() -> None:
    """comp_ratio_max 설정 시 bw_mbs_worst 계산."""
    port = PortInputConfig(
        port="RDMA", format="NV12", width=1920, height=1080,
        compression="SBWC", comp_ratio=0.5, comp_ratio_max=0.8,
    )
    result = calc_port_bw(port=port, ip_name="ISP", port_type=PortType.DMA_READ, fps=30.0)
    assert result.bw_mbs_worst is not None
    assert result.bw_mbs_worst > result.bw_mbs  # worst > nominal
