from __future__ import annotations

import pytest

from scenario_db.api.schemas.decision import GateRuleResponse
from scenario_db.db.repositories.scenario_graph import (
    CanonicalScenarioGraph,
    IssueRecord,
    ScenarioRecord,
    VariantRecord,
    WaiverRecord,
)
from scenario_db.gate.engine import _aggregate_status, evaluate_gate
from scenario_db.gate.models import GateExecutionResult, GateRuleMatch
from scenario_db.models.decision.common import GateResultStatus


# ---------------------------------------------------------------------------
# 헬퍼 함수
# ---------------------------------------------------------------------------

def _make_graph(
    variant_severity: str | None = "heavy",
    variant_design_conditions: dict | None = None,
    issues: list[IssueRecord] | None = None,
    waivers: list[WaiverRecord] | None = None,
) -> CanonicalScenarioGraph:
    return CanonicalScenarioGraph(
        scenario_id="uc-camera-recording",
        variant_id="UHD60-HDR10-H265",
        scenario=ScenarioRecord(
            id="uc-camera-recording", schema_version="2.2",
            project_ref="proj-A", metadata_={"name": "test"},
            pipeline={"nodes": []}, yaml_sha256="abc",
        ),
        variant=VariantRecord(
            scenario_id="uc-camera-recording", id="UHD60-HDR10-H265",
            severity=variant_severity,
            design_conditions=variant_design_conditions or {"resolution": "UHD", "fps": 60},
        ),
        pipeline={"nodes": []},
        ip_catalog={}, sw_profiles={}, evidence=[],
        issues=issues or [],
        waivers=waivers or [],
        reviews=[],
    )


def _make_rule(
    rule_id: str,
    gate_result: str = "PASS",
    applies_to: dict | None = None,
) -> GateRuleResponse:
    return GateRuleResponse(
        id=rule_id,
        schema_version="2.2",
        metadata_={"name": rule_id},
        trigger={"events": ["on_evidence_register"]},
        applies_to=applies_to,
        condition={"match": None},
        action={"gate_result": gate_result, "message_template": f"{rule_id} triggered"},
    )


def _make_issue(
    issue_id: str,
    status: str = "open",
    scenario_ref: str = "uc-camera-recording",
    match_rule: dict | None = None,
) -> IssueRecord:
    affects_entry: dict = {"scenario_ref": scenario_ref}
    if match_rule:
        affects_entry["match_rule"] = match_rule
    return IssueRecord(
        id=issue_id,
        schema_version="2.2",
        metadata_={"status": status, "title": f"Issue {issue_id}", "severity": "heavy"},
        affects=[affects_entry],
        yaml_sha256="abc",
    )


def _make_waiver(
    waiver_id: str,
    issue_ref: str,
    scenario_ref: str = "uc-camera-recording",
    match_rule: dict | None = None,
) -> WaiverRecord:
    variant_scope: dict = {"scenario_ref": scenario_ref}
    if match_rule:
        variant_scope["match_rule"] = match_rule
    return WaiverRecord(
        id=waiver_id,
        yaml_sha256="abc",
        title=f"Waiver {waiver_id}",
        issue_ref=issue_ref,
        scope={"variant_scope": variant_scope},
        justification="test",
        status="approved",
        approver_claim="tester",
    )


# ---------------------------------------------------------------------------
# 기본 케이스
# ---------------------------------------------------------------------------

def test_evaluate_gate_no_rules_pass():
    graph = _make_graph()
    result = evaluate_gate(graph, [])
    assert result.status == GateResultStatus.PASS
    assert result.matched_rules == []
    assert result.matched_issues == []
    assert result.applicable_waivers == []
    assert result.missing_waivers == []


def test_evaluate_gate_returns_gate_execution_result():
    graph = _make_graph()
    result = evaluate_gate(graph, [])
    assert isinstance(result, GateExecutionResult)


# ---------------------------------------------------------------------------
# GateRule 평가 (applies_to)
# ---------------------------------------------------------------------------

def test_block_rule_unconditional():
    """applies_to=None → 모든 variant에 적용 → BLOCK (D-06)."""
    graph = _make_graph()
    rule = _make_rule("rule-block", gate_result="BLOCK", applies_to=None)
    result = evaluate_gate(graph, [rule])
    assert result.status == GateResultStatus.BLOCK
    assert len(result.matched_rules) == 1
    assert result.matched_rules[0].rule_id == "rule-block"
    assert result.matched_rules[0].result == GateResultStatus.BLOCK


