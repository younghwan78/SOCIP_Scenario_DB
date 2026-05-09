---
phase: 2
plan: 1
subsystem: resolver
tags: [resolver, pydantic, pure-python, non-persistent]
dependency_graph:
  requires: [scenario_db.db.repositories.scenario_graph, scenario_db.models.capability.hw]
  provides: [scenario_db.resolver.engine.resolve, scenario_db.resolver.models.ResolverResult]
  affects: []
tech_stack:
  added: []
  patterns: [all-matching-modes, strict-unresolved, zero-padding-version-compare]
key_files:
  created:
    - src/scenario_db/resolver/__init__.py
    - src/scenario_db/resolver/models.py
    - src/scenario_db/resolver/engine.py
    - tests/unit/resolver/__init__.py
    - tests/unit/resolver/test_resolver.py
  modified: []
decisions:
  - "D-01: all-matching modes — throughput >= required 조건 충족 모드 전체 반환 (first-fit 아님)"
  - "D-02: strict unresolved — 미지원 키는 unresolved_requirements + warnings 모두 기록"
  - "D-03: matched_modes 빈 리스트 → node_id를 unresolved_requirements에 추가"
  - "_version_gte: v 접두사 무시 + zero-padding tuple 비교로 자릿수 불일치 처리"
metrics:
  duration: "~20 min"
  completed: "2026-05-09"
  tasks_completed: 2
  files_created: 5
---

# Phase 2 Plan 1: Resolver 엔진 구현 Summary

**One-liner:** `resolve(CanonicalScenarioGraph) -> ResolverResult` 순수 Python 함수 구현 — all-matching mode 전략 + strict unresolved 기록 (SQLAlchemy 의존성 없음).

## 구현한 파일 목록

| 파일 | 설명 |
|------|------|
| `src/scenario_db/resolver/__init__.py` | 패키지 마커 (빈 파일) |
| `src/scenario_db/resolver/models.py` | IpResolution, SwResolution, ResolverResult Pydantic 모델 |
| `src/scenario_db/resolver/engine.py` | `resolve()` 순수 함수 + `_version_gte()` 헬퍼 |
| `tests/unit/resolver/__init__.py` | 테스트 패키지 마커 |
| `tests/unit/resolver/test_resolver.py` | 단위 테스트 28개 |

## 테스트 결과

```
28 passed in 0.25s   (tests/unit/resolver/)
267 passed in 0.99s  (tests/unit/ — regression 없음)
```

## 중요한 구현 결정사항

### D-01: All-matching modes (throughput 체크)

`required_throughput_mpps=498` → ISP의 normal(500✓), high_throughput(800✓), low_power(250✗).
downstream(Phase 3 API)이 최종 모드를 선택하도록 설계.

### D-02: Strict unresolved

`required_codec`, `required_level`, `required_allocations` 등 `_KNOWN_IP_REQ_KEYS`에 없는 키는
모두 `unresolved_requirements` + `warnings`에 기록. silent skip 없음.

SW requirements에서 `required_hal`처럼 Phase 2 미지원 키는 `warnings`만 추가 (`unresolved` 제외).

### D-03: matched_modes=[] → unresolved

모든 operating_mode가 throughput 조건 미충족 시 `node_id`를 `unresolved_requirements`에 추가.
fallback 모드 없음.

### _version_gte: zero-padding 비교

`"1.2"` vs `"1.2.0"` 비교 시 Python tuple 길이 불일치 문제를 zero-padding으로 해결.
`(1, 2)` vs `(1, 2, 0)` → padding 후 `(1, 2, 0)` vs `(1, 2, 0)` → True.

## 기존 테스트 Regression

없음. `uv run pytest tests/unit/ -q` → 267 passed (이전과 동일).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] _version_gte zero-padding 수정**
- **Found during:** Task 2 GREEN 단계
- **Issue:** `_version_gte("1.2", "1.2.0")` 이 `False`를 반환 — Python tuple 비교에서 `(1,2) < (1,2,0)` 이므로 의도와 다름
- **Fix:** `_parse()` 반환 타입을 `list[int]`로 변경 후 `max_len` 기준으로 zero-padding 적용
- **Files modified:** `src/scenario_db/resolver/engine.py`
- **Commit:** e5e15f2

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (test) | 44ade76 | PASS — ImportError로 실패 확인 |
| GREEN (feat) | e5e15f2 | PASS — 28 tests pass |
| REFACTOR | 없음 | 해당 없음 (코드 정리 불필요) |

## Threat Surface Scan

신규 네트워크 엔드포인트 없음. `resolve()`는 순수 함수 — 입력 CanonicalScenarioGraph는
Phase 1 ETL에서 이미 Pydantic 검증됨. 추가 threat surface 없음.

## Self-Check: PASSED

- `src/scenario_db/resolver/models.py` — FOUND
- `src/scenario_db/resolver/engine.py` — FOUND
- `tests/unit/resolver/test_resolver.py` — FOUND
- commit ce2c8bf — FOUND
- commit 44ade76 — FOUND
- commit e5e15f2 — FOUND
- `grep -r "sqlalchemy" src/scenario_db/resolver/` — NO MATCH (비영속 확인)
