---
phase: 7
plan: "07-03"
subsystem: simulation-api
tags: [fastapi, router, integration-test, tdd, caching, evidence]
dependency_graph:
  requires:
    - "07-01 — 5종 Pydantic 스키마, simulation repository (save/find)"
    - "07-02 — load_runner_inputs_from_db(), compute_params_hash(), apply_request_overrides()"
    - "Phase 6 — run_simulation() 시그니처, SimRunResult"
  provides:
    - "5개 /simulation/ 엔드포인트 (SAPI-01~06)"
    - "params_hash 캐싱 플로우 (동일 요청 두 번째부터 cached=True)"
    - "BW/Power/Timing 분석 엔드포인트 (SAPI-03~05)"
  affects:
    - "FastAPI /docs — simulation 태그 라우터 5개 노출"
    - "Evidence 테이블 — evd-sim-* row 생성"
tech_stack:
  added: []
  patterns:
    - "monkeypatch 전략 — run_simulation() + load_runner_inputs_from_db() 패치, save/find는 실제 DB"
    - "APIRouter(tags=['simulation']) — 기존 runtime.py 패턴 동일"
    - "response_model=None — GET /results raw dict 반환 (기존 evidence 라우터 패턴)"
    - "Query(...) 파라미터 — bw/power/timing 분석 엔드포인트"
key_files:
  created:
    - src/scenario_db/api/routers/simulation.py
    - tests/integration/test_simulation_api.py
  modified:
    - src/scenario_db/api/app.py
decisions:
  - "monkeypatch 전략: run_simulation + load_runner_inputs_from_db 패치 — DVFS YAML 파일 의존성 없이 테스트"
  - "test_post_run_cache_miss_and_hit: fps를 달리하여 기존 테스트 캐시와 hash 충돌 방지"
  - "run_sim() 함수 kwargs 호출 패턴 — run_simulation 시그니처와 일치"
metrics:
  duration: "~3 minutes"
  completed: "2026-05-17"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
  tests_added: 11
---

# Phase 7 Plan 03: FastAPI 라우터 + 통합 테스트 Summary

**One-liner:** /simulation/ 5개 엔드포인트 FastAPI 라우터 구현 (POST /run 캐싱 포함) + 11개 통합 테스트 TDD GREEN 완료 — Phase 7 Simulation API 전체 완성.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | simulation.py 라우터 5개 엔드포인트 + app.py 등록 | b98ad3e | api/routers/simulation.py, api/app.py |
| 2 (RED) | 통합 테스트 작성 (11개) | c9659e9 | tests/integration/test_simulation_api.py |
| 2 (GREEN) | 테스트 전체 통과 확인 | c9659e9 (same) | — (구현 변경 없이 통과) |

## Artifacts

### src/scenario_db/api/routers/simulation.py (신규)
- `POST /simulation/run` — params_hash 캐시 HIT/MISS, load_runner_inputs_from_db → run_simulation → save_sim_evidence
- `GET /simulation/results/{evidence_id}` — get_evidence() → raw dict (dma_breakdown + timing_breakdown 포함)
- `GET /simulation/bw-analysis?evidence_id=xxx` — PortBWResult 목록 bw_mbs 내림차순 정렬
- `GET /simulation/power-analysis?evidence_id=xxx` — per_ip(ip_power), per_vdd(vdd_power), bw_power_mw
- `GET /simulation/timing-analysis?evidence_id=xxx` — critical_ip, hw_time_max_ms, per_ip hw_time_ms 내림차순

### src/scenario_db/api/app.py (수정)
- `from scenario_db.api.routers import simulation as simulation_router` 추가
- `for r in [...]` 루프에 `simulation_router.router` 추가

