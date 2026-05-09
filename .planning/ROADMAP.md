# Roadmap — ScenarioDB Viewer MVP & Simulation Engine

_Created: 2026-05-05_

---

## Phases

- [x] **Phase 1: DB Foundation** — ETL semantic validation + CanonicalScenarioGraph builder + repository 확장
- [x] **Phase 2: Resolver & Gate Engine** — 비영속 Resolver + GateExecutionResult 엔진 (순수 Python)
- [ ] **Phase 3: Runtime API** — /graph, /resolve, /gate 엔드포인트 + view router DB 연동
- [ ] **Phase 4: Level 0 Viewer DB** — project_level0(db) 구현, topology mode, gate overlay
- [ ] **Phase 5: Schema Extensions** — IpCatalog.sim_params + Variant.sim_port_config/sim_config + Usecase.sensor + SimulationEvidence 확장
- [ ] **Phase 6: sim/ Package** — constants/models/bw_calc/perf_calc/power_calc/dvfs_resolver/adapter/runner
- [ ] **Phase 7: Simulation API** — /simulation/ 라우터 + params_hash 캐싱

---

## Phase Details

### Phase 1: DB Foundation

**Goal**: DB에서 scenario 전체 그래프를 안전하게 조회할 수 있다 — ETL이 참조 무결성을 보장하고, CanonicalScenarioGraph DTO로 단일 쿼리 조회된다
**Depends on**: Nothing (brownfield 기반 — 기존 ORM/ETL 위에 추가)
**Requirements**: DB-01, DB-02, DB-03
**Success Criteria** (what must be TRUE):
  1. ETL 로드 후 semantic validation이 실행되어 FK-like 참조 오류(존재하지 않는 scenario_id 참조 등)를 감지하고 오류 메시지를 출력한다
  2. `CanonicalScenarioGraph(scenario_id, variant_id)` 호출 시 scenario + variant + project + evidence + issues + waivers + reviews를 단일 DTO로 반환한다
  3. `view_projection` 쿼리와 `scenario_graph` 쿼리가 Repository 메서드로 캡슐화되어 서비스 레이어에서 직접 ORM 쿼리를 쓰지 않는다
  4. 존재하지 않는 scenario_id 요청 시 명확한 NotFound 응답이 반환된다
**Plans**: 3 plans
Plans:
**Wave 1** *(병렬 실행 가능)*
- [x] 01-PLAN-01.md — ETL semantic validation (validate_loaded.py + loader.py 통합 + FHD30 fixture)
- [x] 01-PLAN-02.md — CanonicalScenarioGraph DTO + get_canonical_graph() 구현

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 01-PLAN-03.md — view_projection Repository + Phase 1 통합 테스트 완성

Cross-cutting constraints:
- 모든 Pydantic DTO: `ConfigDict(extra='forbid')` + `from_attributes=True` (D-05, D-07)
**UI hint**: no

---

### Phase 2: Resolver & Gate Engine

**Goal**: variant의 IP requirements가 capability 카탈로그와 매핑되고, gate rule 평가로 PASS/WARN/BLOCK/WAIVER_REQUIRED 판정이 도출된다 — DB 없이 순수 Python으로
**Depends on**: Phase 1 (CanonicalScenarioGraph DTO가 입력)
**Requirements**: RES-01, RES-02, RES-03, GATE-01, GATE-02, GATE-03, GATE-04, GATE-05
**Success Criteria** (what must be TRUE):
  1. `ResolverResult` 모델이 ip_resolutions, sw_resolutions, unresolved_requirements, warnings 필드를 가지며, variant.ip_requirements를 ip_catalog.capabilities에 매핑한 결과를 반환한다
  2. Resolver 결과가 DB에 저장되지 않는다 (비영속 — authored Review 테이블과 분리)
  3. `GateExecutionResult` 모델이 status(PASS/WARN/BLOCK/WAIVER_REQUIRED), matched_rules, matched_issues, applicable_waivers, missing_waivers를 포함한다
  4. blocking rule이 존재하면 status가 BLOCK이 되고, waiver가 없는 issue는 WAIVER_REQUIRED가 된다
  5. 우선순위(BLOCK > WAIVER_REQUIRED > WARN > PASS) 집계가 올바르게 작동한다 — 단위 테스트로 검증
**Plans**: 3 plans
Plans:
**Wave 1** *(병렬 실행 가능)*
- [x] 02-PLAN-01.md — Resolver Engine (ResolverResult 모델 + resolve() 함수 + 단위 테스트)
- [x] 02-PLAN-02.md — Gate Engine (GateExecutionResult 모델 + $-DSL + evaluate_gate() + 단위 테스트)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 02-PLAN-03.md — Phase 2 통합 테스트 + ROADMAP 업데이트

