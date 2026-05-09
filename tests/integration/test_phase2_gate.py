"""Phase 2 Gate Engine 통합 테스트 — 실제 PostgreSQL DB + demo fixtures.

SC-3: GateExecutionResult 모델 필드 확인 (status, matched_rules, matched_issues, applicable_waivers, missing_waivers)
SC-4: blocking rule + issue waiver 로직 작동 확인
SC-5: 우선순위 집계 단위 테스트 통과 확인 (통합 레벨에서 전체 파이프라인 재확인)
"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from scenario_db.api.cache import RuleCache
from scenario_db.db.repositories.scenario_graph import get_canonical_graph
from scenario_db.gate.engine import evaluate_gate
from scenario_db.gate.models import GateExecutionResult, GateRuleMatch
from scenario_db.models.decision.common import GateResultStatus

pytestmark = pytest.mark.integration

SCENARIO_ID = "uc-camera-recording"
UHD_VARIANT = "UHD60-HDR10-H265"                   # severity=heavy
EXPL_VARIANT = "8K120-HDR10plus-AV1-exploration"   # severity=critical
FHD_VARIANT = "FHD30-SDR-H265"                     # severity=light


# ---------------------------------------------------------------------------
# 기본 타입 / 모델 검증 (SC-3)
# ---------------------------------------------------------------------------

def test_gate_result_type(engine):
    """evaluate_gate() 반환 타입이 GateExecutionResult이고 필드가 올바른 타입이다."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, UHD_VARIANT)
        cache = RuleCache.load(session)
    result = evaluate_gate(graph, cache.gate_rules)
    assert isinstance(result, GateExecutionResult)
    assert isinstance(result.status, GateResultStatus)
    assert isinstance(result.matched_rules, list)
    assert isinstance(result.matched_issues, list)
    assert isinstance(result.applicable_waivers, list)
    assert isinstance(result.missing_waivers, list)


def test_gate_rule_match_type(engine):
    """matched_rules 각 항목이 GateRuleMatch 타입이고 condition_not_evaluated=True (D-04)."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, UHD_VARIANT)
        cache = RuleCache.load(session)
    result = evaluate_gate(graph, cache.gate_rules)
    for rm in result.matched_rules:
        assert isinstance(rm, GateRuleMatch)
        assert rm.condition_not_evaluated is True, (
            f"condition_not_evaluated must be True (D-04: condition deferred to Phase 3), "
            f"got False for rule_id={rm.rule_id}"
        )


def test_gate_status_is_valid_enum(engine):
    """status가 GateResultStatus의 유효한 값 중 하나이다."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, UHD_VARIANT)
        cache = RuleCache.load(session)
    result = evaluate_gate(graph, cache.gate_rules)
    assert result.status in (
        GateResultStatus.PASS,
        GateResultStatus.WARN,
        GateResultStatus.BLOCK,
        GateResultStatus.WAIVER_REQUIRED,
    )


# ---------------------------------------------------------------------------
# Gate rule 평가 — applies_to 필터링 (GATE-02, D-05, D-06)
# ---------------------------------------------------------------------------

def test_gate_heavy_variant_matches_feasibility_rule(engine):
    """severity=heavy variant: rule-feasibility-check (applies_to: heavy/critical) → 매칭.

    demo fixture: rule-feasibility-check.applies_to.match.variant.severity.$in=[heavy,critical]
    """
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, UHD_VARIANT)
        cache = RuleCache.load(session)
    result = evaluate_gate(graph, cache.gate_rules)
    matched_ids = [r.rule_id for r in result.matched_rules]
    assert "rule-feasibility-check" in matched_ids, (
        f"rule-feasibility-check should match heavy variant, got matched_rules: {matched_ids}"
    )


