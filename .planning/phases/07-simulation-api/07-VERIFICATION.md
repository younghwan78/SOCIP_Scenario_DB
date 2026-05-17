---
phase: 07-simulation-api
verified: 2026-05-17T00:00:00Z
status: passed
score: 7/7 must-haves verified
overrides_applied: 0
---

# Phase 7: Simulation API Verification Report

**Phase Goal:** Phase 6에서 구현한 run_simulation()을 FastAPI 라우터로 노출. 5개 엔드포인트 구현, params_hash 기반 캐싱, Evidence 저장.
**Verified:** 2026-05-17
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | POST /api/v1/simulation/run 이 SimulateRequest를 받아 동기 계산 후 SimulateResponse를 반환한다 | VERIFIED | simulation.py:38-109, 통합 테스트 test_post_run_cache_miss PASSED |
| 2 | GET /api/v1/simulation/results/{evidence_id} 가 dma_breakdown + timing_breakdown 포함 Evidence JSON을 반환한다 | VERIFIED | simulation.py:112-139, 통합 테스트 test_get_results PASSED |
| 3 | GET /api/v1/simulation/bw-analysis 가 bw_mbs 내림차순 PortBWResult 목록을 반환한다 | VERIFIED | simulation.py:142-161, sorted(..., reverse=True) 확인, test_bw_analysis_sorted PASSED |
| 4 | GET /api/v1/simulation/power-analysis 가 total_power/per_ip/per_vdd/bw_power를 반환한다 | VERIFIED | simulation.py:164-194, test_power_analysis PASSED (per_ip ISP=700.0, bw_power_mw=296.0 검증) |
| 5 | GET /api/v1/simulation/timing-analysis 가 critical_ip/hw_time_max_ms/per_ip/feasible을 반환한다 | VERIFIED | simulation.py:197-224, test_timing_analysis PASSED (critical_ip="ISP" 검증) |
| 6 | 동일 params_hash로 두 번 POST /run 하면 두 번째 응답에서 cached=True를 반환한다 | VERIFIED | simulation.py:56-67 find_by_params_hash() 캐시 HIT 분기, test_post_run_cache_miss_and_hit PASSED |
| 7 | 존재하지 않는 evidence_id 조회 시 404를 반환한다 | VERIFIED | 4개 404 테스트 (test_get_results_not_found, test_bw_analysis_not_found, test_timing_analysis_not_found, test_power_analysis_not_found) 전부 PASSED |

