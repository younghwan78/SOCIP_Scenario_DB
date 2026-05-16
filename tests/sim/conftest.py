from __future__ import annotations

import pytest

from scenario_db.models.capability.hw import IPSimParams, PortSpec, PortType
from scenario_db.models.definition.usecase import (
    IPPortConfig,
    PortInputConfig,
    SimGlobalConfig,
    SensorSpec,
)
from scenario_db.sim.models import DVFSLevel, DVFSTable


@pytest.fixture
def isp_sim_params() -> IPSimParams:
    return IPSimParams(
        hw_name_in_sim="ISP",
        ppc=4.0,
        unit_power_mw_mp=10.5,
        idc=0.5,
        vdd="VDD_INTCAM",
        dvfs_group="CAM",
        ports=[
            PortSpec(name="RDMA_FE", type=PortType.DMA_READ, max_bw_gbps=25.6),
            PortSpec(name="WDMA_BE", type=PortType.DMA_WRITE, max_bw_gbps=12.8),
            PortSpec(name="CINFIFO", type=PortType.OTF_IN),
            PortSpec(name="COUTFIFO", type=PortType.OTF_OUT),
        ],
    )


@pytest.fixture
def csis_sim_params() -> IPSimParams:
    return IPSimParams(
        hw_name_in_sim="CSIS",
        ppc=4.0,
        unit_power_mw_mp=3.2,
        idc=0.1,
        vdd="VDD_CAM",
        dvfs_group="CAM",
        ports=[
            PortSpec(name="WDMA", type=PortType.DMA_WRITE, max_bw_gbps=12.8),
            PortSpec(name="COUTFIFO", type=PortType.OTF_OUT),
        ],
    )


@pytest.fixture
def cam_dvfs_table() -> DVFSTable:
    return DVFSTable(
        domain="CAM",
        levels=[
            DVFSLevel(level=0, speed_mhz=600, voltages={0: 820, 4: 780, 8: 750}),
            DVFSLevel(level=1, speed_mhz=533, voltages={0: 760, 4: 720, 8: 700}),
            DVFSLevel(level=2, speed_mhz=400, voltages={0: 700, 4: 660, 8: 630}),
        ],
    )


@pytest.fixture
def fhd30_wdma_port() -> PortInputConfig:
    """FHD30 ISP WDMA_BE NV12 — Golden BW = 93.312 MB/s.
    계산: 1.0 * 30 * 1920 * 1080 * (8/8) * 1.5 / 1e6 = 93.312
    """
    return PortInputConfig(
        port="WDMA_BE",
        format="NV12",
        bitwidth=8,
        width=1920,
        height=1080,
        compression="disable",
    )


@pytest.fixture
def fhd30_rdma_port() -> PortInputConfig:
    """FHD30 ISP RDMA_FE BAYER SBWC — Golden BW = 202.68 MB/s.
    계산: 0.5 * 30 * 4000 * 2252 * (12/8) * 1.0 / 1e6 = 202.68
    """
    return PortInputConfig(
        port="RDMA_FE",
        format="BAYER",
        bitwidth=12,
        width=4000,
        height=2252,
        compression="SBWC",
        comp_ratio=0.5,
    )


@pytest.fixture
def default_sim_config() -> SimGlobalConfig:
    return SimGlobalConfig(
        asv_group=4,
        sw_margin=0.25,
        bw_power_coeff=80.0,
        vbat=4.0,
        pmic_eff=0.85,
        h_blank_margin=0.05,
    )


@pytest.fixture
def sensor_fhd30() -> SensorSpec:
    """FHD30 센서 — OTF 그룹 DVFS 제약용."""
    return SensorSpec(
        ip_ref="ip-csis-v3",
        frame_width=4000,
        frame_height=3000,
        fps=30.0,
        v_valid_ratio=0.85,
    )
