# Project State

- **Project**: ScenarioDB Viewer MVP & Simulation Engine
- **Current Milestone**: Milestone 1 — Viewer & Runtime
- **Current Phase**: Phase 1 — DB Foundation
- **Status**: Ready to plan
- **Last Updated**: 2026-05-05

---

## Current Position

```
Milestone 1: [Phase 1] → Phase 2 → Phase 3 → Phase 4
Milestone 2: Phase 5 → Phase 6 → Phase 7

Progress: ░░░░░░░░░░░░░░░░░░░░ 0 / 7 phases complete
```

## Phase Sequence

| Phase | Name | Milestone | Depends On | Status |
|-------|------|-----------|------------|--------|
| 1 | DB Foundation | M1 | — | Not started |
| 2 | Resolver & Gate Engine | M1 | Phase 1 | Not started |
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
- **Phase 1 end**: TBD
- **Phase 2 start**: TBD
