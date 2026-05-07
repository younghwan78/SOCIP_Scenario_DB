# Project State

- **Project**: ScenarioDB Viewer MVP & Simulation Engine
- **Current Milestone**: Milestone 1 — Viewer & Runtime
- **Current Phase**: Phase 2 — Resolver & Gate Engine
- **Status**: Phase 2 context gathered. Ready for planning.
- **Last Updated**: 2026-05-08

---

## Current Position

```
Milestone 1: Phase 1 ✓ → [Phase 2] → Phase 3 → Phase 4
Milestone 2: Phase 5 → Phase 6 → Phase 7

Progress: ███░░░░░░░░░░░░░░░░░ 1 / 7 phases complete
```

## Phase Sequence

| Phase | Name | Milestone | Depends On | Status |
|-------|------|-----------|------------|--------|
| 1 | DB Foundation | M1 | — | COMPLETE (3/3 plans) |
| 2 | Resolver & Gate Engine | M1 | Phase 1 | Context gathered — Ready to plan |
| 3 | Runtime API | M1 | Phase 1, 2 | Not started |
| 4 | Level 0 Viewer DB | M1 | Phase 3 | Not started |
| 5 | Schema Extensions | M2 | Phase 1, 4 | Not started |
| 6 | sim/ Package | M2 | Phase 5 | Not started |
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
| Soft validation 채택 (Phase 1) | validate_loaded() — 오류 수집 후 리포트, DB 상태 유지 |
| model_validate() + from_attributes=True (Phase 1) | row.__dict__ 패턴 금지 — _sa_instance_state extra='forbid' 위반 |
| 수동 6-쿼리 전략 (Phase 1) | ORM relationship 없이 joinedload/selectinload 금지, 수동 배치 쿼리 |
| JSONB 필드 타입 dict\|list\|None (Phase 1) | ip_breakdown/artifacts/pmu_signature/auto_checks — fixture에서 list 사용 확인 |
| get_view_projection() raw dict 반환 (Phase 1) | Pydantic DTO 없이 raw dict — Phase 3 라우터가 ViewResponse로 변환 |

### Existing Baseline

- FastAPI 33 endpoints + 209 tests (all passing)
- ELK Level 0 Viewer (hardcoded sample data — Phase 4에서 교체)
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
