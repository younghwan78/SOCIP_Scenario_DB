from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from scenario_db.models.decision.common import GateResultStatus


class GateRuleMatch(BaseModel):
    """단일 gate rule 매칭 결과."""
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    result: GateResultStatus          # PASS, WARN, BLOCK (WAIVER_REQUIRED는 issue 경로로만)
    message: str | None = None        # action.message_template 원본 (미치환 템플릿)
    condition_not_evaluated: bool = True  # D-04: condition.match는 Phase 3에서 평가


class GateExecutionResult(BaseModel):
    """evaluate_gate() 반환 결과 — 비영속."""
    model_config = ConfigDict(extra="forbid")

    status: GateResultStatus                           # 최종 집계 상태
    matched_rules: list[GateRuleMatch] = Field(default_factory=list)
    matched_issues: list[str] = Field(default_factory=list)      # issue id 목록
    applicable_waivers: list[str] = Field(default_factory=list)  # waiver id 목록
    missing_waivers: list[str] = Field(default_factory=list)     # waiver 없는 issue id 목록
