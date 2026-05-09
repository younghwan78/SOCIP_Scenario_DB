from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from scenario_db.api.cache import RuleCache
from scenario_db.api.deps import get_db, get_rule_cache
from scenario_db.db.repositories.scenario_graph import (
    CanonicalScenarioGraph,
    get_canonical_graph,
)
from scenario_db.gate.engine import evaluate_gate
from scenario_db.gate.models import GateExecutionResult
from scenario_db.resolver.engine import resolve
from scenario_db.resolver.models import ResolverResult

router = APIRouter(tags=["runtime"])


@router.get(
    "/scenarios/{scenario_id}/variants/{variant_id}/graph",
    response_model=CanonicalScenarioGraph,
)
def get_graph(
    scenario_id: str,
    variant_id: str,
    db: Session = Depends(get_db),
) -> CanonicalScenarioGraph:
    """CanonicalScenarioGraph DTO 반환 — DB에서 scenario 전체 그래프 조회."""
    graph = get_canonical_graph(db, scenario_id, variant_id)
    if graph is None:
        raise HTTPException(
            status_code=404,
            detail=f"scenario '{scenario_id}' / variant '{variant_id}' not found",
        )
    return graph


@router.get(
    "/scenarios/{scenario_id}/variants/{variant_id}/resolve",
    response_model=ResolverResult,
)
def get_resolve(
    scenario_id: str,
    variant_id: str,
    db: Session = Depends(get_db),
) -> ResolverResult:
    """Resolver 실행 결과 반환 — variant.ip_requirements → ip_catalog.capabilities 매핑."""
    graph = get_canonical_graph(db, scenario_id, variant_id)
    if graph is None:
        raise HTTPException(
            status_code=404,
            detail=f"scenario '{scenario_id}' / variant '{variant_id}' not found",
        )
    return resolve(graph)


@router.get(
    "/scenarios/{scenario_id}/variants/{variant_id}/gate",
    response_model=GateExecutionResult,
)
def get_gate(
    scenario_id: str,
    variant_id: str,
    db: Session = Depends(get_db),
    cache: RuleCache = Depends(get_rule_cache),
) -> GateExecutionResult:
    """Gate 평가 결과 반환 — GateExecutionResult (PASS/WARN/BLOCK/WAIVER_REQUIRED).

    D-05: cache.gate_rules가 빈 리스트여도 503 없이 evaluate_gate(graph, []) 호출 → status=PASS.
    """
    graph = get_canonical_graph(db, scenario_id, variant_id)
    if graph is None:
        raise HTTPException(
            status_code=404,
            detail=f"scenario '{scenario_id}' / variant '{variant_id}' not found",
        )
    return evaluate_gate(graph, cache.gate_rules)
