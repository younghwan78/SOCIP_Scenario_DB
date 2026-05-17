"""Phase 7 — /simulation/ 라우터 (SAPI-01~06).

엔드포인트:
  POST /simulation/run                         — 동기 계산 + 캐싱 (D-02)
  GET  /simulation/results/{evidence_id}       — Evidence 상세 조회
  GET  /simulation/bw-analysis                 — BW 분석 (bw_mbs 내림차순)
  GET  /simulation/power-analysis              — Power 분석 (IP별/VDD별)
  GET  /simulation/timing-analysis             — Timing 분석 (critical IP)
"""
from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from scenario_db.api.deps import get_db
from scenario_db.api.schemas.simulation import (
    BwAnalysisResponse,
    PowerAnalysisResponse,
    SimulateRequest,
    SimulateResponse,
    TimingAnalysisResponse,
)
from scenario_db.db.loaders import (
    apply_request_overrides,
    compute_params_hash,
    load_runner_inputs_from_db,
)
from scenario_db.db.repositories.evidence import get_evidence
from scenario_db.db.repositories.simulation import find_by_params_hash, save_sim_evidence
from scenario_db.models.evidence.simulation import IPTimingResult, PortBWResult
from scenario_db.sim.runner import run_simulation

router = APIRouter(tags=["simulation"])


@router.post("/simulation/run", response_model=SimulateResponse, status_code=200)
def run_sim(
    req: SimulateRequest,
    db: Session = Depends(get_db),
) -> SimulateResponse:
    """SimulateRequest → 동기 계산 → SimulationEvidence 저장 + 캐시 히트 처리 (SAPI-01, SAPI-06).

    Flow:
      1. params_hash 계산
      2. cache 조회 — HIT이면 즉시 반환 (cached=True)
      3. DB에서 runner 입력 로드
      4. run_simulation() 호출
      5. Evidence 저장
      6. SimulateResponse 반환 (cached=False)
    """
    params_hash = compute_params_hash(req)

    # SAPI-06: 캐시 HIT 확인
    cached_row = find_by_params_hash(db, params_hash)
    if cached_row is not None:
        kpi = cached_row.kpi or {}
        return SimulateResponse(
            evidence_id=cached_row.id,
            params_hash=params_hash,
            cached=True,
            feasible=bool(kpi.get("feasible", False)),
            total_power_mw=float(kpi.get("total_power_mw", 0.0)),
            bw_total_mbs=float(kpi.get("bw_total_mbs", 0.0)),
            hw_time_max_ms=float(kpi.get("hw_time_max_ms", 0.0)),
        )

    # D-07: DB → runner 입력 변환
    inputs = load_runner_inputs_from_db(db, req.scenario_id, req.variant_id)
    if inputs is None:
        raise HTTPException(
            status_code=404,
            detail=f"scenario '{req.scenario_id}' or variant '{req.variant_id}' not found",
        )

    pipeline, ip_catalog, dvfs_tables, variant_port_config, sim_config, sensor_spec = inputs

    # D-03: request override 적용 (dvfs_overrides, asv_group)
    sim_config = apply_request_overrides(sim_config, req)

    # D-09: 계산 실행
    result = run_simulation(
        scenario_id=req.scenario_id,
        variant_id=req.variant_id,
        pipeline=pipeline,
        ip_catalog=ip_catalog,
        dvfs_tables=dvfs_tables,
        variant_port_config=variant_port_config,
        sim_config=sim_config,
        sensor_spec=sensor_spec,
        fps=req.fps,
    )

    # D-04: evidence_id 자동 생성
    evidence_id = f"evd-sim-{uuid4().hex[:8]}"

    # D-08: Evidence 저장
    save_sim_evidence(db, evidence_id, req, result, params_hash)

    return SimulateResponse(
        evidence_id=evidence_id,
        params_hash=params_hash,
        cached=False,
        feasible=result.feasible,
        total_power_mw=result.total_power_mw,
        bw_total_mbs=result.bw_total_mbs,
        hw_time_max_ms=result.hw_time_max_ms,
    )


