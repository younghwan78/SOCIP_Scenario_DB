---
phase: 1
plan: 3
subsystem: db-repositories
tags: [view-projection, integration-tests, db-foundation, repository-pattern]
dependency_graph:
  requires:
    - "src/scenario_db/db/models/definition.py (Project, Scenario, ScenarioVariant ORM)"
    - "src/scenario_db/db/models/capability.py (IpCatalog ORM)"
    - "src/scenario_db/db/repositories/scenario_graph.py (CanonicalScenarioGraph — Plan 02 산출물)"
    - "src/scenario_db/etl/validate_loaded.py (validate_loaded — Plan 01 산출물)"
    - "tests/integration/conftest.py (engine fixture — testcontainers PostgreSQL)"
  provides:
    - "get_view_projection(db, scenario_id, variant_id) -> dict | None"
    - "tests/integration/test_scenario_graph.py — DB-02 통합 검증"
    - "tests/integration/test_view_projection.py — DB-03 통합 검증"
  affects:
    - "Phase 3 view router (get_view_projection() 소비)"
    - "Phase 4 Streamlit viewer (Level 0 lane data 공급)"
tech_stack:
  added: []
  patterns:
    - "db.query(Model).filter_by() — SQLAlchemy 1.x 스타일 (기존 패턴 일관성)"
    - "IpCatalog.id.in_(ip_refs) — 배치 쿼리로 pipeline ip_ref 일괄 조회"
    - "lane_id 기준 노드 그룹화 (없으면 'default' lane)"
    - "pytestmark = pytest.mark.integration — 통합 테스트 마커"
key_files:
  created:
    - "src/scenario_db/db/repositories/view_projection.py"
    - "tests/integration/test_scenario_graph.py"
    - "tests/integration/test_view_projection.py"
  modified:
    - "src/scenario_db/db/repositories/scenario_graph.py (JSONB type fix)"
decisions:
  - "get_view_projection() 반환 타입 dict — Pydantic DTO 없이 raw dict 반환 (Phase 3 라우터가 ViewResponse로 변환)"
  - "lane 그룹화 로직 Repository 내부 구현 — service 레이어에서 ORM 직접 접근 불필요"
  - "pipeline JSONB 그대로 반환 — Phase 3에서 ViewResponse 프로젝션 수행"
metrics:
  duration: "3 minutes"
  completed_date: "2026-05-07"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 1
---

# Phase 1 Plan 3: view_projection Repository + Phase 1 Integration Tests Summary

**One-liner:** `get_view_projection()` Level 0 lane data Repository 구현 + DB-02/DB-03 통합 테스트 작성, JSONB list/dict 타입 불일치 버그 4건 자동 수정으로 361개 테스트 전체 green 달성

## Objective

Phase 3 view router가 소비할 `get_view_projection()` 쿼리를 Repository 메서드로 캡슐화.
동시에 Plan 01/02에서 생성된 신규 모듈(validate_loaded, scenario_graph)의 통합 테스트를 완성하여
Phase 1 전체 요구사항(DB-01~DB-03)의 integration test coverage를 달성.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 1c726c6 | feat(01-3) | implement get_view_projection() — Level 0 lane data repository |
| d643fe4 | feat(01-3) | Phase 1 integration tests + EvidenceRecord/IssueRecord/ReviewRecord JSONB type fix |

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | view_projection.py 구현 | 1c726c6 | view_projection.py (신규 86줄) |
| 2 | 통합 테스트 완성 + Phase 1 최종 검증 | d643fe4 | test_scenario_graph.py, test_view_projection.py (신규), scenario_graph.py (수정) |

## Verification Results

```
uv run pytest tests/integration/test_scenario_graph.py tests/integration/test_view_projection.py tests/integration/test_validate_loaded.py -x -q -m integration
14 passed in 2.25s

uv run pytest tests/ -q
361 passed in 3.78s  (regression 없음, 15개 신규 추가)
```

### Acceptance Criteria

