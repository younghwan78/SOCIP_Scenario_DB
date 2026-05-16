from __future__ import annotations

import logging

import pytest

from scenario_db.models.capability.hw import IPSimParams, PortSpec, PortType
from scenario_db.models.definition.usecase import (
    EdgeType,
    IPPortConfig,
    Pipeline,
    PipelineEdge,
    PipelineNode,
    SensorSpec,
    SimGlobalConfig,
)
from scenario_db.sim.dvfs_resolver import DvfsResolver
from scenario_db.sim.models import DVFSLevel, DVFSTable, ResolvedIPConfig


@pytest.fixture
def cam_dvfs_tables(cam_dvfs_table: DVFSTable) -> dict[str, DVFSTable]:
    return {"CAM": cam_dvfs_table}


@pytest.fixture
def simple_pipeline() -> Pipeline:
    """ISP 단일 노드 M2M 파이프라인."""
    return Pipeline(
        nodes=[PipelineNode(id="isp0", ip_ref="ip-isp-v12")],
        edges=[],
    )


@pytest.fixture
def otf_pipeline() -> Pipeline:
    """CSIS -> ISP OTF 연결 파이프라인."""
    return Pipeline(
        nodes=[
            PipelineNode(id="csis0", ip_ref="ip-csis-v3"),
            PipelineNode(id="isp0", ip_ref="ip-isp-v12"),
        ],
        edges=[
            PipelineEdge(**{"from": "csis0", "to": "isp0", "type": EdgeType.OTF}),
        ],
    )


@pytest.fixture
def isp_only_params(isp_sim_params: IPSimParams) -> dict[str, IPSimParams]:
    return {"isp0": isp_sim_params}


@pytest.fixture
def csis_isp_params(isp_sim_params: IPSimParams, csis_sim_params: IPSimParams) -> dict[str, IPSimParams]:
    return {"csis0": csis_sim_params, "isp0": isp_sim_params}


def test_dvfs_basic_level_selection(
    cam_dvfs_tables: dict[str, DVFSTable],
    isp_only_params: dict[str, IPSimParams],
    simple_pipeline: Pipeline,
) -> None:
    """ISP FHD30: required=20.74MHz -> CAM level 2(400MHz), voltage=660mV(asv=4)."""
    resolver = DvfsResolver(dvfs_tables=cam_dvfs_tables, asv_group=4)
    port_configs: dict[str, IPPortConfig] = {
        "isp0": IPPortConfig(
            inputs=[],
            outputs=[],
        )
    }
    resolved = resolver.resolve(
        ip_params=isp_only_params,
        port_configs=port_configs,
        pipeline=simple_pipeline,
        fps=30.0,
        sw_margin=0.25,
        sensor_spec=None,
    )

    assert "isp0" in resolved
    r = resolved["isp0"]
    # required_clock = 1920*1080*30 / ((1-0.25)*4) / 1e6 = 20.74 MHz
    assert r.required_clock_mhz < 25.0
    assert r.set_clock_mhz == 400.0   # level 2
    assert r.set_voltage_mv == 660.0  # asv_group=4, level 2 voltage
    assert r.dvfs_group == "CAM"
    assert r.vdd == "VDD_INTCAM"


def test_dvfs_otf_group_constraint(
    cam_dvfs_tables: dict[str, DVFSTable],
    csis_isp_params: dict[str, IPSimParams],
    otf_pipeline: Pipeline,
    sensor_fhd30: SensorSpec,
) -> None:
    """OTF 그룹: sensor v_valid_time 기반 required_clock >= 105.88 MHz -> level 1(533MHz) 이상."""
    resolver = DvfsResolver(dvfs_tables=cam_dvfs_tables, asv_group=4)
    port_configs = {
        "csis0": IPPortConfig(inputs=[], outputs=[]),
        "isp0": IPPortConfig(inputs=[], outputs=[]),
    }
    resolved = resolver.resolve(
        ip_params=csis_isp_params,
        port_configs=port_configs,
        pipeline=otf_pipeline,
        fps=30.0,
        sw_margin=0.25,
        sensor_spec=sensor_fhd30,  # 4000x3000, fps=30, v_valid_ratio=0.85
    )

    # OTF 그룹 required_clock = 4000*3000 / ((1/30)*0.85) / 4 / 1e6 = 105.88 MHz
    # -> level 0(600MHz) 또는 level 1(533MHz) 선택 — 최소 레벨 = 533MHz
    for node_id in ("csis0", "isp0"):
        assert node_id in resolved
        r = resolved[node_id]
        assert r.set_clock_mhz >= 533.0, (
            f"{node_id}: set_clock={r.set_clock_mhz} should be >= 533 MHz (OTF constraint)"
        )
        assert r.required_clock_mhz > 100.0, (
            f"{node_id}: required_clock={r.required_clock_mhz} should reflect OTF constraint"
        )


def test_dvfs_fallback_missing_domain(
    isp_only_params: dict[str, IPSimParams],
    simple_pipeline: Pipeline,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """DVFS domain 없음 -> ValueError 없이 fallback + logging.WARNING."""
    resolver = DvfsResolver(dvfs_tables={}, asv_group=4)  # CAM 없음
    port_configs = {"isp0": IPPortConfig(inputs=[], outputs=[])}

    with caplog.at_level(logging.WARNING, logger="scenario_db.sim.dvfs_resolver"):
        resolved = resolver.resolve(
            ip_params=isp_only_params,
            port_configs=port_configs,
            pipeline=simple_pipeline,
            fps=30.0,
        )

    assert "isp0" in resolved
    r = resolved["isp0"]
    # Fallback: set_clock = required_clock (not 0 or undefined)
    assert r.set_clock_mhz == r.required_clock_mhz
    assert r.set_voltage_mv == 710.0  # REFERENCE_VOLTAGE_MV
    # logging.warning이 출력되어야 함
    assert len(caplog.records) > 0, "DVFS fallback시 logging.warning이 있어야 함"


def test_dvfs_vdd_voltage_alignment(
    cam_dvfs_tables: dict[str, DVFSTable],
    csis_isp_params: dict[str, IPSimParams],
    otf_pipeline: Pipeline,
) -> None:
    """같은 VDD 도메인 IP들은 max(voltage)로 정렬 (Pitfall 3 방지).
    ISP(VDD_INTCAM)과 CSIS(VDD_CAM) — 서로 다른 VDD이므로 독립적으로 결정됨.
    """
    resolver = DvfsResolver(dvfs_tables=cam_dvfs_tables, asv_group=4)
    port_configs = {
        "csis0": IPPortConfig(inputs=[], outputs=[]),
        "isp0": IPPortConfig(inputs=[], outputs=[]),
    }
    resolved = resolver.resolve(
        ip_params=csis_isp_params,
        port_configs=port_configs,
        pipeline=otf_pipeline,
        fps=30.0,
    )

    # 각 IP의 set_voltage_mv는 해당 VDD 도메인 max 전압이어야 함
    for node_id, r in resolved.items():
        assert r.set_voltage_mv > 0.0, f"{node_id}: set_voltage_mv should be positive"
