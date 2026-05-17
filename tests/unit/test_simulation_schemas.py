"""Phase 7: Simulation API Pydantic 스키마 단위 테스트 (D-03, D-09, D-10, D-11)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from scenario_db.api.schemas.simulation import (
    BwAnalysisResponse,
    PowerAnalysisResponse,
    SimulateRequest,
    SimulateResponse,
    TimingAnalysisResponse,
)
from scenario_db.models.evidence.simulation import IPTimingResult, PortBWResult


# ---------------------------------------------------------------------------
# SimulateRequest
# ---------------------------------------------------------------------------

class TestSimulateRequest:
    """POST /run 요청 스키마 (D-03)."""

    def test_minimal_fields(self):
        """scenario_id + variant_id만으로 인스턴스 생성 가능."""
        req = SimulateRequest(scenario_id="sc-001", variant_id="var-a")
        assert req.scenario_id == "sc-001"
        assert req.variant_id == "var-a"

    def test_default_fps(self):
        """fps 기본값 30.0."""
        req = SimulateRequest(scenario_id="sc-001", variant_id="var-a")
        assert req.fps == 30.0

    def test_default_dvfs_overrides(self):
        """dvfs_overrides 기본값 None."""
        req = SimulateRequest(scenario_id="sc-001", variant_id="var-a")
        assert req.dvfs_overrides is None

    def test_default_asv_group(self):
        """asv_group 기본값 4."""
        req = SimulateRequest(scenario_id="sc-001", variant_id="var-a")
        assert req.asv_group == 4

    def test_extra_field_raises(self):
        """extra='forbid' — 알 수 없는 필드 전달 시 ValidationError."""
        with pytest.raises(ValidationError):
            SimulateRequest(scenario_id="sc-001", variant_id="var-a", unknown_field="x")

    def test_roundtrip(self):
        """model_dump() → model_validate() 라운드트립."""
        req = SimulateRequest(
            scenario_id="sc-001",
            variant_id="var-b",
            fps=60.0,
            dvfs_overrides={"isp": 3},
            asv_group=8,
        )
        data = req.model_dump()
        req2 = SimulateRequest.model_validate(data)
        assert req == req2

    def test_custom_values(self):
        """비기본값 필드 설정 검증."""
        req = SimulateRequest(
            scenario_id="sc-002",
            variant_id="var-c",
            fps=120.0,
            dvfs_overrides={"isp": 5, "mfc": 2},
            asv_group=8,
        )
        assert req.fps == 120.0
        assert req.dvfs_overrides == {"isp": 5, "mfc": 2}
        assert req.asv_group == 8


# ---------------------------------------------------------------------------
# SimulateResponse
# ---------------------------------------------------------------------------

class TestSimulateResponse:
    """POST /run 응답 스키마 (D-10)."""

    def _make(self, **kwargs) -> SimulateResponse:
        defaults = dict(
            evidence_id="evd-sim-abc12345",
            params_hash="a" * 64,
            cached=False,
            feasible=True,
            total_power_mw=1500.0,
            bw_total_mbs=8000.0,
            hw_time_max_ms=28.5,
        )
        defaults.update(kwargs)
        return SimulateResponse(**defaults)

    def test_all_fields(self):
        resp = self._make()
        assert resp.evidence_id == "evd-sim-abc12345"
        assert resp.params_hash == "a" * 64
        assert resp.cached is False
        assert resp.feasible is True
        assert resp.total_power_mw == 1500.0
        assert resp.bw_total_mbs == 8000.0
        assert resp.hw_time_max_ms == 28.5

    def test_cached_true(self):
        resp = self._make(cached=True)
        assert resp.cached is True

    def test_roundtrip(self):
        resp = self._make()
        data = resp.model_dump()
        resp2 = SimulateResponse.model_validate(data)
        assert resp == resp2

    def test_extra_field_raises(self):
        with pytest.raises(ValidationError):
            self._make(unexpected="bad")


# ---------------------------------------------------------------------------
# BwAnalysisResponse
# ---------------------------------------------------------------------------

class TestBwAnalysisResponse:
    """GET /bw-analysis 응답 스키마 (D-09, SAPI-03)."""

    def _port(self, bw_mbs: float = 1000.0) -> PortBWResult:
        return PortBWResult(
            ip="ISP",
            port="rd0",
            direction="read",
            bw_mbs=bw_mbs,
            bw_power_mw=50.0,
        )

    def test_empty_ports(self):
        resp = BwAnalysisResponse(
            evidence_id="evd-sim-001",
            ports=[],
            total_bw_mbs=0.0,
        )
        assert resp.ports == []
        assert resp.total_bw_mbs == 0.0

    def test_with_ports(self):
        ports = [self._port(1000.0), self._port(500.0)]
        resp = BwAnalysisResponse(
            evidence_id="evd-sim-001",
            ports=ports,
            total_bw_mbs=1500.0,
        )
        assert len(resp.ports) == 2
        assert resp.total_bw_mbs == 1500.0

    def test_roundtrip(self):
        resp = BwAnalysisResponse(
            evidence_id="evd-sim-001",
            ports=[self._port()],
            total_bw_mbs=1000.0,
        )
        data = resp.model_dump()
        resp2 = BwAnalysisResponse.model_validate(data)
        assert resp == resp2

    def test_extra_field_raises(self):
        with pytest.raises(ValidationError):
            BwAnalysisResponse(
                evidence_id="evd-sim-001",
                ports=[],
                total_bw_mbs=0.0,
                extra_field="bad",
            )


# ---------------------------------------------------------------------------
# PowerAnalysisResponse
# ---------------------------------------------------------------------------

class TestPowerAnalysisResponse:
    """GET /power-analysis 응답 스키마 (D-09, SAPI-04)."""

    def _make(self, **kwargs) -> PowerAnalysisResponse:
        defaults = dict(
            evidence_id="evd-sim-001",
            total_power_mw=2000.0,
            total_power_ma=500.0,
            per_ip={"ISP": 800.0, "MFC": 600.0},
            per_vdd={"vdd_cam": 900.0, "vdd_mfc": 700.0},
            bw_power_mw=100.0,
        )
        defaults.update(kwargs)
        return PowerAnalysisResponse(**defaults)

    def test_all_fields(self):
        resp = self._make()
        assert resp.evidence_id == "evd-sim-001"
        assert resp.total_power_mw == 2000.0
        assert resp.total_power_ma == 500.0
        assert resp.per_ip == {"ISP": 800.0, "MFC": 600.0}
        assert resp.per_vdd == {"vdd_cam": 900.0, "vdd_mfc": 700.0}
        assert resp.bw_power_mw == 100.0

    def test_roundtrip(self):
        resp = self._make()
        data = resp.model_dump()
        resp2 = PowerAnalysisResponse.model_validate(data)
        assert resp == resp2

    def test_extra_field_raises(self):
        with pytest.raises(ValidationError):
            self._make(bad="extra")


# ---------------------------------------------------------------------------
# TimingAnalysisResponse
# ---------------------------------------------------------------------------

class TestTimingAnalysisResponse:
    """GET /timing-analysis 응답 스키마 (D-09, SAPI-05)."""

    def _timing(self) -> IPTimingResult:
        return IPTimingResult(
            ip="ISP",
            hw_time_ms=25.0,
            required_clock_mhz=533.0,
            set_clock_mhz=600.0,
            set_voltage_mv=780,
            feasible=True,
        )

    def test_with_critical_ip(self):
        resp = TimingAnalysisResponse(
            evidence_id="evd-sim-001",
            feasible=True,
            hw_time_max_ms=25.0,
            critical_ip="ISP",
            per_ip=[self._timing()],
        )
        assert resp.critical_ip == "ISP"
        assert resp.feasible is True
        assert len(resp.per_ip) == 1

    def test_critical_ip_none(self):
        """critical_ip 가 None 허용."""
        resp = TimingAnalysisResponse(
            evidence_id="evd-sim-001",
            feasible=False,
            hw_time_max_ms=0.0,
            critical_ip=None,
            per_ip=[],
        )
        assert resp.critical_ip is None

    def test_roundtrip(self):
        resp = TimingAnalysisResponse(
            evidence_id="evd-sim-001",
            feasible=True,
            hw_time_max_ms=25.0,
            critical_ip="ISP",
            per_ip=[self._timing()],
        )
        data = resp.model_dump()
        resp2 = TimingAnalysisResponse.model_validate(data)
        assert resp == resp2

    def test_extra_field_raises(self):
        with pytest.raises(ValidationError):
            TimingAnalysisResponse(
                evidence_id="evd-sim-001",
                feasible=True,
                hw_time_max_ms=25.0,
                critical_ip=None,
                per_ip=[],
                bad="extra",
            )
