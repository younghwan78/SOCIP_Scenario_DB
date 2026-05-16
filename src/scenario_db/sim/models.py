from __future__ import annotations

from pydantic import Field

from scenario_db.models.common import BaseScenarioModel

# D-01: 단일 정의 원칙 — evidence layer 모델을 복제하면 Phase 7 타입 불일치
from scenario_db.models.evidence.simulation import IPTimingResult, PortBWResult

__all__ = [
    "PortBWResult",       # re-export
    "IPTimingResult",     # re-export
    "ResolvedIPConfig",
    "DVFSLevel",
    "DVFSTable",
    "SimRunResult",
]


class ResolvedIPConfig(BaseScenarioModel):
    """DVFS resolve 결과 — 단일 IP의 최종 클럭/전압 설정."""
    ip_name: str
    required_clock_mhz: float
    set_clock_mhz: float
    set_voltage_mv: float
    dvfs_group: str
    vdd: str


class DVFSLevel(BaseScenarioModel):
    """DVFS 테이블의 단일 레벨 엔트리."""
    level: int
    speed_mhz: float
    voltages: dict[int, float]   # asv_group -> voltage_mv (예: {0: 820, 4: 780, 8: 750})


class DVFSTable(BaseScenarioModel):
    """단일 VDD 도메인의 DVFS 레벨 목록."""
    domain: str
    levels: list[DVFSLevel] = Field(default_factory=list)

    def find_min_level(self, required_clock_mhz: float, asv_group: int = 4) -> DVFSLevel | None:
        """required_clock_mhz 이상을 처리할 수 있는 최소(가장 낮은 speed) 레벨 반환.

        levels는 speed_mhz 내림차순 정렬 가정 (level 0 = 최고속).
        required를 충족하는 가장 낮은 speed 레벨 = 가장 높은 level 번호.
        """
        eligible = [lv for lv in self.levels if lv.speed_mhz >= required_clock_mhz]
        if not eligible:
            return None
        # speed가 가장 작은 것 (level 번호가 가장 큰 것) 선택 → 전력 최소화
        return min(eligible, key=lambda lv: lv.speed_mhz)


class SimRunResult(BaseScenarioModel):
    """전체 시뮬레이션 파이프라인 실행 결과."""
    scenario_id: str
    variant_id: str
    total_power_mw: float
    total_power_ma: float        # mA = total_power_mw / (vbat * pmic_eff * 1000) * 1000
    bw_total_mbs: float          # sum(dma_breakdown[].bw_mbs)
    hw_time_max_ms: float        # max(timing_breakdown[].hw_time_ms)
    feasible: bool               # hw_time_max_ms <= (1000.0 / fps)
    infeasible_reason: str | None = None
    resolved: dict[str, ResolvedIPConfig] = Field(default_factory=dict)   # node_id -> ResolvedIPConfig
    dma_breakdown: list[PortBWResult] = Field(default_factory=list)
    timing_breakdown: list[IPTimingResult] = Field(default_factory=list)
    vdd_power: dict[str, float] = Field(default_factory=dict)             # VDD domain -> total mW