**Score:** 7/7 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `alembic/versions/0003_params_hash.py` | Evidence.params_hash 컬럼 migration | VERIFIED | revision="0003", down_revision="0002", op.add_column("evidence", Text nullable=True) |
| `src/scenario_db/api/schemas/simulation.py` | 5종 Pydantic 스키마 | VERIFIED | SimulateRequest, SimulateResponse, BwAnalysisResponse, PowerAnalysisResponse, TimingAnalysisResponse 모두 존재, extra='forbid', 22 unit tests PASSED |
| `src/scenario_db/db/repositories/simulation.py` | save_sim_evidence(), find_by_params_hash() | VERIFIED | db.add+db.commit+db.refresh 패턴, filter(params_hash==..., kind=='evidence.simulation').order_by(id.desc()) 패턴 |
| `src/scenario_db/db/loaders.py` | load_runner_inputs_from_db(), compute_params_hash(), apply_request_overrides() | VERIFIED | 3개 함수 모두 존재, sort_keys=True SHA256, DVFS YAML 실제 구조 기반 파싱, 13 unit tests PASSED |
| `src/scenario_db/sim/models.py` | SimRunResult.ip_power 필드 추가 | VERIFIED | ip_power: dict[str, float] = Field(default_factory=dict) — Phase 7 추가 |
| `src/scenario_db/sim/runner.py` | Step 5 ip_power 수집 로직 | VERIFIED | ip_power 선언(L161), ip_power[ip_name] 수집(L197), 두 return 경로 모두 ip_power= 인수 포함 |
| `src/scenario_db/api/routers/simulation.py` | 5개 엔드포인트 라우터 | VERIFIED | APIRouter(tags=["simulation"]), 5개 route handler 완전 구현 |
| `src/scenario_db/api/app.py` | simulation router 등록 | VERIFIED | simulation_router import + for loop에 simulation_router.router 추가 |
| `tests/unit/test_simulation_schemas.py` | 스키마 단위 테스트 | VERIFIED | 22 tests PASSED |
| `tests/unit/test_loaders.py` | loaders 단위 테스트 | VERIFIED | 13 tests PASSED (compute_params_hash 6개, apply_request_overrides 5개, load_runner_inputs_from_db None 2개) |
| `tests/integration/test_simulation_api.py` | TestClient 통합 테스트 | VERIFIED | 11 tests PASSED (캐시 HIT/MISS, 분석 엔드포인트 4개, 404 케이스 4개, invalid scenario 404) |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| POST /simulation/run | find_by_params_hash() 캐시 HIT | params_hash 계산 후 DB 조회 | WIRED | simulation.py:53,56 — compute_params_hash() 호출 후 find_by_params_hash() 호출 |
| POST /simulation/run | load_runner_inputs_from_db() → run_simulation() | scenario/variant ORM 로드 후 runner 호출 | WIRED | simulation.py:70,83 — inputs=None 시 404, 정상이면 run_simulation() kwargs 호출 |
| GET /bw-analysis | Evidence.dma_breakdown JSONB | get_evidence() → dma_breakdown → PortBWResult 파싱 → 정렬 | WIRED | simulation.py:153-154 — sorted(ports, key=lambda p: p.bw_mbs, reverse=True) |
| app.py | simulation.router | include_router(simulation_router.router, prefix='/api/v1') | WIRED | app.py:16,76 — import 및 for loop 등록 확인 |
| find_by_params_hash() | Evidence.params_hash 컬럼 | db.query(Evidence).filter(params_hash=..., kind='evidence.simulation') | WIRED | simulation_repo.py:69-76 — filter + order_by(id.desc()).first() |
| save_sim_evidence() | Evidence ORM | db.add(row); db.commit() | WIRED | simulation_repo.py:58-60 — db.add + db.commit + db.refresh |
| runner.py Step 5 | SimRunResult.ip_power | ip_power[ip_name] = power_mw | WIRED | runner.py:161,197 — 선언 및 수집, 두 return 경로 모두 ip_power= 포함 |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| POST /simulation/run | SimulateResponse.cached | find_by_params_hash() DB 쿼리 | Yes — 실제 DB Evidence 행 조회 | FLOWING |
| POST /simulation/run | SimulateResponse.evidence_id | save_sim_evidence() DB insert | Yes — 실제 DB 저장 후 반환 | FLOWING |
| GET /bw-analysis | BwAnalysisResponse.ports | get_evidence() → dma_breakdown JSONB | Yes — DB JSONB 컬럼에서 실제 데이터 파싱 | FLOWING |
| GET /power-analysis | PowerAnalysisResponse.per_ip | ip_breakdown.ip_power (runner.py D-06) | Yes — runner Step 5에서 수집, DB 저장 후 조회 | FLOWING |
| GET /timing-analysis | TimingAnalysisResponse.critical_ip | timing_breakdown JSONB → sorted max | Yes — DB JSONB 파싱 후 hw_time_ms 기준 정렬 | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 5개 라우트 등록 확인 | python -c "from scenario_db.api.app import create_app; routes=[r.path for r in create_app().routes]; sim=[p for p in routes if 'simulation' in p]; print(sim)" | ['/api/v1/simulation/run', '/api/v1/simulation/results/{evidence_id}', '/api/v1/simulation/bw-analysis', '/api/v1/simulation/power-analysis', '/api/v1/simulation/timing-analysis'] | PASS |
| 11개 통합 테스트 전체 통과 | uv run pytest tests/integration/test_simulation_api.py -v | 11 passed in 2.22s | PASS |
| 스키마+loaders 단위 테스트 | uv run pytest tests/unit/test_simulation_schemas.py tests/unit/test_loaders.py | 35 passed in 0.31s | PASS |
| SHA256 해시 결정론 + 64자 길이 | compute_params_hash(req) 두 번 호출 동일 결과, len=64 | h1==h2, len=64 | PASS |
| SimRunResult.ip_power 기본값 | SimRunResult(...).ip_power == {} | {} | PASS |
| migration 파싱 | ast.parse('alembic/versions/0003_params_hash.py') | parse ok | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SAPI-01 | 07-01, 07-02, 07-03 | POST /simulation/run — 동기 계산, evidence_id 반환 | SATISFIED | simulation.py POST /simulation/run 완전 구현, 통합 테스트 PASSED |
| SAPI-02 | 07-01, 07-03 | GET /simulation/results/{evidence_id} — SimulationEvidence 상세 반환 | SATISFIED | simulation.py GET /simulation/results/{evidence_id}, dma_breakdown+timing_breakdown 포함, 404 처리 |
| SAPI-03 | 07-01, 07-03 | GET /simulation/bw-analysis — PortBWResult 목록 bw_mbs 내림차순 | SATISFIED | sorted(..., reverse=True) 구현, test_bw_analysis_sorted 내림차순 검증 PASSED |
| SAPI-04 | 07-01, 07-03 | GET /simulation/power-analysis — total_power, per_ip, per_vdd, bw_power | SATISFIED | ip_breakdown.ip_power/vdd_power 파싱, sum(bw_power_mw), test_power_analysis PASSED |
| SAPI-05 | 07-01, 07-03 | GET /simulation/timing-analysis — critical_ip, hw_time_max_ms, per_ip, feasible | SATISFIED | timing_sorted[0].ip = critical_ip, test_timing_analysis critical_ip="ISP" 검증 PASSED |
| SAPI-06 | 07-01, 07-02, 07-03 | params_hash 캐싱 — SHA256, 동일 해시 재계산 생략 | SATISFIED | compute_params_hash(SHA256, sort_keys=True) + find_by_params_hash() + cached=True 반환, test_post_run_cache_miss_and_hit PASSED |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | 스텁, TODO, placeholder 없음 |

