"""ETL post-load semantic validation — FK-like 참조 무결성 8가지 규칙."""
from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from scenario_db.db.models.capability import IpCatalog
from scenario_db.db.models.decision import GateRule, Issue, Waiver
from scenario_db.db.models.definition import Project, Scenario, ScenarioVariant
from scenario_db.db.models.evidence import Evidence
from scenario_db.db.models.decision import Review

logger = logging.getLogger(__name__)


class ValidationReport(BaseModel):
    """ETL 완료 후 semantic validation 결과 DTO (D-02)."""

    model_config = ConfigDict(extra="forbid")

    errors: list[str] = []
    warnings: list[str] = []

    @property
    def is_valid(self) -> bool:
        """오류 목록이 비어 있으면 유효."""
        return len(self.errors) == 0


def _issue_affects_scenario(affects: list[dict] | None, scenario_id: str) -> bool:
    """issue.affects 목록에서 특정 scenario_id 또는 wildcard '*'가 있으면 True."""
    if not affects:
        return False
    return any(
        entry.get("scenario_ref") in ("*", scenario_id)
        for entry in affects
    )


def validate_loaded(session: Session) -> ValidationReport:
    """DB 상태에서 FK-like 참조 무결성 8가지 규칙을 소프트하게 검증한다 (D-01, D-04).

    오류 발견 시 즉시 raise하지 않고 오류 목록으로 수집한다.
    DB 상태는 변경하지 않는다 (read-only SELECT).

    Args:
        session: 이미 commit()이 완료된 SQLAlchemy Session.

    Returns:
        ValidationReport: errors(위반 항목)와 warnings(경고 항목) 목록.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # --- Rule 1: scenario.project_ref → projects.id ---
    project_ids = {r[0] for r in session.execute(select(Project.id))}
    for scenario_id, project_ref in session.execute(
        select(Scenario.id, Scenario.project_ref)
    ):
        if project_ref not in project_ids:
            errors.append(
                f"scenario '{scenario_id}': project_ref '{project_ref}' not found in projects"
            )

    # --- Rule 2: scenario_variant.scenario_id → scenarios.id ---
    scenario_ids = {r[0] for r in session.execute(select(Scenario.id))}
    for sv_scenario_id, sv_id in session.execute(
        select(ScenarioVariant.scenario_id, ScenarioVariant.id)
    ):
        if sv_scenario_id not in scenario_ids:
            errors.append(
                f"variant '{sv_id}': scenario_id '{sv_scenario_id}' not found in scenarios"
            )

    # --- Rule 3: evidence.scenario_ref + evidence.variant_ref → 대상 존재 여부 ---
    variant_keys = {
        (r[0], r[1])
        for r in session.execute(
            select(ScenarioVariant.scenario_id, ScenarioVariant.id)
        )
    }
    for ev_id, ev_scenario_ref, ev_variant_ref in session.execute(
        select(Evidence.id, Evidence.scenario_ref, Evidence.variant_ref)
    ):
        if ev_scenario_ref not in scenario_ids:
            errors.append(
                f"evidence '{ev_id}': scenario_ref '{ev_scenario_ref}' not found in scenarios"
            )
        elif (ev_scenario_ref, ev_variant_ref) not in variant_keys:
            errors.append(
                f"evidence '{ev_id}': variant_ref '{ev_variant_ref}' "
                f"not found under scenario '{ev_scenario_ref}'"
            )

    # --- Rule 4: review 참조 무결성 ---
    evidence_ids = {r[0] for r in session.execute(select(Evidence.id))}
    waiver_ids = {r[0] for r in session.execute(select(Waiver.id))}
    for rev_id, rev_scenario_ref, rev_variant_ref, rev_evidence_refs, rev_waiver_ref in session.execute(
        select(
            Review.id,
            Review.scenario_ref,
            Review.variant_ref,
            Review.evidence_refs,
            Review.waiver_ref,
        )
    ):
        if rev_scenario_ref not in scenario_ids:
            errors.append(
                f"review '{rev_id}': scenario_ref '{rev_scenario_ref}' not found in scenarios"
            )
        elif (rev_scenario_ref, rev_variant_ref) not in variant_keys:
            errors.append(
                f"review '{rev_id}': variant_ref '{rev_variant_ref}' "
                f"not found under scenario '{rev_scenario_ref}'"
            )
        if rev_evidence_refs:
            for eref in rev_evidence_refs:
                if eref not in evidence_ids:
                    errors.append(
                        f"review '{rev_id}': evidence_ref '{eref}' not found in evidence"
                    )
        if rev_waiver_ref and rev_waiver_ref not in waiver_ids:
            errors.append(
                f"review '{rev_id}': waiver_ref '{rev_waiver_ref}' not found in waivers"
            )

    # --- Rule 5: issue.affects[*].scenario_ref → '*' 또는 존재하는 scenario_id ---
    for issue_id, affects in session.execute(select(Issue.id, Issue.affects)):
        if affects:
            for entry in affects:
                ref = entry.get("scenario_ref", "")
                if ref != "*" and ref not in scenario_ids:
                    warnings.append(
                        f"issue '{issue_id}': affects.scenario_ref '{ref}' not found"
                    )

    # --- Rule 6: waiver.issue_ref → issues.id ---
    issue_ids = {r[0] for r in session.execute(select(Issue.id))}
    for waiver_id, issue_ref in session.execute(select(Waiver.id, Waiver.issue_ref)):
        if issue_ref and issue_ref not in issue_ids:
            errors.append(
                f"waiver '{waiver_id}': issue_ref '{issue_ref}' not found in issues"
            )

    # --- Rule 7: gate_rule trigger/condition/action 필수 키 존재 ---
    for rule_id, trigger, condition, action in session.execute(
        select(GateRule.id, GateRule.trigger, GateRule.condition, GateRule.action)
    ):
        if not trigger or "events" not in trigger:
            errors.append(f"gate_rule '{rule_id}': trigger missing 'events' key")
        if not condition or "match" not in condition:
            errors.append(f"gate_rule '{rule_id}': condition missing 'match' key")
        if not action or "gate_result" not in action:
            errors.append(f"gate_rule '{rule_id}': action missing 'gate_result' key")

    # --- Rule 8: scenario.pipeline 노드 ip_ref → ip_catalog.id ---
    ip_ids = {r[0] for r in session.execute(select(IpCatalog.id))}
    for scen_id, pipeline in session.execute(select(Scenario.id, Scenario.pipeline)):
        for node in (pipeline or {}).get("nodes", []):
            ip_ref = node.get("ip_ref")
            if ip_ref and ip_ref not in ip_ids:
                errors.append(
                    f"scenario '{scen_id}': pipeline node ip_ref '{ip_ref}' not in ip_catalog"
                )

    return ValidationReport(errors=errors, warnings=warnings)
