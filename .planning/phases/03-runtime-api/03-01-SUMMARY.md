---
phase: 03-runtime-api
plan: "01"
subsystem: api
tags: [fastapi, router, runtime, graph, resolve, gate]
dependency_graph:
  requires:
    - 02-resolver-gate-engine/02-01-SUMMARY.md
    - 02-resolver-gate-engine/02-02-SUMMARY.md
    - 01-db-foundation/01-02-SUMMARY.md
  provides:
    - src/scenario_db/api/routers/runtime.py
    - /api/v1/scenarios/{id}/variants/{vid}/graph endpoint
    - /api/v1/scenarios/{id}/variants/{vid}/resolve endpoint
    - /api/v1/scenarios/{id}/variants/{vid}/gate endpoint
  affects:
    - src/scenario_db/api/app.py
tech_stack:
  added: []
  patterns:
    - FastAPI APIRouter with response_model
    - NoResultFound → 404 via registered exception handler
    - RuleCache dependency injection (Depends(get_rule_cache))
key_files:
  created:
    - src/scenario_db/api/routers/runtime.py
  modified:
    - src/scenario_db/api/app.py
decisions:
  - "D-05 준수: cache.gate_rules 빈 리스트도 503 없이 evaluate_gate(graph, []) 직접 전달"
  - "NoResultFound raise 패턴: get_canonical_graph() None 반환 시 exceptions.py 핸들러가 404로 변환"
  - "resolve 엔드포인트에 RuleCache 의존성 제외 (Resolver는 gate_rules 무관)"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-10"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 1
---

# Phase 3 Plan 01: Runtime Router Summary

## One-liner

Phase 1/2 순수 Python 계산 결과(CanonicalScenarioGraph, ResolverResult, GateExecutionResult)를 HTTP로 노출하는 FastAPI runtime.py 라우터 신규 생성 및 app.py 등록.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | runtime.py 라우터 신규 생성 | bdc9a2d | src/scenario_db/api/routers/runtime.py (created, 70 lines) |
| 2 | app.py에 runtime.router 등록 | 6d2f665 | src/scenario_db/api/app.py (+2 lines) |

## What Was Built

### src/scenario_db/api/routers/runtime.py (신규)

`APIRouter(tags=["runtime"])` 에 3개 엔드포인트 등록:

1. **GET `/scenarios/{scenario_id}/variants/{variant_id}/graph`**
   - `response_model=CanonicalScenarioGraph`
   - `get_canonical_graph(db, sid, vid)` → None 이면 `NoResultFound` raise → 404 JSON
   - Depends: `get_db` 만 (RuleCache 불필요)

2. **GET `/scenarios/{scenario_id}/variants/{variant_id}/resolve`**
   - `response_model=ResolverResult`
   - graph 조회 후 `resolve(graph)` 호출
   - Depends: `get_db` 만 (D-05: Resolver는 gate_rules 무관)

3. **GET `/scenarios/{scenario_id}/variants/{variant_id}/gate`**
   - `response_model=GateExecutionResult`
   - graph 조회 후 `evaluate_gate(graph, cache.gate_rules)` 호출
   - Depends: `get_db` + `get_rule_cache`
   - D-05: `cache.gate_rules=[]` 이어도 503 없이 `evaluate_gate(graph, [])` → `status=PASS`

### src/scenario_db/api/app.py (수정)

- `from scenario_db.api.routers import runtime as runtime_router` import 추가
- `include_router` 리스트에 `runtime_router.router` 추가
- 기존 5개 라우터(capability, definition, evidence, decision, view_router) 변경 없음

## Verification Results

```
OK ['/scenarios/{scenario_id}/variants/{variant_id}/graph',
    '/scenarios/{scenario_id}/variants/{variant_id}/resolve',
    '/scenarios/{scenario_id}/variants/{variant_id}/gate']

PASS: 3 runtime routes registered
['/api/v1/gate-rules',
 '/api/v1/scenarios/{scenario_id}/variants/{variant_id}/graph',
 '/api/v1/scenarios/{scenario_id}/variants/{variant_id}/resolve',
 '/api/v1/scenarios/{scenario_id}/variants/{variant_id}/gate']

PASS: import chain OK
```

## Deviations from Plan

None — 플랜 대로 정확히 실행됨.

## Threat Surface Scan

- T-03-01 (Spoofing): `scenario_id`, `variant_id` → SQLAlchemy `filter_by()` parameterized query로 SQL injection 방지. 추가 위협 없음.
- T-03-02, T-03-03: accept 처분 그대로 유지.
- 신규 노출 경로 없음 — 플랜 threat_model 완전 포함.

## Known Stubs

None — 3개 엔드포인트 모두 실제 Phase 1/2 로직(get_canonical_graph, resolve, evaluate_gate)을 직접 호출. mock/placeholder 없음.

## Self-Check: PASSED

- [x] `src/scenario_db/api/routers/runtime.py` 존재
- [x] `src/scenario_db/api/app.py` runtime_router 포함
- [x] commit bdc9a2d 존재
- [x] commit 6d2f665 존재
- [x] Python import 에러 없음
- [x] /graph, /resolve, /gate 3개 경로 `/api/v1/` prefix로 라우팅 확인