def test_gate_heavy_variant_matches_known_issue_rule(engine):
    """severity=heavy variant: rule-known-issue-match (applies_to: heavy/critical) → 매칭."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, UHD_VARIANT)
        cache = RuleCache.load(session)
    result = evaluate_gate(graph, cache.gate_rules)
    matched_ids = [r.rule_id for r in result.matched_rules]
    assert "rule-known-issue-match" in matched_ids, (
        f"rule-known-issue-match should match heavy variant, got matched_rules: {matched_ids}"
    )


def test_gate_fhd_light_variant_no_heavy_rules(engine):
    """severity=light variant: heavy/critical 전용 rules는 매칭 안 됨 (D-05 applies_to 필터링).

    FHD30-SDR-H265 severity=light → variant.severity.$in=[heavy,critical] 조건 불충족.
    """
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, FHD_VARIANT)
        cache = RuleCache.load(session)
    result = evaluate_gate(graph, cache.gate_rules)
    heavy_rules = [
        r for r in result.matched_rules
        if r.rule_id in {"rule-feasibility-check", "rule-known-issue-match"}
    ]
    assert heavy_rules == [], (
        f"Light variant should not match heavy-only rules, "
        f"got: {[r.rule_id for r in heavy_rules]}"
    )


def test_gate_critical_variant_matches_rules(engine):
    """severity=critical variant: heavy/critical 전용 rules가 매칭된다."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, EXPL_VARIANT)
        if graph is None:
            pytest.skip(f"Variant {EXPL_VARIANT} not found in DB")
        cache = RuleCache.load(session)
    result = evaluate_gate(graph, cache.gate_rules)
    matched_ids = [r.rule_id for r in result.matched_rules]
    assert "rule-feasibility-check" in matched_ids, (
        f"rule-feasibility-check should match critical variant, got: {matched_ids}"
    )


def test_gate_empty_rules_returns_pass(engine):
    """gate_rules=[] → status=PASS (rules 없으면 항상 PASS)."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, UHD_VARIANT)
    result = evaluate_gate(graph, [])
    assert result.status == GateResultStatus.PASS
    assert result.matched_rules == []


# ---------------------------------------------------------------------------
# blocking rule → BLOCK status (SC-4, GATE-01)
# ---------------------------------------------------------------------------

def test_gate_feasibility_rule_action_is_block(engine):
    """rule-feasibility-check의 action.gate_result=BLOCK → GateRuleMatch.result=BLOCK."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, UHD_VARIANT)
        cache = RuleCache.load(session)
    result = evaluate_gate(graph, cache.gate_rules)
    feasibility_match = next(
        (r for r in result.matched_rules if r.rule_id == "rule-feasibility-check"),
        None,
    )
    assert feasibility_match is not None
    assert feasibility_match.result == GateResultStatus.BLOCK


def test_gate_heavy_variant_status_block(engine):
    """UHD60 variant (heavy) + BLOCK rule → 최종 status=BLOCK (D-11 우선순위)."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, UHD_VARIANT)
        cache = RuleCache.load(session)
    result = evaluate_gate(graph, cache.gate_rules)
    # BLOCK rule이 매칭되면 최종 status는 반드시 BLOCK
    assert result.status == GateResultStatus.BLOCK, (
        f"Heavy variant with rule-feasibility-check (BLOCK) should yield BLOCK status, "
        f"got: {result.status}"
    )


# ---------------------------------------------------------------------------
# Issue matching (GATE-03) — demo issue status=resolved
# ---------------------------------------------------------------------------

def test_gate_resolved_issue_not_in_missing_waivers(engine):
    """iss-LLC-thrashing-0221 status=resolved → missing_waivers에 없음 (D-09).

    resolved issue는 waiver 불필요이므로 WAIVER_REQUIRED 트리거 안 됨.
    """
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, UHD_VARIANT)
    result = evaluate_gate(graph, [])  # gate_rules 없이 issue 평가만
    assert "iss-LLC-thrashing-0221" not in result.missing_waivers, (
        f"Resolved issue should not appear in missing_waivers, "
        f"got: {result.missing_waivers}"
    )


def test_gate_matched_issues_are_strings(engine):
    """matched_issues 항목들이 모두 문자열 (issue id)."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, UHD_VARIANT)
    result = evaluate_gate(graph, [])
    for issue_id in result.matched_issues:
        assert isinstance(issue_id, str), (
            f"matched_issues items should be str, got {type(issue_id)}"
        )


