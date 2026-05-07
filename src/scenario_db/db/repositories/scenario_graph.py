"""CanonicalScenarioGraph DTO + DB 조회 서비스 (DB-02).

DB에서 scenario + variant + project + evidence + issues + waivers + reviews를
단일 Pydantic DTO로 반환하는 get_canonical_graph() 서비스.

ORM relationship 없이 수동 다중 쿼리(최대 6회)로 N+1을 방지한다.
"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from scenario_db.db.models.capability import IpCatalog, SwProfile
from scenario_db.db.models.decision import Issue, Review, Waiver
from scenario_db.db.models.definition import Project, Scenario, ScenarioVariant
from scenario_db.db.models.evidence import Evidence
from scenario_db.db.utils import issue_affects_scenario


# ---------------------------------------------------------------------------
# Record DTOs — ORM 객체 → Pydantic 변환용
# model_validate(orm_obj) + from_attributes=True 패턴 사용
# row.__dict__ 패턴 금지 (_sa_instance_state 포함으로 extra='forbid' 위반)
# ---------------------------------------------------------------------------


class ProjectRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    schema_version: str
    metadata_: dict
    globals_: dict | None = None
    yaml_sha256: str


class ScenarioRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    schema_version: str
    project_ref: str
    metadata_: dict
    pipeline: dict
    size_profile: dict | None = None
    design_axes: list | None = None
    yaml_sha256: str


class VariantRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    scenario_id: str
    id: str
    severity: str | None = None
    design_conditions: dict | None = None
    ip_requirements: dict | None = None
    sw_requirements: dict | None = None
    violation_policy: dict | None = None
    tags: list | None = None
    derived_from_variant: str | None = None


class IpRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    schema_version: str
    category: str | None = None
    hierarchy: dict | None = None
    capabilities: dict | None = None
    rtl_version: str | None = None
    compatible_soc: list | None = None
    yaml_sha256: str


class SwProfileRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    schema_version: str
    metadata_: dict
    components: dict
    feature_flags: dict
    compatibility: dict | None = None
    yaml_sha256: str


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    schema_version: str
    kind: str
    scenario_ref: str
    variant_ref: str
    sw_baseline_ref: str | None = None
    sweep_job_id: str | None = None
    execution_context: dict
    sweep_context: dict | None = None
    resolution_result: dict | None = None
    overall_feasibility: str | None = None
    aggregation: dict
    kpi: dict
    run_info: dict | None = None
    ip_breakdown: dict | list | None = None
    provenance: dict | list | None = None
    artifacts: dict | list | None = None
    yaml_sha256: str
    sw_version_hint: str | None = None
    sweep_value_hint: str | None = None


class IssueRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    schema_version: str
    metadata_: dict
    affects: list | None = None
    affects_ip: list | None = None
    pmu_signature: dict | list | None = None
    resolution: dict | None = None
    yaml_sha256: str


class WaiverRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    yaml_sha256: str
    title: str
    issue_ref: str | None = None
    scope: dict
    justification: str | None = None
    status: str
    approver_claim: str
    claim_at: date | None = None
    git_commit_sha: str | None = None
    git_commit_author_email: str | None = None
    git_signed: bool | None = None
    approved_by_auth: str | None = None
    auth_method: str | None = None
    auth_timestamp: datetime | None = None
    auth_session_id: str | None = None
    approved_at: date | None = None
    expires_on: date | None = None


class ReviewRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    yaml_sha256: str
    scenario_ref: str
    variant_ref: str
    evidence_refs: list | None = None
    gate_result: str | None = None
    auto_checks: dict | list | None = None
    decision: str | None = None
    waiver_ref: str | None = None
    rationale: str | None = None
    review_scope: dict | None = None
    validation_: dict | None = None
    status: str
    approver_claim: str
    claim_at: date | None = None
    git_commit_sha: str | None = None
    git_commit_author_email: str | None = None
    git_signed: bool | None = None
    approved_by_auth: str | None = None
    auth_method: str | None = None
    auth_timestamp: datetime | None = None
    auth_session_id: str | None = None


# ---------------------------------------------------------------------------
# CanonicalScenarioGraph — Phase 2~4 파이프라인의 공통 입력 계약
# ---------------------------------------------------------------------------


class CanonicalScenarioGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    variant_id: str
    scenario: ScenarioRecord
    variant: VariantRecord
    project: ProjectRecord | None = None
    pipeline: dict
    ip_catalog: dict[str, IpRecord]
    sw_profiles: dict[str, SwProfileRecord]
    evidence: list[EvidenceRecord]
    issues: list[IssueRecord]
    waivers: list[WaiverRecord]
    reviews: list[ReviewRecord]


# ---------------------------------------------------------------------------
# get_canonical_graph() — DB 조회 서비스
# ---------------------------------------------------------------------------


def get_canonical_graph(
    db: Session,
    scenario_id: str,
    variant_id: str,
) -> CanonicalScenarioGraph | None:
    """DB에서 scenario 전체 그래프를 단일 DTO로 반환.

    존재하지 않는 scenario_id 또는 variant_id → None 반환.

    ORM relationship 없으므로 joinedload/selectinload 사용 금지.
    수동 다중 쿼리(최대 6회) 전략으로 N+1 방지.
    """
    # Query 1a: Scenario 조회
    scenario = db.query(Scenario).filter_by(id=scenario_id).one_or_none()
    if scenario is None:
        return None

    # Query 1b: ScenarioVariant 조회 (복합 PK: scenario_id + id 모두 필요)
    variant = (
        db.query(ScenarioVariant)
        .filter_by(scenario_id=scenario_id, id=variant_id)
        .one_or_none()
    )
    if variant is None:
        return None

    # Query 1c: Project 조회 (LEFT OUTER — project_ref가 없을 수도 있음)
    project = db.query(Project).filter_by(id=scenario.project_ref).one_or_none()

    # Query 2a: Evidence (scenario_ref + variant_ref 필터)
    evidence_rows = (
        db.query(Evidence)
        .filter(Evidence.scenario_ref == scenario_id, Evidence.variant_ref == variant_id)
        .all()
    )

    # Query 2b: Issues (Python-level filter — affects JSONB, 소규모 fixture)
    # joinedload/selectinload 대신 전체 로드 후 Python 필터 (Finding 3)
    all_issues = db.query(Issue).all()
    issues = [iss for iss in all_issues if issue_affects_scenario(iss.affects, scenario_id)]

    # Query 2c: Waivers (matched issue_refs — issue_ref IN (matched ids))
    matched_issue_ids = {iss.id for iss in issues}
    if matched_issue_ids:
        waivers = (
            db.query(Waiver)
            .filter(Waiver.issue_ref.in_(matched_issue_ids))
            .all()
        )
    else:
        waivers = []

    # Query 2d: Reviews (scenario_ref + variant_ref)
    reviews = (
        db.query(Review)
        .filter(Review.scenario_ref == scenario_id, Review.variant_ref == variant_id)
        .all()
    )

    # Query 3: IP Catalog (pipeline nodes의 ip_ref 목록)
    pipeline_ip_refs = {
        node["ip_ref"]
        for node in (scenario.pipeline or {}).get("nodes", [])
        if "ip_ref" in node
    }
    if pipeline_ip_refs:
        ip_catalog_rows = db.query(IpCatalog).filter(IpCatalog.id.in_(pipeline_ip_refs)).all()
    else:
        ip_catalog_rows = []

    # Query 4: SW Profiles (variant.sw_requirements의 profile_ref 목록)
    sw_req = variant.sw_requirements or {}
    sw_profile_refs: set[str] = set()
    for item in sw_req.get("profile_constraints", []) if isinstance(sw_req, dict) else []:
        if isinstance(item, dict) and "profile_ref" in item:
            sw_profile_refs.add(item["profile_ref"])
    if sw_profile_refs:
        sw_profile_rows = db.query(SwProfile).filter(SwProfile.id.in_(sw_profile_refs)).all()
    else:
        sw_profile_rows = []

    # ORM → Pydantic 변환 (from_attributes=True — _sa_instance_state 자동 무시)
    return CanonicalScenarioGraph(
        scenario_id=scenario_id,
        variant_id=variant_id,
        scenario=ScenarioRecord.model_validate(scenario),
        variant=VariantRecord.model_validate(variant),
        project=ProjectRecord.model_validate(project) if project else None,
        pipeline=scenario.pipeline or {},
        ip_catalog={ip.id: IpRecord.model_validate(ip) for ip in ip_catalog_rows},
        sw_profiles={sw.id: SwProfileRecord.model_validate(sw) for sw in sw_profile_rows},
        evidence=[EvidenceRecord.model_validate(e) for e in evidence_rows],
        issues=[IssueRecord.model_validate(i) for i in issues],
        waivers=[WaiverRecord.model_validate(w) for w in waivers],
        reviews=[ReviewRecord.model_validate(r) for r in reviews],
    )
