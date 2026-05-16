from __future__ import annotations

from scenario_db.models.evidence.simulation import (
    IPTimingResult as EvidenceIPTimingResult,
)
from scenario_db.models.evidence.simulation import (
    PortBWResult as EvidencePortBWResult,
)
from scenario_db.sim.models import (
    DVFSLevel,
    DVFSTable,
    IPTimingResult,
    PortBWResult,
    ResolvedIPConfig,
    SimRunResult,
)


def test_port_bw_result_is_reimport() -> None:
    """D-01: sim.models.PortBWResult는 evidence.simulation.PortBWResult와 동일 클래스."""
    assert PortBWResult is EvidencePortBWResult


def test_ip_timing_result_is_reimport() -> None:
    assert IPTimingResult is EvidenceIPTimingResult


def test_dvfs_level_roundtrip() -> None:
    obj = DVFSLevel(level=0, speed_mhz=600.0, voltages={0: 820, 4: 780, 8: 750})
    dumped = obj.model_dump(exclude_none=True)
    obj2 = DVFSLevel.model_validate(dumped)
    assert obj == obj2
    assert obj.speed_mhz == 600.0


def test_dvfs_table_roundtrip() -> None:
    obj = DVFSTable(
        domain="CAM",
        levels=[
            DVFSLevel(level=0, speed_mhz=600.0, voltages={0: 820, 4: 780}),
            DVFSLevel(level=1, speed_mhz=533.0, voltages={0: 760, 4: 720}),
        ],
    )
    dumped = obj.model_dump(exclude_none=True)
    obj2 = DVFSTable.model_validate(dumped)
    assert obj == obj2


def test_dvfs_table_find_min_level() -> None:
    table = DVFSTable(
        domain="CAM",
        levels=[
            DVFSLevel(level=0, speed_mhz=600.0, voltages={4: 780}),
            DVFSLevel(level=1, speed_mhz=533.0, voltages={4: 720}),
            DVFSLevel(level=2, speed_mhz=400.0, voltages={4: 660}),
        ],
    )
    # 20.74 MHz required -> level 2 (400 MHz) 충분 — 가장 낮은 speed 선택
    lv = table.find_min_level(required_clock_mhz=20.74, asv_group=4)
    assert lv is not None
    assert lv.level == 2
    assert lv.speed_mhz == 400.0


def test_dvfs_table_find_min_level_none_when_insufficient() -> None:
    table = DVFSTable(
        domain="CAM",
        levels=[DVFSLevel(level=0, speed_mhz=100.0, voltages={4: 700})],
    )
    # 200 MHz required → 모든 레벨 insufficient
    lv = table.find_min_level(required_clock_mhz=200.0, asv_group=4)
    assert lv is None


def test_resolved_ip_config_roundtrip() -> None:
    obj = ResolvedIPConfig(
        ip_name="ISP",
        required_clock_mhz=20.74,
        set_clock_mhz=400.0,
        set_voltage_mv=660.0,
        dvfs_group="CAM",
        vdd="VDD_INTCAM",
    )
    dumped = obj.model_dump(exclude_none=True)
    obj2 = ResolvedIPConfig.model_validate(dumped)
    assert obj == obj2


def test_sim_run_result_roundtrip() -> None:
    bw = PortBWResult(ip="ISP", port="WDMA_BE", direction="write", bw_mbs=93.31, bw_power_mw=7.46)
    timing = IPTimingResult(
        ip="ISP", hw_time_ms=1.021,
        required_clock_mhz=20.74, set_clock_mhz=400.0,
        set_voltage_mv=660.0, feasible=True,
    )
    resolved = ResolvedIPConfig(
        ip_name="ISP", required_clock_mhz=20.74, set_clock_mhz=400.0,
        set_voltage_mv=660.0, dvfs_group="CAM", vdd="VDD_INTCAM",
    )
    obj = SimRunResult(
        scenario_id="uc-camera-recording",
        variant_id="FHD30-normal",
        total_power_mw=26.28,
        total_power_ma=7.73,
        bw_total_mbs=93.31,
        hw_time_max_ms=1.021,
        feasible=True,
        resolved={"isp0": resolved},
        dma_breakdown=[bw],
        timing_breakdown=[timing],
        vdd_power={"VDD_INTCAM": 26.28},
    )
    dumped = obj.model_dump(exclude_none=True)
    obj2 = SimRunResult.model_validate(dumped)
    assert obj2.scenario_id == "uc-camera-recording"
    assert obj2.feasible is True
    assert len(obj2.dma_breakdown) == 1
    assert len(obj2.timing_breakdown) == 1
