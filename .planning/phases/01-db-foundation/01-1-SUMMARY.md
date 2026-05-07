---
phase: 1
plan: 1
subsystem: etl-validation
tags: [validation, pydantic, etl, semantic-check, db-foundation]
dependency_graph:
  requires: []
  provides:
    - validate_loaded(session) -> ValidationReport
    - FHD30-SDR-H265 demo fixture variant
  affects:
    - src/scenario_db/etl/loader.py (validate_loaded auto-call on ETL complete)
    - tests/unit/test_validate_loaded.py
    - tests/integration/test_validate_loaded.py
tech_stack:
  added: []
  patterns:
    - Pydantic v2 ValidationReport DTO (extra=forbid, is_valid property)
    - SQLAlchemy 2.0 select() — read-only multi-table scan
    - Soft validation — collect errors, preserve DB state
    - Local import inside function (circular import prevention)
key_files:
  created:
    - src/scenario_db/etl/validate_loaded.py
    - tests/unit/test_validate_loaded.py
    - tests/integration/test_validate_loaded.py
  modified:
    - src/scenario_db/etl/loader.py
    - demo/fixtures/02_definition/uc-camera-recording.yaml
decisions:
  - "D-01: Soft validation 채택 — 오류 수집 후 리포트, DB 상태 유지"
  - "D-02: ValidationReport(errors, warnings, is_valid) Pydantic 모델"
  - "D-03: load_yaml_dir() 내 session.commit() 직후 자동 호출, 지역 import"
  - "D-04: 8가지 FK-like 규칙 — project_ref, scenario_variant, evidence, review, issue.affects, waiver.issue_ref, gate_rule 형식, pipeline.ip_ref"
metrics:
  duration: "~25 minutes"
  completed_date: "2026-05-07"
  tasks_completed: 2
  files_changed: 5
  tests_added: 8
  tests_total: 346
---

# Phase 1 Plan 1: ETL Post-Load Semantic Validation Summary

**One-liner:** `validate_loaded(session)` — 8가지 FK-like 규칙을 소프트하게 검사하는 `ValidationReport` Pydantic DTO, `load_yaml_dir()` commit 직후 자동 실행.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | FHD30-SDR-H265 fixture 추가 + 테스트 스캐폴드 | 7e26fb0 | demo/fixtures/02_definition/uc-camera-recording.yaml, tests/unit/test_validate_loaded.py, tests/integration/test_validate_loaded.py |
| 2 | validate_loaded.py 구현 + loader.py 통합 | 97a24de | src/scenario_db/etl/validate_loaded.py, src/scenario_db/etl/loader.py |

## Verification Results

```
uv run pytest tests/unit/test_validate_loaded.py -x -q
  4 passed

uv run pytest tests/integration/test_validate_loaded.py -x -q -m integration
  4 passed

uv run pytest tests/ -q
  346 passed (기존 + 신규 모두 green)
```

## Decisions Made

- `validate_loaded()` 반환값 `dict[str, int]`의 변경 없이 부수 효과(side effect)로 처리
- `is_valid` 프로퍼티를 Pydantic 모델 내부에 정의하여 `report.is_valid` 패턴 사용 가능
- circular import 방지를 위해 `loader.py`에서 `validate_loaded` import를 함수 내부 지역 import로 배치
- `issue.affects[*].scenario_ref == '*'` wildcard를 `_issue_affects_scenario()` 헬퍼로 캡슐화

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] FHD30-SDR-H265 severity enum 불일치**
- **Found during:** Task 2 통합 테스트 실행
- **Issue:** fixture에 `severity: normal`을 지정했으나 Pydantic Severity StrEnum은 `light/medium/heavy/critical` 값만 허용. ETL 로드 시 `ValidationError: Input should be 'light', 'medium', 'heavy' or 'critical'` 발생
- **Fix:** `severity: normal` → `severity: light`로 수정 (FHD 30fps SDR은 가장 경량 severity)
- **Files modified:** demo/fixtures/02_definition/uc-camera-recording.yaml
- **Commit:** 2b4c833

## Known Stubs

없음. 모든 8가지 규칙이 완전 구현되어 있으며, ValidationReport의 모든 필드가 실제 쿼리 결과로 채워집니다.

## Threat Flags

없음. 추가된 모든 코드는 read-only SELECT 쿼리만 수행하며 새로운 네트워크 엔드포인트나 인증 경로를 도입하지 않습니다.

## Self-Check: PASSED

```
src/scenario_db/etl/validate_loaded.py: FOUND
tests/unit/test_validate_loaded.py: FOUND
tests/integration/test_validate_loaded.py: FOUND
commit 7e26fb0: FOUND
commit 97a24de: FOUND
commit 2b4c833: FOUND
346 tests all passed
```