스캔 대상: simulation.py, schemas/simulation.py, repositories/simulation.py, loaders.py, models.py(ip_power), runner.py(Step 5), app.py

---

## Human Verification Required

없음. 모든 동작이 TestClient 통합 테스트로 프로그래밍적으로 검증됨.

---

## Regression Status

| Suite | Before Phase 7 | After Phase 7 | Delta |
|-------|---------------|--------------|-------|
| tests/sim/ | 41 | 41 | 0 |
| tests/unit/ | ~420 | 442 | +22 (스키마) + 13 (loaders) |
| tests/integration/ | N/A | 11 | +11 |
| 기존 실패 | 6 | 6 | 0 (Phase 7 이전부터 존재) |
| 전체 | ~501 | 612 | +111 신규 |

기존 6개 실패는 Phase 7 변경 이전부터 존재하는 사전 실패임 (demo fixture 미설정, sw_stack topology, caplog.records 빈 목록). Phase 7로 인한 회귀 없음 확인.

---

## Gaps Summary

없음. Phase 7 목표가 완전히 달성되었습니다.

- 5개 /simulation/ 엔드포인트 완전 구현 및 app.py 등록 완료
- params_hash 기반 캐싱 (SAPI-06) 완전 동작 검증
- Evidence 저장 (save_sim_evidence) 및 조회 (find_by_params_hash) 완전 구현
- SimRunResult.ip_power D-06 필드 추가 및 runner.py Step 5 수집 완료
- loaders.py ORM 변환 레이어 완전 구현
- SAPI-01~06 전체 요구사항 충족
- 11개 통합 테스트 전체 PASS, 35개 단위 테스트 전체 PASS

---

_Verified: 2026-05-17_
_Verifier: Claude (gsd-verifier)_
