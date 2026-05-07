---
phase: 1
plan: 2
subsystem: db-repositories
tags: [pydantic, dto, orm, canonical-graph, scenario-graph]
dependency_graph:
  requires:
    - "src/scenario_db/db/models/definition.py (Project, Scenario, ScenarioVariant ORM)"
    - "src/scenario_db/db/models/decision.py (Issue, Waiver, Review ORM)"
    - "src/scenario_db/db/models/capability.py (IpCatalog, SwProfile ORM)"
    - "src/scenario_db/db/models/evidence.py (Evidence ORM)"
  provides:
    - "CanonicalScenarioGraph Pydantic DTO (Phase 2~4 공통 입력 계약)"
    - "get_canonical_graph(db, scenario_id, variant_id) -> CanonicalScenarioGraph | None"
  affects:
    - "Phase 2 Resolver Engine (입력 DTO)"
    - "Phase 3 API /graph 엔드포인트 (응답 DTO)"
    - "Phase 4 Level 0 Viewer (projection 입력)"
tech_stack:
  added: []
  patterns:
    - "Pydantic v2 ConfigDict(extra='forbid', from_attributes=True) — ORM 직접 전달"
    - "session.query().filter_by() — SQLAlchemy 1.x 스타일 (기존 패턴 일관성)"
    - "수동 6-쿼리 전략 — ORM relationship 없이 N+1 방지"
    - "_issue_affects_scenario() — JSONB wildcard '*' 필터"
key_files:
  created:
    - "src/scenario_db/db/repositories/scenario_graph.py (DTO + 서비스)"
    - "tests/unit/test_scenario_graph_models.py (Pydantic round-trip 단위 테스트)"
  modified: []
decisions:
  - "model_validate(orm_obj) + from_attributes=True 패턴 채택 — row.__dict__ 패턴 금지(_sa_instance_state 포함으로 extra='forbid' 위반)"
  - "수동 6-쿼리 전략 채택 — ORM relationship 부재로 joinedload/selectinload 불가(Finding 1)"
  - "Issues 스코핑: Python-level 필터 + wildcard '*' 지원 — 소규모 fixture 기준 DB-side JSONB 쿼리 대신 단순성 선택"
  - "Waivers 스코핑: matched issue_refs IN 쿼리 — Phase 1 scope에서 단순 연결만 구현"
metrics:
  duration: "3 minutes"
  completed_date: "2026-05-07"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 1 Plan 2: CanonicalScenarioGraph DTO + get_canonical_graph() Summary

**One-liner:** 9개 Record Pydantic DTO + CanonicalScenarioGraph 통합 DTO + 수동 6-쿼리 get_canonical_graph() 서비스를 SQLAlchemy 1.x session.query 스타일로 구현

## Objective

DB에서 scenario + variant + project + evidence + issues + waivers + reviews를
단일 Pydantic DTO(CanonicalScenarioGraph)로 반환하는 서비스 구현.
이 DTO는 Phase 2 Resolver, Phase 3 API /graph 엔드포인트, Phase 4 Viewer의 공통 입력 계약이다.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 2d14ad7 | test(01-2) | TDD RED — failing test for CanonicalScenarioGraph Pydantic round-trip |
| 260125e | feat(01-2) | TDD GREEN — CanonicalScenarioGraph DTO + get_canonical_graph() service |

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Record DTO 정의 + 단위 테스트 (TDD) | 2d14ad7 (RED) + 260125e (GREEN) | scenario_graph.py, test_scenario_graph_models.py |
| 2 | get_canonical_graph() 구현 | 260125e | scenario_graph.py |

## Verification Results

```
uv run pytest tests/unit/test_scenario_graph_models.py -x -q
5 passed in 1.68s

uv run pytest tests/unit/ -q
235 passed in 1.83s  (regression 없음)
```

### Acceptance Criteria

