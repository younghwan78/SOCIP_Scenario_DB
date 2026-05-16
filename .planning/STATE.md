# Project State

- **Project**: ScenarioDB Viewer MVP & Simulation Engine
- **Current Milestone**: Milestone 1 — Viewer & Runtime
- **Current Phase**: Phase 6 — sim/ Package
- **Status**: Phase 6 COMPLETE (3/3 plans complete).
- **Last Updated**: 2026-05-16

---

## Current Position

```
Milestone 1: Phase 1 ✓ → Phase 2 ✓ → Phase 3 ✓ → Phase 4 ✓
Milestone 2: Phase 5 ✓ → Phase 6 ✓ → [Phase 7]

Progress: ██████████████████░░ 6 / 7 phases complete
```

## Phase Sequence

| Phase | Name | Milestone | Depends On | Status |
|-------|------|-----------|------------|--------|
| 1 | DB Foundation | M1 | — | COMPLETE (3/3 plans) |
| 2 | Resolver & Gate Engine | M1 | Phase 1 | COMPLETE (3/3 plans) |
| 3 | Runtime API | M1 | Phase 1, 2 | COMPLETE (3/3 plans) |
| 4 | Level 0 Viewer DB | M1 | Phase 3 | COMPLETE (3/3 plans) |
| 5 | Schema Extensions | M2 | Phase 1, 4 | COMPLETE (3/3 plans) |
| 6 | sim/ Package | M2 | Phase 5 | COMPLETE (3/3 plans) |
| 7 | Simulation API | M2 | Phase 5, 6 | Not started |

---

## Accumulated Context

### Key Decisions (inherited from PROJECT.md)

| Decision | Outcome |
|----------|---------|
| Resolver 결과 비영속 | gate_executions 테이블 없음, runtime only |
| View sample fallback 제거 | demo 모드만 허용 |
| Simulation porting: Option B | sim/ 패키지 신규 생성, ScenarioGraph 재구현 없음 |
| DVFS 테이블 YAML화 | `hw_config/dvfs-projectA.yaml` |
| D-01 단일 정의 원칙 (Phase 6) | PortBWResult/IPTimingResult는 evidence.simulation에서 re-import — 재정의 없음 |
| DVFS_CONFIG_PATH 배치 (Phase 6) | Settings 클래스 외부 모듈 수준 상수 — 환경변수 불필요 |
| OTF 포트 direction 필드 (Phase 6-02) | Literal[read,write] 제약 충족 위해 read 고정 — bw_mbs=0으로 실질적 의미 없음 |
| compression=disable 시 comp_ratio 무시 (Phase 6-02) | Pitfall 4 방지 — 명시적 분기 구현, BPP_MAP fallback=1.0 보수적 처리 |
| run_simulation() fps 인수 (Phase 6-03) | sensor_spec.fps 우선, 기본값 30.0 — SimGlobalConfig에 fps 필드 없으므로 별도 인수 추가 |
| DvfsResolver OTF required_clock (Phase 6-03) | v_valid_time = (1/fps)*v_valid_ratio, sw_margin 미적용 (Pitfall 2) — DVFS 룩업은 동일한 find_min_level() |
| Soft validation 채택 (Phase 1) | validate_loaded() — 오류 수집 후 리포트, DB 상태 유지 |
| model_validate() + from_attributes=True (Phase 1) | row.__dict__ 패턴 금지 — _sa_instance_state extra='forbid' 위반 |
| 수동 6-쿼리 전략 (Phase 1) | ORM relationship 없이 joinedload/selectinload 금지, 수동 배치 쿼리 |
| JSONB 필드 타입 dict\|list\|None (Phase 1) | ip_breakdown/artifacts/pmu_signature/auto_checks — fixture에서 list 사용 확인 |
| get_view_projection() raw dict 반환 (Phase 1) | Pydantic DTO 없이 raw dict — Phase 3 라우터가 ViewResponse로 변환 |

### Existing Baseline