def test_warn_rule_unconditional():
    graph = _make_graph()
    rule = _make_rule("rule-warn", gate_result="WARN", applies_to=None)
    result = evaluate_gate(graph, [rule])
    assert result.status == GateResultStatus.WARN


def test_block_and_warn_block_wins():
    """BLOCK + WARN → BLOCK (D-11 우선순위)."""
    graph = _make_graph()
    rules = [
        _make_rule("rule-block", gate_result="BLOCK"),
        _make_rule("rule-warn", gate_result="WARN"),
    ]
    result = evaluate_gate(graph, rules)
    assert result.status == GateResultStatus.BLOCK
    assert len(result.matched_rules) == 2


def test_rule_applies_to_heavy_severity():
    """applies_to.match={'variant.severity': {'$in': ['heavy','critical']}} + severity='heavy' → matched."""
    graph = _make_graph(variant_severity="heavy")
    rule = _make_rule(
        "rule-feasibility",
        gate_result="BLOCK",
        applies_to={"match": {"variant.severity": {"$in": ["heavy", "critical"]}}},
    )
    result = evaluate_gate(graph, [rule])
    assert result.status == GateResultStatus.BLOCK
    assert len(result.matched_rules) == 1


def test_rule_not_applies_to_light_severity():
    """applies_to.match={'variant.severity': {'$in': ['heavy','critical']}} + severity='light' → not matched."""
    graph = _make_graph(variant_severity="light")
    rule = _make_rule(
        "rule-feasibility",
        gate_result="BLOCK",
        applies_to={"match": {"variant.severity": {"$in": ["heavy", "critical"]}}},
    )
    result = evaluate_gate(graph, [rule])
    assert result.status == GateResultStatus.PASS
    assert result.matched_rules == []


def test_condition_not_evaluated_flag():
    """GateRuleMatch.condition_not_evaluated=True (D-04)."""
    graph = _make_graph()
    rule = _make_rule("rule-test", gate_result="WARN")
    result = evaluate_gate(graph, [rule])
    assert result.matched_rules[0].condition_not_evaluated is True


# ---------------------------------------------------------------------------
# Issue matching
# ---------------------------------------------------------------------------

def test_matched_issues_open_no_waiver_waiver_required():
    """open issue + waiver 없음 → WAIVER_REQUIRED + missing_waivers (D-09)."""
    graph = _make_graph(issues=[_make_issue("iss-01", status="open")])
    result = evaluate_gate(graph, [])
    assert result.status == GateResultStatus.WAIVER_REQUIRED
    assert "iss-01" in result.matched_issues
    assert "iss-01" in result.missing_waivers


def test_matched_issues_deferred_no_waiver_waiver_required():
    """deferred issue + waiver 없음 → WAIVER_REQUIRED (D-09)."""
    graph = _make_graph(issues=[_make_issue("iss-02", status="deferred")])
    result = evaluate_gate(graph, [])
    assert result.status == GateResultStatus.WAIVER_REQUIRED


def test_resolved_issue_not_waiver_required():
    """resolved issue → WAIVER_REQUIRED 아님 (D-09)."""
    graph = _make_graph(issues=[_make_issue("iss-03", status="resolved")])
    result = evaluate_gate(graph, [])
    assert result.status == GateResultStatus.PASS
    assert result.missing_waivers == []


def test_wontfix_issue_not_waiver_required():
    """wontfix issue → WAIVER_REQUIRED 아님 (D-09)."""
    graph = _make_graph(issues=[_make_issue("iss-04", status="wontfix")])
    result = evaluate_gate(graph, [])
    assert result.status == GateResultStatus.PASS


def test_issue_different_scenario_not_matched():
    """scenario_ref 불일치 issue → matched_issues에 없음."""
    graph = _make_graph(issues=[_make_issue("iss-05", scenario_ref="uc-other")])
    result = evaluate_gate(graph, [])
    assert "iss-05" not in result.matched_issues
    assert result.status == GateResultStatus.PASS


def test_issue_wildcard_scenario_ref_matched():
    """scenario_ref='*' → 매칭 성립."""
    graph = _make_graph(issues=[_make_issue("iss-06", scenario_ref="*")])
    result = evaluate_gate(graph, [])
    assert "iss-06" in result.matched_issues


# ---------------------------------------------------------------------------
# Waiver 적용 가능성 (D-10)
# ---------------------------------------------------------------------------

