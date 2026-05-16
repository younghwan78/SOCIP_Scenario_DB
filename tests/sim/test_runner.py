from __future__ import annotations

import pytest

from scenario_db.models.capability.hw import IpCatalog, IpCapabilities, IpHierarchy
from scenario_db.models.definition.usecase import (
    EdgeType,
    IPPortConfig,
    Pipeline,
    PipelineEdge,
    PipelineNode,
    PortInputConfig,
    SimGlobalConfig,
)
from scenario_db.sim.models import DVFSTable, SimRunResult
from scenario_db.sim.runner import run_simulation


def _make_ip_catalog(ip_ref: str, sim_params) -> IpCatalog:
    return IpCatalog(
        id=ip_ref,
        schema_version="2.2",
        kind="ip",
        category="ISP",
        hierarchy=IpHierarchy(type="simple"),
        capabilities=IpCapabilities(),
        sim_params=sim_params,
    )


def test_run_simulation_fhd30_isp(
    isp_sim_params,
    cam_dvfs_table: DVFSTable,
    fhd30_wdma_port: PortInputConfig,
    fhd30_rdma_port: PortInputConfig,
    default_sim_config: SimGlobalConfig,
) -> None:
    """FHD30 ISP M2M 파이프라인 end-to-end: SimRunResult 반환, feasible=True."""
    pipeline = Pipeline(
        nodes=[PipelineNode(id="isp0", ip_ref="ip-isp-v12")],
        edges=[],
    )
    ip_catalog = {"ip-isp-v12": _make_ip_catalog("ip-isp-v12", isp_sim_params)}
    dvfs_tables = {"CAM": cam_dvfs_table}
    variant_port_config = {
        "isp0": IPPortConfig(
            inputs=[fhd30_rdma_port],
            outputs=[fhd30_wdma_port],
        )
    }

    result = run_simulation(
        scenario_id="uc-camera-recording",
        variant_id="FHD30-normal",
        pipeline=pipeline,
        ip_catalog=ip_catalog,
        dvfs_tables=dvfs_tables,
        variant_port_config=variant_port_config,
        sim_config=default_sim_config,
        sensor_spec=None,
    )

    assert isinstance(result, SimRunResult)
    assert result.scenario_id == "uc-camera-recording"
    assert result.variant_id == "FHD30-normal"
    assert result.feasible is True
    assert result.bw_total_mbs > 0.0
    assert result.total_power_mw > 0.0
    assert len(result.dma_breakdown) > 0
    assert len(result.timing_breakdown) > 0
    assert "isp0" in result.resolved


def test_run_simulation_bw_golden(
    isp_sim_params,
    cam_dvfs_table: DVFSTable,
    fhd30_wdma_port: PortInputConfig,
    default_sim_config: SimGlobalConfig,
) -> None:
    """WDMA_BE NV12 disable BW Golden 값이 SimRunResult.dma_breakdown에 반영됨."""
    pipeline = Pipeline(
        nodes=[PipelineNode(id="isp0", ip_ref="ip-isp-v12")],
        edges=[],
    )
    ip_catalog = {"ip-isp-v12": _make_ip_catalog("ip-isp-v12", isp_sim_params)}
    variant_port_config = {
        "isp0": IPPortConfig(inputs=[], outputs=[fhd30_wdma_port])
    }

    result = run_simulation(
        scenario_id="uc-test",
        variant_id="FHD30",
        pipeline=pipeline,
        ip_catalog=ip_catalog,
        dvfs_tables={"CAM": cam_dvfs_table},
        variant_port_config=variant_port_config,
        sim_config=default_sim_config,
    )

    wdma_results = [r for r in result.dma_breakdown if r.port == "WDMA_BE"]
    assert len(wdma_results) == 1
    # Golden: 93.312 MB/s (+-1%)
    assert abs(wdma_results[0].bw_mbs - 93.312) / 93.312 < 0.01
