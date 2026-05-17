# Project State

- **Project**: ScenarioDB Viewer MVP & Simulation Engine
- **Current Milestone**: v1.0 SHIPPED — next: v1.1 (Viewer 개선)
- **Current Phase**: — (모든 v1.0 phases 완료, v1.1 미시작)
- **Status**: v1.0 MVP COMPLETE. 41 endpoints, 612 tests.
- **Last Updated**: 2026-05-17

---

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-17)

**Core value**: 시나리오 YAML 한 세트에서 IP capability 해석, gate 판정, BW/Power/DVFS 수치 계산까지 일관된 Pydantic v2 4-Layer 모델로 자동화
**Current focus**: v1.1 계획 — Viewer 점검 후 신규 마일스톤 설정 (`/gsd-new-milestone`)

---

## Current Position

```
v1.0 MVP: Phase 1 ✓ → Phase 2 ✓ → Phase 3 ✓ → Phase 4 ✓ → Phase 5 ✓ → Phase 6 ✓ → Phase 7 ✓

Progress: ████████████████████ 7 / 7 phases complete — SHIPPED v1.0
```

---

## Accumulated Context

### Key Decisions (latest)

| Decision | Outcome |
|----------|---------|
| monkeypatch 전략 (Phase 7-03) | run_simulation + load_runner_inputs_from_db 패치 — DVFS YAML 파일 의존성 없이 통합 테스트 |
| Resolver 결과 비영속 | gate_executions 테이블 없음, runtime only |
| View sample fallback 제거 | demo 모드만 허용 |
| Simulation porting: Option B | sim/ 패키지 신규 생성, ScenarioGraph 재구현 없음 |
| D-01 단일 정의 원칙 (Phase 6) | PortBWResult/IPTimingResult는 evidence.simulation에서 re-import |
| DVFS_CONFIG_PATH 배치 (Phase 6) | Settings 클래스 외부 모듈 수준 상수 — 환경변수 불필요 |

### Existing Baseline (v1.0 shipped)

- FastAPI 41 endpoints + 612 tests (unit + integration, 6개 pre-existing failures 존재)
- Simulation API: 5 endpoints + 11 integration tests
- Runtime API: /graph, /resolve, /gate
- Level 0 Viewer: architecture + topology mode + gate overlay (ELK 기반)
- sim/ 패키지: 9개 모듈, FHD30 ISP: 295.992 MB/s, 42.494 mW, 660mV
- ETL semantic validation (8가지 FK-like 규칙)
- Alembic migrations: 0001~0003

### Open Issues for v1.1

- 6개 pre-existing test failures:
  1. `test_validate_loaded.py::test_validate_loaded_fhd_variant_exists` — demo fixture FHD30 variant sim_config 없음
  2. `test_view_topology.py::TestTopologyMode::*` (3개) — sw_stack 관련
  3. `test_dvfs_resolver.py::test_dvfs_fallback_missing_domain` — caplog.records 빈 목록
  4. `test_scenario_adapter.py::test_build_ip_params_skips_missing` — caplog.records 빈 목록
- topology mode ViewSummary.period_ms/budget_ms/resolution/fps → placeholder 값

### Active Blockers

None.

---

## Session Continuity

- **v1.0 shipped**: 2026-05-17
- **v1.0 tag**: `v1.0`
- **All phases archived**: `.planning/milestones/v1.0-ROADMAP.md`
