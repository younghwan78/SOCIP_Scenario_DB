---
phase: 03-runtime-api
plan: "02"
subsystem: view-router
tags: [view, mode-param, db-projection, d06-compliance]
dependency_graph:
  requires: [03-01]
  provides: [API-04]
  affects: [src/scenario_db/api/routers/view.py, src/scenario_db/view/service.py]
tech_stack:
  added: []
  patterns: [keyword-only db param, lazy import inside function, mode-branch dispatch]
key_files:
  modified:
    - src/scenario_db/api/routers/view.py
    - src/scenario_db/view/service.py
decisions:
  - "db=None 분기 완전 제거(D-06): dashboard에서 project_level0 직접 호출 없음(grep 확인)"
  - "mode 미지정값 → NotImplementedError(T-03-04 mitigate, Rule 2 자동 추가)"
  - "_projection_to_view_response() 헬퍼로 get_view_projection dict → ViewResponse 변환"
metrics:
  duration: "15m"
  completed: "2026-05-10"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 03 Plan 02: View Router mode Param + DB Projection Summary

View router level 0 분기에 mode 파라미터를 project_level0()에 전달하고, service.py에서 sample fallback(db=None 분기)을 완전 제거한 뒤 mode 분기(architecture=DB projection, topology=NotImplementedError)를 구현.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | dashboard 호출 지점 확인 후 view.py 라우터 수정 | e05d279 | src/scenario_db/api/routers/view.py |
| 2 | service.py sample fallback 제거 + mode 분기 구현 | 44032cd | src/scenario_db/view/service.py |

## Success Criteria Verification

1. view.py level 0 분기에 `mode=mode` 전달 확인 — PASS (line 35)
2. service.py project_level0() 시그니처에 `mode: str = "architecture"` 파라미터 존재 — PASS
3. topology mode → NotImplementedError("topology mode is Phase 4 work") raise — PASS
4. architecture mode + db 있음 → _projection_to_view_response(get_view_projection(...)) 반환 — PASS
5. project_level0()에 `if db is None` 분기가 없음 (D-06 완전 이행) — PASS (count=0)
6. 기존 `response = build_sample_level0()` 후 ViewResponse 재구성 블록 제거됨 — PASS (model_dump 없음)
7. _projection_to_view_response()가 ViewSummary 필수 필드 전부 채움 — PASS
8. build_sample_level0() 함수 정의는 service.py에 보존 (D-06 note) — PASS (count=1)

## Deviations from Plan

### Auto-added Issues

**1. [Rule 2 - Security] T-03-04 mitigate: mode 미지정값 guard 추가**
- **Found during:** Task 2
- **Issue:** mode 파라미터가 "architecture"/"topology" 이외의 임의 문자열이면 DB projection이 silently 실행됨 — T-03-04 위협 register의 mitigate disposition과 불일치
- **Fix:** `if mode not in ("architecture", "topology"): raise NotImplementedError(f"mode '{mode}' is not supported")` 추가 — FastAPI 501로 변환
- **Files modified:** src/scenario_db/view/service.py
- **Commit:** 44032cd (Task 2 커밋에 포함)

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| dashboard에서 project_level0 직접 호출 없음 | grep 사전 확인: dashboard/*.py에서 project_level0 호출 없음 → db=None 분기 제거 시 dashboard 영향 없음 |
| mode 미지정값 → NotImplementedError | T-03-04 Tampering 위협 mitigate — 알 수 없는 mode는 501로 거부 |
| keyword-only db param (db: "Session") | D-06 이행 — 실수로 positional 전달 방지, 타입 힌트로 Session 명시 |

## Known Stubs

- _projection_to_view_response()의 NodeElement는 pipeline.nodes를 그대로 사용하며 type="ip", layer="hw"로 고정됨 — Phase 4 VIEW-01에서 실제 ELK 레이아웃 및 타입/레이어 매핑으로 교체 예정
- ViewSummary 필드 subtitle, period_ms, budget_ms, resolution, fps, variant_label은 임시 기본값 사용 — Phase 4에서 DB 필드로 매핑 예정

## Threat Flags

없음 — 기존 T-03-04 위협은 mode guard 추가로 mitigate 완료.

## Self-Check: PASSED

- src/scenario_db/api/routers/view.py: FOUND
- src/scenario_db/view/service.py: FOUND
- Commit e05d279: FOUND
- Commit 44032cd: FOUND