Cross-cutting constraints:
- 모든 Pydantic DTO: `ConfigDict(extra='forbid')` (CONTEXT.md D-05, D-07 준수)
- DB 의존성 없음: resolve()와 evaluate_gate() 모두 순수 Python 함수 (RES-03)
**UI hint**: no

---

### Phase 3: Runtime API

**Goal**: /graph, /resolve, /gate 세 엔드포인트가 동작하고, view router가 sample fallback 없이 DB projection을 반환한다
**Depends on**: Phase 1, Phase 2
**Requirements**: API-01, API-02, API-03, API-04
**Success Criteria** (what must be TRUE):
  1. `GET /api/v1/scenarios/{id}/variants/{vid}/graph` 가 CanonicalScenarioGraph JSON을 반환한다
  2. `GET /api/v1/scenarios/{id}/variants/{vid}/resolve` 가 ResolverResult JSON을 반환한다
  3. `GET /api/v1/scenarios/{id}/variants/{vid}/gate` 가 GateExecutionResult JSON을 반환한다
  4. view router의 `mode` 파라미터(architecture|topology)가 실제로 분기되고, sample fallback 코드 경로가 제거된다
  5. 기존 209개 테스트가 모두 통과하고, 신규 3개 엔드포인트에 대한 통합 테스트가 추가된다
**Plans**: TBD
**UI hint**: no

---

### Phase 4: Level 0 Viewer DB

**Goal**: Streamlit Level 0 뷰어가 DB 데이터를 렌더링하며, topology mode와 gate overlay가 작동한다
**Depends on**: Phase 3 (API가 DB 데이터 제공)
**Requirements**: VIEW-01, VIEW-02, VIEW-03, VIEW-04, VIEW-05
**Success Criteria** (what must be TRUE):
  1. `project_level0(db, scenario_id, variant_id)` 가 DB에서 레인 데이터를 조회하여 ELK 그래프로 렌더링한다 (하드코딩 sample data 없음)
  2. architecture mode에서 기존 레인 뷰(HW IP + AXI bus lane)가 DB 데이터로 구동된다
  3. topology mode에서 SW stack 레인(Camera App → CameraService → HAL → Driver → IP)이 렌더링된다
  4. 인스펙터 패널에 GateExecutionResult(status badge + matched_rules risk card)가 표시된다
  5. Streamlit UI에 `mode=architecture|topology` radio selector가 존재하고 선택 시 레이아웃이 전환된다
**Plans**: TBD
**UI hint**: yes

---

### Phase 5: Schema Extensions

**Goal**: sim/ 패키지가 필요로 하는 모든 추가 필드가 Pydantic 모델 + ORM + Alembic migration으로 반영된다
**Depends on**: Phase 1 (기존 ORM 구조 위에 추가), Phase 4 (Milestone 1 완료 확인)
**Requirements**: SCH-01, SCH-02, SCH-03, SCH-04, SCH-05
**Success Criteria** (what must be TRUE):
  1. `IpCatalog.sim_params: IPSimParams | None` 필드가 Pydantic 모델과 ORM 컬럼으로 존재하고, 기존 YAML 픽스처가 sim_params 없이도 로드된다 (하위 호환 Optional)
  2. `Variant.sim_port_config` 와 `Variant.sim_config` 가 Pydantic 모델과 ORM JSONB 컬럼으로 존재한다
  3. `Usecase.sensor: SensorSpec | None` 필드가 추가되어 OTF v_valid_time 입력값을 담는다
  4. `SimulationEvidence` 가 `dma_breakdown: list[PortBWResult]` 와 `timing_breakdown: list[IPTimingResult]` 를 포함하도록 확장된다
  5. Alembic migration이 생성되어 기존 DB에 `alembic upgrade head` 로 스키마가 적용된다
**Plans**: TBD
**UI hint**: no

---

### Phase 6: sim/ Package