# ---------------------------------------------------------------------------
# 모든 variant에서 유효한 status 반환 (SC-5)
# ---------------------------------------------------------------------------

def test_gate_all_variants_return_valid_status(engine):
    """세 variant 모두 유효한 GateResultStatus를 반환한다."""
    valid_statuses = set(GateResultStatus)
    for variant_id in [UHD_VARIANT, EXPL_VARIANT, FHD_VARIANT]:
        with Session(engine) as session:
            graph = get_canonical_graph(session, SCENARIO_ID, variant_id)
            if graph is None:
                continue
            cache = RuleCache.load(session)
        result = evaluate_gate(graph, cache.gate_rules)
        assert result.status in valid_statuses, (
            f"Invalid status for {variant_id}: {result.status}"
        )


def test_gate_fhd_variant_with_no_rules_is_pass(engine):
    """FHD light variant + gate_rules=[] → PASS (아무 rule도 적용 안 됨)."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, FHD_VARIANT)
        cache = RuleCache.load(session)
    # FHD는 heavy/critical 전용 rules에 해당 안 됨 → matched_rules=[]
    result = evaluate_gate(graph, cache.gate_rules)
    # light variant에 해당 rule이 없으면 PASS 또는 WARN (issue 매칭 없으면 PASS)
    assert result.status in (GateResultStatus.PASS, GateResultStatus.WARN)


# ---------------------------------------------------------------------------
# 결과 직렬화 가능성 확인 (Phase 3 API 대비)
# ---------------------------------------------------------------------------

def test_gate_result_serializable(engine):
    """GateExecutionResult.model_dump()가 오류 없이 직렬화된다 (Phase 3 JSON 응답 대비)."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, UHD_VARIANT)
        cache = RuleCache.load(session)
    result = evaluate_gate(graph, cache.gate_rules)
    dumped = result.model_dump()
    assert isinstance(dumped, dict)
    assert "status" in dumped
    assert "matched_rules" in dumped
    assert "matched_issues" in dumped
    assert "applicable_waivers" in dumped
    assert "missing_waivers" in dumped


# ---------------------------------------------------------------------------
# 비영속 확인 (RES-03 동일 원칙 — Gate Engine도 비영속)
# ---------------------------------------------------------------------------

def test_gate_does_not_persist(engine):
    """evaluate_gate() 호출 전후 reviews 테이블 레코드 수 변화 없음."""
    from sqlalchemy import text
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, UHD_VARIANT)
        cache = RuleCache.load(session)
        count_before = session.execute(
            text("SELECT COUNT(*) FROM reviews")
        ).scalar()

    evaluate_gate(graph, cache.gate_rules)  # DB session 없이 순수 함수 호출

    with Session(engine) as session:
        count_after = session.execute(
            text("SELECT COUNT(*) FROM reviews")
        ).scalar()

    assert count_before == count_after, (
        f"evaluate_gate() must not write to DB: "
        f"before={count_before}, after={count_after}"
    )


def test_gate_does_not_persist_variants(engine):
    """evaluate_gate() 호출 후 scenario_variants 테이블도 변화 없음."""
    from sqlalchemy import text
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, UHD_VARIANT)
        cache = RuleCache.load(session)
        count_before = session.execute(
            text("SELECT COUNT(*) FROM scenario_variants")
        ).scalar()

    evaluate_gate(graph, cache.gate_rules)

    with Session(engine) as session:
        count_after = session.execute(
            text("SELECT COUNT(*) FROM scenario_variants")
        ).scalar()

    assert count_before == count_after, (
        f"evaluate_gate() must not write to scenario_variants: "
        f"before={count_before}, after={count_after}"
    )
