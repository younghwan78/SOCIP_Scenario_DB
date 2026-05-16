# ScenarioDB — Viewer MVP & Simulation Engine

## What This Is

Mobile SoC 멀티미디어 IP 시나리오 DB의 Milestone 2: Pipeline Viewer를 DB 기반으로 완성하고
SimEngine(BW/Power/DVFS) 계산 로직을 ScenarioDB `sim/` 패키지로 이식한다.

**Core Value**: 기존 하드코딩 샘플 뷰어를 DB-backed projection으로 전환하고,
실제 HW 파라미터 기반 BW/Power/DVFS 계산 결과를 API로 제공하는 것.

## Context

### What Exists (Validated)

Phase 1~4 + Phase A + Phase B Week 1 완료 상태:

- **4-Layer Pydantic 모델**: Capability / Definition / Evidence / Decision
- **PostgreSQL ORM + Alembic migration** (0001_initial_schema)
- **ETL loader**: YAML → DB (LOAD_ORDER, SAVEPOINT per file)
- **Matcher DSL + RuleCache**: GateRule / Issue 인메모리 캐시, JSONB SQL push-down
- **FastAPI 33 엔드포인트** (29 GET + utility): 209 tests all pass
- **ELK Level 0 Lane Viewer**: Streamlit + SVG 렌더링, 하드코딩 sample data
- **SimEngine 설계 문서**: `docs/simulation-engine-integration.md` — BW/Power/DVFS 공식 완전 문서화
- **구현 로드맵**: `docs/implementation-roadmap-etl-resolver-api-viewer.md`

### What's Missing (Active)

**Milestone 1 — Viewer & Runtime**:
- DB-backed canonical graph builder
- Resolver engine (IP capability mode matching)
- Review Gate engine (GateExecutionResult: PASS/WARN/BLOCK/WAIVER_REQUIRED)
- API: `/graph`, `/resolve`, `/gate` 엔드포인트
- View API DB 연동 (Level 0 projection — `project_level0(db)` 구현)
- Level 0 topology mode (현재 architecture mode만 존재)
- Viewer에 gate result overlay 표시

**Milestone 2 — Simulation Engine**:
- `src/scenario_db/sim/` 패키지 (constants, bw_calc, power_calc, perf_calc, dvfs_resolver)
- IpCatalog `sim_params` 스키마 확장 (ppc, unit_power_mw_mp, vdd, dvfs_group, ports)
- Variant `sim_port_config` + `sim_config` 스키마 확장
- SimulationEvidence 확장 (dma_breakdown, timing_breakdown)
- `sim/runner.py` 전체 파이프라인 오케스트레이터
- `sim/scenario_adapter.py` (Usecase.pipeline + Variant → runner 입력)
- `/simulation/` FastAPI 라우터 (run, results, bw-analysis, power-analysis, timing-analysis)
- params_hash 캐싱 (동일 입력 재계산 생략)

## Requirements

### Validated

- ✓ 4-Layer Pydantic v2 모델 (extra='forbid') — existing
- ✓ PostgreSQL + SQLAlchemy ORM + Alembic — existing
- ✓ ETL YAML → DB (LOAD_ORDER + SAVEPOINT) — existing
- ✓ Matcher DSL + RuleCache — existing
- ✓ FastAPI 33 endpoints, 209 tests — existing
- ✓ ELK Level 0 lane viewer (sample data) — existing

### Active

**Milestone 1 — Viewer & Runtime**

- [ ] **M1-DB**: ETL semantic validation + CanonicalScenarioGraph builder
- [ ] **M1-RESOLVE**: Resolver engine — variant ip_requirements → matched capability mode
- [ ] **M1-GATE**: Review Gate engine — GateExecutionResult (PASS/WARN/BLOCK/WAIVER_REQUIRED)
- [ ] **M1-API**: `/graph`, `/resolve`, `/gate` 엔드포인트
- [ ] **M1-VIEW**: View router DB 연동 — `project_level0(db)` 구현, sample fallback 제거
- [ ] **M1-TOPO**: Level 0 topology mode (SW task/thread/queue 노드 중심)
- [ ] **M1-OVERLAY**: Viewer에서 gate result 오버레이 (risk card + status badge)

**Milestone 2 — Simulation Engine**

- [x] **M2-SIM1**: `sim/` 패키지 — constants, bw_calc, power_calc, perf_calc, dvfs_resolver — Validated in Phase 6
- [x] **M2-SCHEMA**: IpCatalog.sim_params + Variant.sim_port_config + sim_config 스키마 확장 — Validated in Phase 5
- [x] **M2-EVIDENCE**: SimulationEvidence 확장 (dma_breakdown, timing_breakdown) — Validated in Phase 5
- [x] **M2-RUNNER**: `sim/runner.py` + `sim/scenario_adapter.py` — Validated in Phase 6
- [ ] **M2-API**: `/simulation/` 라우터 (run, results, bw-analysis, power-analysis, timing-analysis)
- [ ] **M2-CACHE**: params_hash 캐시 (SHA256 기반 중복 계산 생략)

### Out of Scope

- Level 1 IP DAG / Level 2 drill-down — 다음 Milestone
- SimPy discrete-event 시뮬레이션 (Sim-5) — Phase Sim-5로 분리
- Evidence Dashboard Streamlit 페이지 — Milestone 2 이후
- ParametricSweep ↔ ExplorationEngine 연동 — Milestone 2 이후
- Compare mode — 다음 Milestone
- Excel/Visio import — 범위 외

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Simulation porting 전략: Option B (선택적 포팅) | 단일 코드베이스 + Pydantic v2 표준 유지 | sim/ 패키지 신규 생성 |
| ScenarioGraph 재구현 불필요 | Usecase.pipeline이 이미 동일 구조 | scenario_adapter.py에서 변환 |
| DVFS 테이블 YAML화 | CSV 의존성 제거, 설정 변수화 | hw_config/dvfs-projectA.yaml |
| Resolver 결과는 비영속 (Phase 1) | authored Review와 runtime 결과 분리 | gate_executions 테이블은 나중에 |
| View API: sample fallback 명시 제거 | "Sample data trap" 방지 | demo 모드만 허용 |

## Evolution

이 문서는 phase transition과 milestone 경계에서 업데이트된다.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Out of Scope로 이동
2. Requirements validated? → Validated로 이동
3. 새 requirements 발생? → Active에 추가
4. 결정 사항? → Key Decisions에 기록

**After each milestone** (via `/gsd-complete-milestone`):
1. 전체 섹션 재검토
2. Core Value 재확인
3. Out of Scope 이유 재검토

---
*Last updated: 2026-05-16 — Phase 6 complete (sim/ Package: 9 modules, 41 tests, run_simulation() interface confirmed)*
