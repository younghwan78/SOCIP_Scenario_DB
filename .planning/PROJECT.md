# ScenarioDB — Viewer MVP & Simulation Engine

## What This Is

Mobile SoC 멀티미디어 IP 시나리오 DB 기반 도구.
DB-backed Level 0 Pipeline Viewer (architecture/topology mode + gate overlay)와
실제 HW 파라미터 기반 BW/Power/DVFS 계산 Simulation API를 FastAPI로 제공한다.

**v1.0 MVP shipped 2026-05-17**: 41 endpoints, 612 tests, 7 phases / 28일

## Core Value

시나리오 YAML 한 세트에서 — IP capability 해석, gate 판정, BW/Power/DVFS 수치 계산까지 —
일관된 데이터 모델(Pydantic v2 4-Layer)로 자동화한다.

## Context

### Current State (v1.0 shipped)

- **FastAPI**: 41 endpoints (33개 기존 + 3개 Runtime + 5개 Simulation)
- **Tests**: 612 (346 unit + 266 integration) — 6개 pre-existing failures 존재
- **DB**: PostgreSQL + SQLAlchemy ORM, Alembic migration 0003까지
- **sim/ 패키지**: 9개 모듈 (constants, models, bw_calc, perf_calc, power_calc, dvfs_resolver, scenario_adapter, runner, __init__)
- **FHD30 ISP 기준값**: bw=295.992 MB/s, power=42.494 mW, hw_time=1.361 ms, voltage=660 mV

### What Exists (Validated)

- **4-Layer Pydantic 모델**: Capability / Definition / Evidence / Decision (extra='forbid', from_attributes=True)
- **PostgreSQL ORM + Alembic migration** 0001~0003
- **ETL loader**: YAML → DB (LOAD_ORDER, SAVEPOINT per file) + validate_loaded() semantic validation
- **Matcher DSL + RuleCache**: GateRule / Issue 인메모리 캐시, JSONB SQL push-down
- **Runtime API**: /graph, /resolve, /gate (비영속 Resolver + GateExecutionResult)
- **Level 0 Viewer**: architecture mode (DB projection) + topology mode (SW stack) + gate overlay
- **Schema Extensions**: IpCatalog.sim_params, Variant.sim_port_config/sim_config, Usecase.sensor, SimulationEvidence 확장
- **sim/ 패키지**: BW/Power/DVFS/Timing 계산 + DvfsResolver + scenario_adapter + runner
- **Simulation API**: POST /simulation/run + GET results/bw-analysis/power-analysis/timing-analysis + params_hash 캐시

## Requirements

### Validated

- ✓ 4-Layer Pydantic v2 모델 (extra='forbid') — existing
- ✓ PostgreSQL + SQLAlchemy ORM + Alembic — existing
- ✓ ETL YAML → DB (LOAD_ORDER + SAVEPOINT + semantic validation) — v1.0
- ✓ Matcher DSL + RuleCache — existing
- ✓ FastAPI 41 endpoints, 612 tests — v1.0
- ✓ ETL semantic validation (DB-01) — v1.0
- ✓ CanonicalScenarioGraph builder (DB-02) — v1.0
- ✓ Repository 확장 view_projection/scenario_graph (DB-03) — v1.0
- ✓ Resolver Engine 비영속 (RES-01~03) — v1.0
- ✓ Gate Engine PASS/WARN/BLOCK/WAIVER_REQUIRED (GATE-01~05) — v1.0
- ✓ Runtime API /graph, /resolve, /gate (API-01~03) — v1.0
- ✓ View Router DB 연동, sample fallback 제거 (API-04) — v1.0
- ✓ Level 0 Viewer DB 구동 (VIEW-01~02) — v1.0
- ✓ Topology mode SW stack (VIEW-03) — v1.0 (6개 test failures 존재)
- ✓ Gate overlay inspector (VIEW-04) — v1.0
- ✓ Mode selector UI (VIEW-05) — v1.0
- ✓ Schema Extensions 8개 신규 Pydantic 모델 + 6개 JSONB ORM 컬럼 (SCH-01~05) — v1.0
- ✓ sim/ 패키지 9개 모듈 (SIM-01~09) — v1.0
- ✓ Simulation API 5개 엔드포인트 + params_hash 캐싱 (SAPI-01~06) — v1.0

### Active (v1.1)

- [ ] **V11-FIX**: 기존 6개 pre-existing test failures 해소 (topology 3개, caplog 2개, demo fixture 1개)
- [ ] **V11-META**: topology mode ViewSummary.period_ms/budget_ms/resolution/fps DB 연동 (현재 placeholder)
- [ ] **V11-VIEWER**: Viewer 전반 UX 개선 — 사용자 관점에서 점검 후 v1.1 scope 확정

### Out of Scope

- Level 1 IP DAG 렌더링 (Sensor→CSIS→ISP→MLSC→MFC→DPU) — 다음 Milestone
- SimPy discrete-event 시뮬레이션 (Sim-5) — Phase Sim-5로 분리
- Evidence Dashboard Streamlit 페이지 — Milestone 이후
- ParametricSweep ↔ ExplorationEngine 연동 — Milestone 이후
- gate_executions 영속 테이블 — runtime only 원칙 (Deferred)
- Compare mode — 다음 Milestone
- Excel/Visio import — 범위 외
- GPU multimedia IP (MDP, G3D) — ISP/MFC/DPU/CSIS 한정

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Soft validation 채택 (Phase 1) | 오류 수집 후 리포트 — DB 상태 유지 | validate_loaded() 8가지 규칙 |
| Resolver 결과 비영속 | authored Review와 runtime 결과 분리 | gate_executions 테이블 없음 |
| View API sample fallback 제거 | "Sample data trap" 방지 | demo 모드만 허용 |
| Simulation porting: Option B (선택적 포팅) | 단일 코드베이스 + Pydantic v2 표준 | sim/ 패키지 신규 생성 |
| ScenarioGraph 재구현 불필요 | Usecase.pipeline이 이미 동일 구조 | scenario_adapter.py에서 변환 |
| DVFS 테이블 YAML화 | CSV 의존성 제거, 설정 변수화 | hw_config/dvfs-projectA.yaml |
| D-01 단일 정의 원칙 (Phase 6) | 순환 import 방지 | PortBWResult/IPTimingResult는 evidence.simulation에서 re-import |
| DVFS_CONFIG_PATH 배치 (Phase 6) | 환경변수 불필요 | Settings 클래스 외부 모듈 수준 상수 |
| OTF 포트 direction 필드 (Phase 6) | Literal[read,write] 제약 충족 | read 고정, bw_mbs=0 (실질적 의미 없음) |
| monkeypatch 전략 (Phase 7) | DVFS YAML 파일 의존성 없이 통합 테스트 | run_simulation + load_runner_inputs_from_db 패치 |
| model_validate() + from_attributes=True (Phase 1) | row.__dict__ → _sa_instance_state extra='forbid' 위반 방지 | ORM 행 → DTO 변환 패턴 확립 |
| 수동 6-쿼리 전략 (Phase 1) | ORM relationship joinedload 금지 | 수동 배치 쿼리 |

## Constraints

- Python 3.11+ / Pydantic v2 / FastAPI / SQLAlchemy 2.0
- `uv run` 가상환경 필수 — 시스템 Python 금지
- DB: PostgreSQL (testcontainers로 통합 테스트 격리)
- sim/ 패키지: DB/ORM import 없음 — 순수 Pydantic

## Evolution

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
*Last updated: 2026-05-17 after v1.0 milestone — 7 phases shipped (DB Foundation → Simulation API)*