| Criterion | Expected | Actual | Status |
|-----------|----------|--------|--------|
| class CanonicalScenarioGraph 수 | 1 | 1 | PASS |
| from_attributes=True 수 | >=7 | 11 | PASS |
| extra='forbid'/"forbid" 수 | >=9 | 11 | PASS |
| class ScenarioRecord 수 | 1 | 1 | PASS |
| class VariantRecord 수 | 1 | 1 | PASS |
| def get_canonical_graph 수 | 1 | 1 | PASS |
| def _issue_affects_scenario 수 | 1 | 1 | PASS |
| row.__dict__ (코드) | 0 | 0 (주석만) | PASS |
| joinedload\|selectinload (코드) | 0 | 0 (주석만) | PASS |
| filter_by(scenario_id=..., id=...) | 1 | 1 | PASS |

## Architecture

```
CanonicalScenarioGraph (Phase 2~4 공통 입력 계약)
├── scenario: ScenarioRecord       (ORM → Pydantic, from_attributes=True)
├── variant: VariantRecord
├── project: ProjectRecord | None
├── pipeline: dict                 (scenario.pipeline JSONB)
├── ip_catalog: dict[str, IpRecord]  (pipeline nodes ip_ref 기반)
├── sw_profiles: dict[str, SwProfileRecord]  (variant.sw_requirements 기반)
├── evidence: list[EvidenceRecord]
├── issues: list[IssueRecord]      (_issue_affects_scenario() wildcard 필터)
├── waivers: list[WaiverRecord]    (matched issue_refs IN 쿼리)
└── reviews: list[ReviewRecord]

get_canonical_graph() 6-쿼리 전략:
  Q1a: Scenario.filter_by(id=scenario_id)
  Q1b: ScenarioVariant.filter_by(scenario_id=x, id=y)  ← 복합 PK
  Q1c: Project.filter_by(id=scenario.project_ref)       ← LEFT OUTER
  Q2a: Evidence.filter(scenario_ref=x, variant_ref=y)
  Q2b: Issue.all() → Python-level wildcard 필터
  Q2c: Waiver.filter(issue_ref.in_(matched_ids))
  Q2d: Review.filter(scenario_ref=x, variant_ref=y)
  Q3:  IpCatalog.filter(id.in_(pipeline_ip_refs))
  Q4:  SwProfile.filter(id.in_(sw_profile_refs))
```

## Decisions Made

1. **model_validate(orm_obj) 패턴 채택:** `from_attributes=True`로 ORM 객체 직접 전달.
   `row.__dict__` 금지 — `_sa_instance_state` 포함으로 `extra='forbid'` 위반 (Pitfall 1).

2. **수동 6-쿼리 전략:** ORM에 `relationship()` 선언 없음(RESEARCH.md Finding 1).
   `joinedload`/`selectinload` 사용 불가 → 수동 쿼리 조합으로 동등한 효과 달성.

3. **Issues Python-level 필터:** `Issue.affects` JSONB wildcard `*` 포함 여부를
   DB-side JSONB 쿼리 대신 Python 필터로 처리. 소규모 fixture 기준 단순성 선택.

4. **SQLAlchemy 1.x 스타일 유지:** 기존 `definition.py` 패턴(`session.query().filter_by()`)과
   일관성 유지. 신규 코드에서도 1.x 스타일 적용.

## Deviations from Plan

None — 플랜에 명시된 구현 내용 그대로 실행됨.

## Known Stubs

None — `sw_profiles` 필드는 `variant.sw_requirements.profile_constraints[*].profile_ref`를
실제로 파싱하여 DB에서 조회하도록 구현됨 (RESEARCH.md Open Question 3 해결).

## Threat Flags

None — 이 모듈은 내부 서비스 계층이며, HTTP 엔드포인트 미노출.
`get_canonical_graph()` 입력(`scenario_id`, `variant_id`)은 SQLAlchemy 파라미터화 쿼리로
처리되므로 SQL Injection 불가 (T-02-01 accept).
Phase 3에서 HTTP 경로 파라미터로 노출 시 인증/인가 레이어 추가 필요 (T-02-02).

## Self-Check: PASSED

- `src/scenario_db/db/repositories/scenario_graph.py` exists: FOUND
- `tests/unit/test_scenario_graph_models.py` exists: FOUND
- Commit 2d14ad7 (RED): FOUND
- Commit 260125e (GREEN): FOUND
- 5 unit tests passing: CONFIRMED
- 235 total unit tests passing (regression check): CONFIRMED