@router.get(
    "/simulation/results/{evidence_id}",
    response_model=None,  # Evidence raw dict 반환
)
def get_sim_result(
    evidence_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """SimulationEvidence 상세 반환 — dma_breakdown + timing_breakdown 포함 (SAPI-02).

    response_model=None: Evidence ORM → raw dict (기존 evidence 라우터 패턴 동일).
    """
    row = get_evidence(db, evidence_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"evidence '{evidence_id}' not found")
    return {
        "id": row.id,
        "kind": row.kind,
        "schema_version": row.schema_version,
        "scenario_ref": row.scenario_ref,
        "variant_ref": row.variant_ref,
        "overall_feasibility": row.overall_feasibility,
        "kpi": row.kpi,
        "dma_breakdown": row.dma_breakdown or [],
        "timing_breakdown": row.timing_breakdown or [],
        "ip_breakdown": row.ip_breakdown or {},
        "params_hash": row.params_hash,
    }


@router.get("/simulation/bw-analysis", response_model=BwAnalysisResponse)
def get_bw_analysis(
    evidence_id: str = Query(..., description="Evidence ID"),
    db: Session = Depends(get_db),
) -> BwAnalysisResponse:
    """PortBWResult 목록을 bw_mbs 내림차순으로 반환 (SAPI-03, D-05)."""
    row = get_evidence(db, evidence_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"evidence '{evidence_id}' not found")

    raw_ports: list[dict] = row.dma_breakdown or []
    ports = [PortBWResult.model_validate(p) for p in raw_ports]
    ports_sorted = sorted(ports, key=lambda p: p.bw_mbs, reverse=True)
    total_bw_mbs = sum(p.bw_mbs for p in ports_sorted)

    return BwAnalysisResponse(
        evidence_id=evidence_id,
        ports=ports_sorted,
        total_bw_mbs=total_bw_mbs,
    )


@router.get("/simulation/power-analysis", response_model=PowerAnalysisResponse)
def get_power_analysis(
    evidence_id: str = Query(..., description="Evidence ID"),
    db: Session = Depends(get_db),
) -> PowerAnalysisResponse:
    """total_power/per_ip/per_vdd/bw_power 반환 (SAPI-04, D-05, D-09).

    per_ip: ip_breakdown.ip_power (D-06 — runner.py Step 5에서 수집)
    per_vdd: ip_breakdown.vdd_power
    bw_power_mw: sum(dma_breakdown[].bw_power_mw)
    """
    row = get_evidence(db, evidence_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"evidence '{evidence_id}' not found")

    kpi: dict = row.kpi or {}
    ip_breakdown: dict = row.ip_breakdown or {}
    raw_ports: list[dict] = row.dma_breakdown or []

    per_ip: dict[str, float] = ip_breakdown.get("ip_power", {})
    per_vdd: dict[str, float] = ip_breakdown.get("vdd_power", {})
    bw_power_mw = sum(float(p.get("bw_power_mw", 0.0)) for p in raw_ports)

    return PowerAnalysisResponse(
        evidence_id=evidence_id,
        total_power_mw=float(kpi.get("total_power_mw", 0.0)),
        total_power_ma=float(kpi.get("total_power_ma", 0.0)),
        per_ip=per_ip,
        per_vdd=per_vdd,
        bw_power_mw=bw_power_mw,
    )


@router.get("/simulation/timing-analysis", response_model=TimingAnalysisResponse)
def get_timing_analysis(
    evidence_id: str = Query(..., description="Evidence ID"),
    db: Session = Depends(get_db),
) -> TimingAnalysisResponse:
    """critical_ip/hw_time_max_ms/per_ip/feasible 반환 (SAPI-05, D-05, D-09).

    per_ip: timing_breakdown — hw_time_ms 내림차순
    critical_ip: hw_time_ms 최대 IP 이름
    """
    row = get_evidence(db, evidence_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"evidence '{evidence_id}' not found")

    kpi: dict = row.kpi or {}
    raw_timing: list[dict] = row.timing_breakdown or []

    timing_results = [IPTimingResult.model_validate(t) for t in raw_timing]
    timing_sorted = sorted(timing_results, key=lambda t: t.hw_time_ms, reverse=True)
    critical_ip: str | None = timing_sorted[0].ip if timing_sorted else None

    return TimingAnalysisResponse(
        evidence_id=evidence_id,
        feasible=bool(kpi.get("feasible", False)),
        hw_time_max_ms=float(kpi.get("hw_time_max_ms", 0.0)),
        critical_ip=critical_ip,
        per_ip=timing_sorted,
    )
