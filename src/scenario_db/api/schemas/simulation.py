"""Phase 7 Simulation API — 요청/응답 Pydantic 스키마 (D-03, D-09, D-10)."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

# D-01: 단일 정의 원칙 — evidence layer 모델을 복제하면 Phase 7 타입 불일치
from scenario_db.models.evidence.simulation import IPTimingResult, PortBWResult


class SimulateRequest(BaseModel):
    """POST /api/v1/simulation/run 요청 스키마 (D-03)."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    variant_id: str
    fps: float = 30.0
    dvfs_overrides: dict[str, int] | None = None   # node_id → DVFS level override
    asv_group: int = 4


class SimulateResponse(BaseModel):
    """POST /api/v1/simulation/run 응답 스키마 (D-10)."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    params_hash: str
    cached: bool          # True = 재계산 없이 캐시 HIT
    feasible: bool
    total_power_mw: float
    bw_total_mbs: float
    hw_time_max_ms: float


class BwAnalysisResponse(BaseModel):
    """GET /api/v1/simulation/bw-analysis 응답 스키마 (D-09, SAPI-03)."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    ports: list[PortBWResult]   # bw_mbs 내림차순 정렬 (라우터에서 정렬)
    total_bw_mbs: float


class PowerAnalysisResponse(BaseModel):
    """GET /api/v1/simulation/power-analysis 응답 스키마 (D-09, SAPI-04)."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    total_power_mw: float
    total_power_ma: float
    per_ip: dict[str, float]    # ip_name → active_power_mw
    per_vdd: dict[str, float]   # vdd_domain → total_power_mw
    bw_power_mw: float          # sum(dma_breakdown[].bw_power_mw)


class TimingAnalysisResponse(BaseModel):
    """GET /api/v1/simulation/timing-analysis 응답 스키마 (D-09, SAPI-05)."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    feasible: bool
    hw_time_max_ms: float
    critical_ip: str | None     # hw_time_ms 최대 IP (per_ip가 비어있으면 None)
    per_ip: list[IPTimingResult]  # hw_time_ms 내림차순 정렬 (라우터에서 정렬)