def test_open_issue_with_applicable_waiver():
    """open issue + variant_scope 매칭 waiver → applicable_waivers, status not WAIVER_REQUIRED."""
    issue = _make_issue("iss-07", status="open")
    waiver = _make_waiver("waiver-01", issue_ref="iss-07", scenario_ref="uc-camera-recording")
    graph = _make_graph(issues=[issue], waivers=[waiver])
    result = evaluate_gate(graph, [])
    assert result.status == GateResultStatus.PASS
    assert "waiver-01" in result.applicable_waivers
    assert "iss-07" not in result.missing_waivers


def test_open_issue_waiver_scenario_ref_mismatch():
    """waiver scenario_ref != graph.scenario_id → waiver 적용 안 됨."""
    issue = _make_issue("iss-08", status="open")
    waiver = _make_waiver("waiver-02", issue_ref="iss-08", scenario_ref="uc-other")
    graph = _make_graph(issues=[issue], waivers=[waiver])
    result = evaluate_gate(graph, [])
    assert result.status == GateResultStatus.WAIVER_REQUIRED
    assert "iss-08" in result.missing_waivers
    assert "waiver-02" not in result.applicable_waivers


def test_open_issue_waiver_match_rule_pass():
    """waiver match_rule이 현재 variant에 매칭 → 적용 가능."""
    issue = _make_issue("iss-09", status="open")
    waiver = _make_waiver(
        "waiver-03", issue_ref="iss-09",
        match_rule={"all": [{"axis": "resolution", "op": "eq", "value": "UHD"}]},
    )
    # variant design_conditions={"resolution": "UHD", "fps": 60}
    graph = _make_graph(issues=[issue], waivers=[waiver])
    result = evaluate_gate(graph, [])
    assert "waiver-03" in result.applicable_waivers


def test_open_issue_waiver_match_rule_fail():
    """waiver match_rule이 현재 variant에 불일치 → 적용 불가."""
    issue = _make_issue("iss-10", status="open")
    waiver = _make_waiver(
        "waiver-04", issue_ref="iss-10",
        match_rule={"all": [{"axis": "resolution", "op": "eq", "value": "8K"}]},
    )
    # variant design_conditions={"resolution": "UHD"}
    graph = _make_graph(issues=[issue], waivers=[waiver])
    result = evaluate_gate(graph, [])
    assert result.status == GateResultStatus.WAIVER_REQUIRED


# ---------------------------------------------------------------------------
# 우선순위 집계 (D-11)
# ---------------------------------------------------------------------------

def test_aggregate_block_wins_over_waiver_required():
    """BLOCK rule + open issue without waiver → BLOCK (D-11)."""
    issue = _make_issue("iss-11", status="open")
    block_rule = _make_rule("rule-block", gate_result="BLOCK")
    graph = _make_graph(issues=[issue])
    result = evaluate_gate(graph, [block_rule])
    assert result.status == GateResultStatus.BLOCK


def test_aggregate_waiver_required_over_warn():
    """WARN rule + open issue without waiver → WAIVER_REQUIRED (D-11)."""
    issue = _make_issue("iss-12", status="open")
    warn_rule = _make_rule("rule-warn", gate_result="WARN")
    graph = _make_graph(issues=[issue])
    result = evaluate_gate(graph, [warn_rule])
    assert result.status == GateResultStatus.WAIVER_REQUIRED


def test_aggregate_warn_over_pass():
    """WARN rule + no issues → WARN."""
    warn_rule = _make_rule("rule-warn", gate_result="WARN")
    graph = _make_graph()
    result = evaluate_gate(graph, [warn_rule])
    assert result.status == GateResultStatus.WARN


@pytest.mark.parametrize("matched_rules,missing_waivers,expected", [
    ([GateRuleMatch(rule_id="r", result=GateResultStatus.BLOCK, condition_not_evaluated=True)], [], GateResultStatus.BLOCK),
    ([], ["iss-x"], GateResultStatus.WAIVER_REQUIRED),
    ([GateRuleMatch(rule_id="r", result=GateResultStatus.WARN, condition_not_evaluated=True)], [], GateResultStatus.WARN),
    ([], [], GateResultStatus.PASS),
    ([GateRuleMatch(rule_id="r", result=GateResultStatus.BLOCK, condition_not_evaluated=True)], ["iss-x"], GateResultStatus.BLOCK),
    ([GateRuleMatch(rule_id="r", result=GateResultStatus.WARN, condition_not_evaluated=True)], ["iss-x"], GateResultStatus.WAIVER_REQUIRED),
])
def test_aggregate_status_priority(matched_rules, missing_waivers, expected):
    assert _aggregate_status(matched_rules, missing_waivers) == expected