- FastAPI 36 endpoints + 464 tests (313 unit + 159 integration, all passing); sim/ 41 tests (Phase 6-01: 14, Phase 6-02: 16, Phase 6-03: 11)
- Runtime API: /graph, /resolve, /gate 엔드포인트 (Phase 3 완료)
- View Router: mode 분기 (architecture=DB projection, topology=501)
- ELK Level 0 Viewer (sample data 제거 완료, Phase 4에서 ELK 레이아웃 구현)
- Matcher DSL + RuleCache (Phase 2에서 재사용)
- ETL YAML → DB (Phase 1에서 semantic validation 추가)

### Active Blockers

None.

---

## Session Continuity

_Updated after each phase transition._

- **Phase 1 start**: 2026-05-05
- **Phase 1 context**: 2026-05-06 (`.planning/phases/01-db-foundation/01-CONTEXT.md`)
- **Phase 1 planned**: 2026-05-07 — 3 plans (PLAN-01 Wave1, PLAN-02 Wave1, PLAN-03 Wave2)
- **Phase 1 end**: 2026-05-07 (3 plans complete — validate_loaded, CanonicalScenarioGraph, view_projection + integration tests)
- **Phase 2 start**: 2026-05-08
- **Phase 2 context**: 2026-05-08 (`.planning/phases/02-resolver-gate-engine/02-CONTEXT.md`)
- **Phase 2 planned**: 2026-05-09 — 3 plans (PLAN-01 Wave1: Resolver, PLAN-02 Wave1: Gate, PLAN-03 Wave2: Integration)
- **Phase 2 end**: 2026-05-09 (3 plans complete — ResolverResult, GateExecutionResult, 56 tests passing)
- **Phase 3 start**: 2026-05-10
- **Phase 3 context**: 2026-05-10 (`.planning/phases/03-runtime-api/03-CONTEXT.md`)
- **Phase 3 planned**: 2026-05-10 — 3 plans (PLAN-01 Wave1: Runtime router, PLAN-02 Wave1: View router, PLAN-03 Wave2: Integration tests)
- **Phase 3 end**: 2026-05-10 (3 plans complete — runtime.py router, view mode DB projection, 8 new integration tests, 159 total passing)
- **Phase 4 start**: 2026-05-10
- **Phase 4 context**: 2026-05-10 (`.planning/phases/04-level0-viewer-db/04-CONTEXT.md`)
- **Phase 4 planned**: 2026-05-10 — 3 plans (PLAN-01 Wave1A: service.py 실좌표, PLAN-02 Wave1B: Dashboard HTTP 연동, PLAN-03 Wave2: topology + gate overlay)
- **Phase 4 end**: 2026-05-10 (3 plans complete — _projection_to_view_response, Dashboard HTTP, topology mode + gate overlay, 493 tests passing)
- **Phase 5 start**: 2026-05-10
- **Phase 5 end**: 2026-05-10 (3 plans complete — 8 new Pydantic models, 6 JSONB ORM columns, Alembic migration 0002, ETL serialization, 16 unit + 8 integration tests)
- **Phase 6 start**: 2026-05-11
- **Phase 6 context**: 2026-05-11 (`.planning/phases/06-sim-package/06-CONTEXT.md`)
- **Phase 6 planned**: 2026-05-11 — 3 plans (PLAN-01 Wave1: infra+constants+models, PLAN-02 Wave1: bw/perf/power calc, PLAN-03 Wave2: dvfs_resolver+adapter+runner)
- **Phase 6 PLAN-01 end**: 2026-05-16 (sim/ 인프라 확립, 14 tests passing — commits fc4c338 f350440 673ebde)
- **Phase 6 PLAN-02 end**: 2026-05-16 (bw_calc/perf_calc/power_calc 순수 함수, 16 tests passing — commits a57e02e b4d90b9 56e0018 458474d)
- **Phase 6 PLAN-03 end**: 2026-05-16 (DvfsResolver+scenario_adapter+runner, 11 tests passing, 41 total — commits 053733f 6e2ff4e 9d08d93 9b0fec3)
- **Phase 6 end**: 2026-05-16 (3/3 plans complete — sim/ 패키지 전체 완성, 41 tests, run_simulation() 시그니처 확정)