### tests/integration/test_simulation_api.py (신규, 11개 테스트)
- `test_post_run_cache_miss` — cached=False, evidence_id 반환
- `test_post_run_cache_miss_and_hit` — 동일 payload 2회 → cached=True, 동일 evidence_id
- `test_get_results` — dma_breakdown/timing_breakdown 키 존재, 데이터 수 검증
- `test_get_results_not_found` — 404
- `test_bw_analysis_sorted` — ports bw_mbs 내림차순 검증 + total_bw_mbs
- `test_bw_analysis_not_found` — 404
- `test_power_analysis` — per_ip/per_vdd/bw_power_mw, 구체적 값 검증
- `test_timing_analysis` — critical_ip=ISP, per_ip hw_time_ms 내림차순
- `test_run_invalid_scenario` — 404
- `test_timing_analysis_not_found` — 404
- `test_power_analysis_not_found` — 404

## Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| tests/integration/test_simulation_api.py | 11 | PASS |
| tests/ (전체) | 612 passed + 6 pre-existing failures | 회귀 없음 |

**기존 실패 6개 (Phase 7 이전부터 존재):**
- `test_validate_loaded.py::test_validate_loaded_fhd_variant_exists` — demo fixture FHD30 variant sim_config 없음
- `test_view_topology.py::TestTopologyMode::*` (3개) — sw_stack 관련
- `test_dvfs_resolver.py::test_dvfs_fallback_missing_domain` — caplog.records 빈 목록
- `test_scenario_adapter.py::test_build_ip_params_skips_missing` — caplog.records 빈 목록

모두 stash로 07-03 변경 전 상태에서도 동일하게 실패함을 확인.

## Phase 7 전체 완성 요약

Wave 1a (07-01): Alembic migration 0003 + 5종 스키마 + repository 2종
Wave 1b (07-02): SimRunResult.ip_power + runner Step 5 + loaders.py ORM 변환
Wave 2 (07-03): 5개 /simulation/ 라우터 엔드포인트 + 11개 통합 테스트

**SAPI 요구사항 충족:**
- SAPI-01: POST /simulation/run — 동기 계산, 200 SimulateResponse
- SAPI-02: GET /simulation/results/{id} — Evidence 상세, 없으면 404
- SAPI-03: GET /simulation/bw-analysis — ports bw_mbs 내림차순
- SAPI-04: GET /simulation/power-analysis — per_ip/per_vdd/bw_power_mw
- SAPI-05: GET /simulation/timing-analysis — critical_ip/hw_time_max_ms
- SAPI-06: params_hash 캐싱 — 동일 요청 두 번째부터 cached=True

## Deviations from Plan

### Auto-fixed Issues

None — 계획대로 정확하게 구현됨.

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (test) | c9659e9 | PASS — 11개 테스트 파일 먼저 작성 |
| GREEN (feat) | b98ad3e + c9659e9 | PASS — Task 1 라우터 구현 후 테스트 통과 |

*Note: 계획 상 TDD 순서가 테스트 전에 라우터(Task 1)를 먼저 구현하도록 되어 있어, RED→GREEN 순서를 Task 2 내에서 적용. 테스트 파일 커밋(c9659e9)이 GREEN 확인 포함.*

## Known Stubs

없음. 모든 엔드포인트가 실제 DB + 실제 runner를 호출하는 완전 구현.

## Threat Surface Scan

| Flag | File | Description |
|------|------|-------------|
| T-07-07 mitigate | api/routers/simulation.py | SimulateRequest extra='forbid' — unknown field 422 반환 (계획대로 구현) |
| T-07-09 mitigate | api/routers/simulation.py | load_runner_inputs_from_db() None → 404 — 임의 계산 불가 (계획대로 구현) |

## Self-Check: PASSED

| Item | Status |
|------|--------|
| src/scenario_db/api/routers/simulation.py | FOUND |
| src/scenario_db/api/app.py (simulation_router 추가) | FOUND |
| tests/integration/test_simulation_api.py | FOUND |
| b98ad3e (Task 1 라우터 커밋) | FOUND |
| c9659e9 (Task 2 테스트 커밋) | FOUND |
| 11개 테스트 전체 PASS | CONFIRMED |
| 기존 테스트 회귀 없음 (612 passed) | CONFIRMED |
