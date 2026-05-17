"""Simulation Evidence DB 저장/조회 (D-08, D-02, SAPI-06)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from scenario_db.api.schemas.simulation import SimulateRequest
from scenario_db.db.models.evidence import Evidence
from scenario_db.sim.models import SimRunResult


def save_sim_evidence(
    db: Session,
    evidence_id: str,
    req: SimulateRequest,
    result: SimRunResult,
    params_hash: str,
) -> Evidence:
    """SimRunResult를 Evidence ORM row로 변환하여 DB에 저장한다 (D-08).

    yaml_sha256 = params_hash (YAML 파일 없는 simulation evidence 한정).
    """
    row = Evidence(
        id=evidence_id,
        schema_version="0.1.0",
        kind="evidence.simulation",
        scenario_ref=req.scenario_id,
        variant_ref=req.variant_id,
        execution_context={
            "silicon_rev": "api-sim",
            "sw_baseline_ref": "n/a",
            "thermal": "nominal",
        },
        aggregation={"strategy": "single"},
        kpi={
            "total_power_mw": result.total_power_mw,
            "total_power_ma": result.total_power_ma,
            "bw_total_mbs": result.bw_total_mbs,
            "hw_time_max_ms": result.hw_time_max_ms,
            "feasible": result.feasible,  # bool — JSONB에 boolean으로 저장
        },
        run_info={
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "tool": "scenario_db.sim.runner",
            "source": "simulated",
        },
        dma_breakdown=[r.model_dump() for r in result.dma_breakdown],
        timing_breakdown=[t.model_dump() for t in result.timing_breakdown],
        ip_breakdown={
            "vdd_power": result.vdd_power,
            "ip_power": result.ip_power,    # D-06: IP별 active power 저장
        },
        overall_feasibility="feasible" if result.feasible else "infeasible",
        yaml_sha256=params_hash,
        params_hash=params_hash,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def find_by_params_hash(db: Session, params_hash: str) -> Evidence | None:
    """params_hash + kind='evidence.simulation' 으로 최신 Evidence 조회 (D-02, SAPI-06).

    동일 params_hash 행이 여러 개일 경우 id 내림차순(가장 최근 생성) 반환.
    """
    return (
        db.query(Evidence)
        .filter(
            Evidence.params_hash == params_hash,
            Evidence.kind == "evidence.simulation",
        )
        .order_by(Evidence.id.desc())
        .first()
    )