**Goal**: BW/Power/DVFS/Timing 계산 로직이 `src/scenario_db/sim/` 패키지로 이식되고, runner가 전체 파이프라인을 오케스트레이션한다
**Depends on**: Phase 5 (IPSimParams, PortBWResult, IPTimingResult 모델 존재)
**Requirements**: SIM-01, SIM-02, SIM-03, SIM-04, SIM-05, SIM-06, SIM-07, SIM-08, SIM-09
**Success Criteria** (what must be TRUE):
  1. `sim/constants.py` 에 BPP_MAP, BW_POWER_COEFF_DEFAULT, REFERENCE_VOLTAGE_MV 상수가 정의되고, `sim/models.py` 의 모든 Pydantic v2 모델이 round-trip 직렬화 테스트를 통과한다
  2. `calc_port_bw()` 가 OTF 포트를 제외하고 comp_ratio/llc_weight를 적용한 BW(MB/s)를 반환한다 — 단위 테스트로 계산값 검증
  3. `calc_processing_time()` 이 h_blank_margin 포함 처리시간(ms)을 반환하고, `calc_active_power()` 가 V² 스케일링 + fps 스케일링을 적용한다
  4. `DvfsResolver` 가 OTF 그룹 v_valid_time 제약을 지키며 VDD 도메인 전압을 정렬하고, `dvfs-projectA.yaml` 이 CAM/INT/MIF 도메인을 정의한다
  5. `scenario_adapter.py` 가 Usecase.pipeline + Variant.sim_port_config를 runner 입력으로 변환하고, `runner.py` 가 전체 파이프라인을 실행하여 `SimRunResult` 를 반환한다
**Plans**: TBD
**UI hint**: no

---

### Phase 7: Simulation API

**Goal**: /simulation/ 라우터가 동기 계산 실행, 결과 조회, BW/Power/Timing 분석을 제공하고, params_hash 캐싱으로 중복 계산을 생략한다
**Depends on**: Phase 6 (sim/runner 완료), Phase 5 (SimulationEvidence ORM)
**Requirements**: SAPI-01, SAPI-02, SAPI-03, SAPI-04, SAPI-05, SAPI-06
**Success Criteria** (what must be TRUE):
  1. `POST /simulation/run` 이 SimulateRequest를 받아 동기 계산 후 SimulationEvidence를 DB에 저장하고 evidence_id를 반환한다
  2. `GET /simulation/results/{evidence_id}` 가 dma_breakdown + timing_breakdown 포함 SimulationEvidence 상세를 반환한다
  3. `GET /simulation/bw-analysis` 가 PortBWResult 목록을 bw_mbs 내림차순으로 반환하고, `GET /simulation/power-analysis` 가 total_power/per_ip/per_vdd/bw_power를 반환한다
  4. `GET /simulation/timing-analysis` 가 critical_ip/hw_time_max_ms/per_ip/feasible을 반환한다
  5. 동일 SHA256 params_hash로 두 번 요청하면 재계산 없이 캐시된 evidence_id를 즉시 반환한다
**Plans**: TBD
**UI hint**: no

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. DB Foundation | 3/3 | COMPLETE | 2026-05-07 |
| 2. Resolver & Gate Engine | 3/3 | COMPLETE | 2026-05-09 |
| 3. Runtime API | 0/3 | Not started | - |
| 4. Level 0 Viewer DB | 0/3 | Not started | - |
| 5. Schema Extensions | 0/3 | Not started | - |
| 6. sim/ Package | 0/4 | Not started | - |
| 7. Simulation API | 0/3 | Not started | - |

---

## Coverage Map

| REQ-ID | Phase |
|--------|-------|
| DB-01 | Phase 1 |
| DB-02 | Phase 1 |
| DB-03 | Phase 1 |
| RES-01 | Phase 2 |
| RES-02 | Phase 2 |
| RES-03 | Phase 2 |
| GATE-01 | Phase 2 |
| GATE-02 | Phase 2 |
| GATE-03 | Phase 2 |
| GATE-04 | Phase 2 |
| GATE-05 | Phase 2 |
| API-01 | Phase 3 |
| API-02 | Phase 3 |
| API-03 | Phase 3 |
| API-04 | Phase 3 |
| VIEW-01 | Phase 4 |
| VIEW-02 | Phase 4 |
| VIEW-03 | Phase 4 |
| VIEW-04 | Phase 4 |
| VIEW-05 | Phase 4 |
| SCH-01 | Phase 5 |
| SCH-02 | Phase 5 |
| SCH-03 | Phase 5 |
| SCH-04 | Phase 5 |
| SCH-05 | Phase 5 |
| SIM-01 | Phase 6 |
| SIM-02 | Phase 6 |
| SIM-03 | Phase 6 |
| SIM-04 | Phase 6 |
| SIM-05 | Phase 6 |
| SIM-06 | Phase 6 |
| SIM-07 | Phase 6 |
| SIM-08 | Phase 6 |
| SIM-09 | Phase 6 |
| SAPI-01 | Phase 7 |
| SAPI-02 | Phase 7 |
| SAPI-03 | Phase 7 |
| SAPI-04 | Phase 7 |
| SAPI-05 | Phase 7 |
| SAPI-06 | Phase 7 |

**Coverage: 39/39 v1 requirements mapped.**