| Criterion | Expected | Actual | Status |
|-----------|----------|--------|--------|
| view_projection.py 존재 | Y | Y | PASS |
| def get_view_projection 수 | 1 | 1 | PASS |
| filter_by(scenario_id=..., id=...) 수 | 1 | 1 | PASS |
| test_scenario_graph.py pytestmark | integration | integration | PASS |
| test_view_projection.py pytestmark | integration | integration | PASS |
| test_canonical_graph_no_sa_instance_state 수 | 1 | 1 | PASS |
| import OK | exit 0 | exit 0 | PASS |
| 통합 테스트 3파일 | all green | 14 passed | PASS |
| 전체 테스트 | all green | 361 passed | PASS |

## Architecture

```
Phase 3 view router
  └── get_view_projection(db, scenario_id, variant_id)
        ├── Q1a: Scenario.filter_by(id=scenario_id)
        ├── Q1b: ScenarioVariant.filter_by(scenario_id=x, id=y)  ← 복합 PK
        ├── Q1c: Project.filter_by(id=scenario.project_ref)       ← optional
        ├── Q2:  IpCatalog.filter(id.in_(pipeline_ip_refs))       ← 배치
        └── returns: {
              scenario_id, variant_id, project_name,
              pipeline (JSONB),
              ip_catalog (list[dict] — id/category/hierarchy/capabilities),
              lanes (list[{lane_id, nodes}] — pipeline.nodes 그룹화)
            }
```

## Phase 1 Goal Achievement

| Requirement | Description | Status |
|-------------|-------------|--------|
| DB-01 | ETL 로드 후 semantic validation 자동 실행 | DONE (Plan 01) |
| DB-02 | get_canonical_graph()로 단일 DTO 조회 | DONE (Plan 02) |
| DB-03 | view_projection + scenario_graph Repository 캡슐화 | DONE (Plan 03) |

**Phase 1 Goal: "DB에서 scenario 전체 그래프를 안전하게 조회할 수 있다" — ACHIEVED**

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] EvidenceRecord JSONB list/dict 타입 불일치 4건**
- **Found during:** Task 2 통합 테스트 실행 (test_canonical_graph_demo_scenario)
- **Issue:** `EvidenceRecord.ip_breakdown`, `EvidenceRecord.artifacts`, `IssueRecord.pmu_signature`, `ReviewRecord.auto_checks` 필드가 Pydantic에서 `dict`로 선언되어 있으나, demo fixtures YAML에서 해당 필드들이 `list` 타입으로 저장됨. 통합 테스트 실행 시 `pydantic_core.ValidationError: Input should be a valid dictionary` 발생.
- **Fix:** 4개 필드 타입을 `dict | None` → `dict | list | None`으로 수정
- **Files modified:** `src/scenario_db/db/repositories/scenario_graph.py`
- **Commit:** d643fe4 (Task 2 커밋에 포함)
- **Root cause:** Plan 02 구현 시 YAML fixture의 실제 데이터 구조를 확인하지 않고 JSONB 필드를 일률적으로 `dict`로 선언. 통합 테스트가 없었으므로 단위 테스트 단계에서 발견되지 않음.

## Known Stubs

없음. `get_view_projection()`은 DB 실데이터 기반으로 완전 구현되어 있음.
Phase 3에서 이 Repository를 소비하여 `ViewResponse` Pydantic DTO로 프로젝션 수행 예정.

## Threat Flags

없음. `get_view_projection()`은 내부 서비스 계층이며, 현재 HTTP 엔드포인트 미노출.
입력값(`scenario_id`, `variant_id`)은 SQLAlchemy 파라미터화 쿼리로 처리 (T-03-01 accept).
Phase 3에서 HTTP 경로 파라미터로 노출 시 FastAPI path parameter validation 적용 예정 (T-03-02 defer).

## Self-Check: PASSED

- `src/scenario_db/db/repositories/view_projection.py`: FOUND
- `tests/integration/test_scenario_graph.py`: FOUND
- `tests/integration/test_view_projection.py`: FOUND
- Commit 1c726c6: FOUND
- Commit d643fe4: FOUND
- 14 integration tests passing: CONFIRMED
- 361 total tests passing (regression check): CONFIRMED
