"""Phase 5 Schema Extensions — Pydantic 모델 round-trip + backward compat 단위 테스트.

FIXTURES 경로:
  - fixtures/hw/ip-isp-v12.yaml           (기존 — sim_params 없음)
  - fixtures/hw/ip-isp-v12-with-sim.yaml  (신규 — sim_params 있음)
  - fixtures/evidence/sim-camera-recording-UHD60-A0-sw123.yaml  (기존 — breakdown 없음)
  - fixtures/evidence/sim-FHD30-with-breakdown.yaml             (신규 — breakdown 있음)
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from scenario_db.models.capability.hw import (
    IpCatalog,
    IPSimParams,
    PortSpec,
    PortType,
)
from scenario_db.models.definition.usecase import (
    IPPortConfig,
    PortInputConfig,
    SensorSpec,
    SimGlobalConfig,
    Usecase,
    Variant,
)
from scenario_db.models.evidence.simulation import (
    IPTimingResult,
    PortBWResult,
    SimulationEvidence,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def roundtrip(model_cls, path: Path, **dump_kwargs):
    raw = load_yaml(path)
    obj = model_cls.model_validate(raw)
    serialised = obj.model_dump(exclude_none=True, **dump_kwargs)
    obj2 = model_cls.model_validate(serialised)
    assert obj == obj2
    return obj


# ---------------------------------------------------------------------------
# SCH-01: IpCatalog.sim_params
# ---------------------------------------------------------------------------

def test_ip_catalog_backward_compat_no_sim_params():
    """기존 ip-isp-v12.yaml (sim_params 없음)이 ValidationError 없이 파싱된다."""
    obj = roundtrip(IpCatalog, FIXTURES / "hw" / "ip-isp-v12.yaml")
    assert obj.sim_params is None


def test_ip_catalog_sim_params_roundtrip():
    """sim_params가 있는 fixture가 round-trip 직렬화를 통과한다."""
    obj = roundtrip(IpCatalog, FIXTURES / "hw" / "ip-isp-v12-with-sim.yaml")
    assert obj.sim_params is not None
    assert obj.sim_params.hw_name_in_sim == "ISP"
    assert obj.sim_params.ppc == 4.0
    assert len(obj.sim_params.ports) == 4


def test_ip_sim_params_port_types():
    """PortSpec의 type이 PortType enum으로 정확히 파싱된다."""
    obj = roundtrip(IpCatalog, FIXTURES / "hw" / "ip-isp-v12-with-sim.yaml")
    types = {p.type for p in obj.sim_params.ports}
    assert PortType.DMA_READ in types
    assert PortType.OTF_IN in types


def test_ip_sim_params_inline():
    """IPSimParams inline dict로 직접 생성 가능하다."""
    params = IPSimParams(
        hw_name_in_sim="MFC",
        ppc=2.0,
        unit_power_mw_mp=5.0,
        vdd="VDD_INT",
        dvfs_group="INT",
        ports=[PortSpec(name="RDMA", type=PortType.DMA_READ)],
    )
    assert params.idc == 0.0
    assert params.latency_us == 0.0


# ---------------------------------------------------------------------------
# SCH-02: Variant.sim_port_config + sim_config
# ---------------------------------------------------------------------------

def test_variant_sim_config_defaults():
    """SimGlobalConfig의 모든 필드가 기본값을 가진다."""
    cfg = SimGlobalConfig()
    assert cfg.asv_group == 4
    assert cfg.sw_margin == 0.25
    assert cfg.bw_power_coeff == 80.0
    assert cfg.dvfs_overrides is None  # CR-01: dict[str,int]|None=None으로 변경


def test_port_input_config_compression_literal():
    """PortInputConfig.compression이 허용되지 않는 값이면 ValidationError."""
    with pytest.raises(ValidationError):
        PortInputConfig(
            port="RDMA", format="BAYER", width=1920, height=1080,
            compression="INVALID_CODEC",
        )


def test_ip_port_config_roundtrip():
    """IPPortConfig가 dict -> model -> dict 직렬화를 통과한다."""
    raw = {
        "mode": "Normal",
        "inputs": [
            {"port": "RDMA_FE", "format": "BAYER", "width": 4000, "height": 2252}
        ],
    }
    cfg = IPPortConfig.model_validate(raw)
    out = cfg.model_dump(exclude_none=True)
    cfg2 = IPPortConfig.model_validate(out)
    assert cfg == cfg2


def test_usecase_backward_compat_no_sim_config():
    """기존 uc-camera-recording.yaml (sim_port_config 없음)이 ValidationError 없이 파싱된다."""
    obj = roundtrip(Usecase, FIXTURES / "definition" / "uc-camera-recording.yaml")
    for v in obj.variants:
        assert v.sim_port_config is None
        assert v.sim_config is None


# ---------------------------------------------------------------------------
# SCH-03: Usecase.sensor (SensorSpec)
# ---------------------------------------------------------------------------

def test_sensor_spec_roundtrip():
    """SensorSpec inline dict가 round-trip 직렬화를 통과한다."""
    raw = {
        "ip_ref": "ip-csis-v8",
        "frame_width": 4000,
        "frame_height": 3000,
        "fps": 60.0,
    }
    spec = SensorSpec.model_validate(raw)
    assert spec.v_valid_ratio == 0.85
    out = spec.model_dump(exclude_none=True)
    spec2 = SensorSpec.model_validate(out)
    assert spec == spec2


def test_sensor_spec_extra_field_forbidden():
    """SensorSpec에 알 수 없는 필드를 추가하면 ValidationError."""
    with pytest.raises(ValidationError):
        SensorSpec.model_validate({
            "ip_ref": "ip-csis-v8",
            "frame_width": 4000,
            "frame_height": 3000,
            "fps": 60.0,
            "unknown_field": "oops",
        })


def test_usecase_backward_compat_no_sensor():
    """기존 uc-camera-recording.yaml (sensor 없음)이 ValidationError 없이 파싱된다."""
    obj = roundtrip(Usecase, FIXTURES / "definition" / "uc-camera-recording.yaml")
    assert obj.sensor is None


# ---------------------------------------------------------------------------
# SCH-04: SimulationEvidence.dma_breakdown + timing_breakdown
# ---------------------------------------------------------------------------

def test_sim_evidence_backward_compat_no_breakdown():
    """기존 sim-*.yaml (dma_breakdown 없음)이 ValidationError 없이 파싱된다."""
    obj = roundtrip(
        SimulationEvidence,
        FIXTURES / "evidence" / "sim-camera-recording-UHD60-A0-sw123.yaml",
    )
    assert obj.dma_breakdown == []
    assert obj.timing_breakdown == []


def test_port_bw_result_roundtrip():
    """PortBWResult inline dict가 round-trip 직렬화를 통과한다."""
    raw = {
        "ip": "isp0",
        "port": "RDMA_FE",
        "direction": "read",
        "bw_mbs": 4800.0,
        "bw_power_mw": 384.0,
    }
    result = PortBWResult.model_validate(raw)
    assert result.llc_enabled is False
    assert result.bw_mbs_worst is None
    out = result.model_dump(exclude_none=True)
    result2 = PortBWResult.model_validate(out)
    assert result == result2


def test_ip_timing_result_roundtrip():
    """IPTimingResult inline dict가 round-trip 직렬화를 통과한다."""
    raw = {
        "ip": "isp0",
        "hw_time_ms": 16.67,
        "required_clock_mhz": 533.0,
        "set_clock_mhz": 533.0,
        "set_voltage_mv": 750.0,
        "feasible": True,
    }
    result = IPTimingResult.model_validate(raw)
    assert result.feasible is True
    out = result.model_dump(exclude_none=True)
    result2 = IPTimingResult.model_validate(out)
    assert result == result2


def test_port_bw_direction_invalid():
    """PortBWResult.direction이 'read'/'write' 외 값이면 ValidationError."""
    with pytest.raises(ValidationError):
        PortBWResult.model_validate({
            "ip": "isp0",
            "port": "RDMA_FE",
            "direction": "readwrite",
            "bw_mbs": 4800.0,
            "bw_power_mw": 384.0,
        })


def test_sim_evidence_with_breakdown_roundtrip():
    """dma_breakdown + timing_breakdown이 있는 fixture가 round-trip을 통과한다."""
    obj = roundtrip(
        SimulationEvidence,
        FIXTURES / "evidence" / "sim-FHD30-with-breakdown.yaml",
    )
    assert len(obj.dma_breakdown) >= 1
    assert len(obj.timing_breakdown) >= 1
    assert obj.dma_breakdown[0].ip == "isp0"
    assert obj.timing_breakdown[0].feasible is True
