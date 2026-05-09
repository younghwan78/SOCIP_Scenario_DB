"""Gate 실행 엔진 (GATE-01~GATE-05).

evaluate_gate(graph, gate_rules) — 순수 함수 (D-07).
DB 쿼리 없음. Phase 3 라우터가 RuleCache에서 gate_rules를 주입.

결정 사항:
- D-04: condition.match 평가 생략 — evidence 데이터 참조 → Phase 3
- D-05: applies_to.match → gate/dsl.py의 evaluate_applies_to() 사용
- D-06: applies_to=None → 모든 variant에 적용
- D-07: 순수 함수 — Session/SQLAlchemy 의존성 없음
- D-08: Resolver와 독립 — matched_issues는 graph.issues에서 직접
- D-09: open/deferred issue + waiver 없음 → WAIVER_REQUIRED
- D-10: variant_scope 평가 (matcher.runner.evaluate 재사용), execution_scope 스킵
- D-11: BLOCK > WAIVER_REQUIRED > WARN > PASS
"""
from __future__ import annotations

from scenario_db.api.schemas.decision import GateRuleResponse
from scenario_db.db.repositories.scenario_graph import (
    CanonicalScenarioGraph,
    IssueRecord,
    VariantRecord,
    WaiverRecord,
)
from scenario_db.gate.dsl import evaluate_applies_to
from scenario_db.gate.models import GateExecutionResult, GateRuleMatch
from scenario_db.matcher.context import MatcherContext
from scenario_db.matcher.runner import evaluate
from scenario_db.models.decision.common import GateResultStatus

# issue.metadata_.status 값 중 WAIVER_REQUIRED 트리거 대상 (D-09)
_WAIVER_REQUIRED_STATUSES = frozenset({"open", "deferred"})


def evaluate_gate(
    graph: CanonicalScenarioGraph,
    gate_rules: list[GateRuleResponse],
) -> GateExecutionResult:
    """gate_rules를 CanonicalScenarioGraph에 평가하여 GateExecutionResult를 반환 (D-07).

    DB 쿼리 없음 — 순수 함수. Phase 3 라우터가 RuleCache에서 gate_rules를 주입.
    D-04: condition.match 평가 생략 (evidence 데이터 참조 → Phase 3).
    D-08: Resolver와 독립 — matched_issues는 graph.issues에서 직접.
    """
    # 1. GateRule 평가 — applies_to.match로 rule 적용 여부 판단
    matched_rules: list[GateRuleMatch] = []
    for rule in gate_rules:
        if _rule_applies_to_variant(rule, graph.variant):
            result_str = (rule.action or {}).get("gate_result", "PASS")
            try:
                result = GateResultStatus(result_str)
            except ValueError:
                result = GateResultStatus.WARN  # 알 수 없는 값 → WARN으로 강등 (T-02-05)
            message = (rule.action or {}).get("message_template")
            matched_rules.append(GateRuleMatch(
                rule_id=rule.id,
                result=result,
                message=message,
                condition_not_evaluated=True,  # D-04: condition evaluation deferred to Phase 3
            ))

    # 2. Issue matching — variant context로 graph.issues 필터링 (D-08)
    ctx = MatcherContext(
        design_conditions=graph.variant.design_conditions,
        ip_requirements=graph.variant.ip_requirements,
        sw_requirements=graph.variant.sw_requirements,
    )
    matched_issues = _match_issues_for_variant(graph.issues, ctx, graph.scenario_id)
    matched_issue_ids = [iss.id for iss in matched_issues]

    # 3. Waiver applicability 평가 (D-09, D-10)
    applicable_waivers: list[str] = []
    missing_waivers: list[str] = []

    for issue in matched_issues:
        status = (issue.metadata_ or {}).get("status")
        if status not in _WAIVER_REQUIRED_STATUSES:
            continue  # resolved/wontfix — waiver 불필요 (D-09)

        issue_waivers = [w for w in graph.waivers if w.issue_ref == issue.id]
        applicable = [
            w for w in issue_waivers
            if _waiver_applicable(w, graph.scenario_id, ctx)
        ]

        if applicable:
            for w in applicable:
                if w.id not in applicable_waivers:
                    applicable_waivers.append(w.id)
        else:
            missing_waivers.append(issue.id)

    # 4. 최종 status 집계 (D-11: BLOCK > WAIVER_REQUIRED > WARN > PASS)
    status = _aggregate_status(matched_rules, missing_waivers)

    return GateExecutionResult(
        status=status,
        matched_rules=matched_rules,
        matched_issues=matched_issue_ids,
        applicable_waivers=applicable_waivers,
        missing_waivers=missing_waivers,
    )


def _rule_applies_to_variant(rule: GateRuleResponse, variant: VariantRecord) -> bool:
    """applies_to.match DSL로 rule 적용 여부 판단 (D-05, D-06)."""
    applies_to = rule.applies_to  # dict | None
    if not applies_to:
        return True  # D-06: applies_to=None → 모든 variant에 적용
    match = applies_to.get("match") if isinstance(applies_to, dict) else None
    if not match:
        return True
    return evaluate_applies_to(match, variant)


def _match_issues_for_variant(
    issues: list[IssueRecord],
    ctx: MatcherContext,
    scenario_id: str,
) -> list[IssueRecord]:
    """Issue.affects match_rule을 variant context에 평가하여 매칭 issue 반환 (D-08)."""
    matched: list[IssueRecord] = []
    for issue in issues:
        affects = issue.affects
        if not affects:
            continue
        for affect in affects:
            if not isinstance(affect, dict):
                continue
            ref = affect.get("scenario_ref", "*")
            if ref != "*" and ref != scenario_id:
                continue
            match_rule = affect.get("match_rule")
            if not match_rule:
                matched.append(issue)
                break
            if evaluate(match_rule, ctx):
                matched.append(issue)
                break
    return matched


def _waiver_applicable(
    waiver: WaiverRecord,
    scenario_id: str,
    ctx: MatcherContext,
) -> bool:
    """Waiver variant_scope가 현재 variant에 적용 가능한지 판단 (D-10).

    execution_scope는 Phase 3에서 평가 — condition evaluation deferred to Phase 3.
    """
    scope = waiver.scope or {}
    variant_scope = scope.get("variant_scope")
    if not variant_scope or not isinstance(variant_scope, dict):
        return True  # variant_scope 없으면 unconditional

    # scenario_ref 체크
    scenario_ref = variant_scope.get("scenario_ref", "*")
    if scenario_ref != "*" and scenario_ref != scenario_id:
        return False

    # match_rule 체크 — matcher.runner.evaluate() 재사용
    match_rule = variant_scope.get("match_rule")
    if not match_rule:
        return True
    return evaluate(match_rule, ctx)


def _aggregate_status(
    matched_rules: list[GateRuleMatch],
    missing_waivers: list[str],
) -> GateResultStatus:
    """D-11: BLOCK > WAIVER_REQUIRED > WARN > PASS."""
    if any(r.result == GateResultStatus.BLOCK for r in matched_rules):
        return GateResultStatus.BLOCK
    if missing_waivers:
        return GateResultStatus.WAIVER_REQUIRED
    if any(r.result == GateResultStatus.WARN for r in matched_rules):
        return GateResultStatus.WARN
    return GateResultStatus.PASS
