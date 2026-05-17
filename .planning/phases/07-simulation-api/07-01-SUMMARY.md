---
phase: 7
plan: "07-01"
subsystem: simulation-api
tags: [alembic, pydantic, repository, tdd, evidence, params-hash]
dependency_graph:
  requires:
    - "Phase 6 — sim/ 패키지 (SimRunResult, PortBWResult, IPTimingResult)"
    - "Phase 5 — Evidence ORM 모델 (migration 0002)"
  provides:
    - "Alembic migration 0003 — Evidence.params_hash 컬럼"
    - "5종 Pydantic 스키마 (SimulateRequest 외 4종)"
    - "simulation repository (save_sim_evidence, find_by_params_hash)"
  affects:
    - "07-03-PLAN — FastAPI 라우터 (Wave 2 의존)"
    - "07-02-PLAN — loaders.py (병렬 Wave 1)"
tech_stack:
  added: []
  patterns:
    - "ConfigDict(extra='forbid') — 모든 API 스키마에 적용"
    - "D-01 단일 정의 원칙 — PortBWResult/IPTimingResult는 evidence.simulation에서 re-import"
    - "TDD RED→GREEN 사이클 — 테스트 먼저, 구현 후 GREEN"
key_files:
  created:
    - alembic/versions/0003_params_hash.py
    - src/scenario_db/api/schemas/simulation.py
    - src/scenario_db/db/repositories/simulation.py
    - tests/unit/test_simulation_schemas.py
  modified:
    - src/scenario_db/db/models/evidence.py
decisions:
  - "D-01 단일 정의 원칙 유지: PortBWResult/IPTimingResult는 evidence.simulation에서 re-import (재정의 금지)"
  - "D-02 params_hash: nullable=True로 기존 evidence 행 보호"
  - "save_sim_evidence: yaml_sha256 = params_hash (YAML 없는 sim evidence)"
  - "find_by_params_hash: order_by id.desc() — 중복 hash 시 최신 행 반환"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-17"
  tasks_completed: 2
  files_created: 4
  files_modified: 1
---

# Phase 7 Plan 01: 인프라 + 스키마 레이어 Summary

**One-liner:** Alembic migration 0003으로 Evidence.params_hash 컬럼 추가, Simulation API 5종 Pydantic 스키마 + save/find repository 2종 구현 (TDD RED→GREEN, 22 tests pass)

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Alembic migration 0003 + Evidence ORM 수정 | 59f6815 | alembic/versions/0003_params_hash.py, db/models/evidence.py |
| TDD RED | 실패하는 스키마 단위 테스트 | 02ffe8c | tests/unit/test_simulation_schemas.py |
| 2 (GREEN) | Pydantic 스키마 5종 + repository 2종 | 1692f12 | api/schemas/simulation.py, db/repositories/simulation.py |

## Artifacts

### alembic/versions/0003_params_hash.py
- `revision = "0003"`, `down_revision = "0002"`
- `op.add_column("evidence", Column("params_hash", Text, nullable=True))`
- `downgrade()`: `op.drop_column("evidence", "params_hash")`

### src/scenario_db/api/schemas/simulation.py
- `SimulateRequest`: scenario_id, variant_id, fps=30.0, dvfs_overrides=None, asv_group=4, extra='forbid'
- `SimulateResponse`: evidence_id, params_hash, cached, feasible, total_power_mw, bw_total_mbs, hw_time_max_ms
- `BwAnalysisResponse`: evidence_id, ports(list[PortBWResult]), total_bw_mbs
- `PowerAnalysisResponse`: evidence_id, total_power_mw, total_power_ma, per_ip(dict), per_vdd(dict), bw_power_mw
- `TimingAnalysisResponse`: evidence_id, feasible, hw_time_max_ms, critical_ip(str|None), per_ip(list[IPTimingResult])

### src/scenario_db/db/repositories/simulation.py
- `save_sim_evidence(db, evidence_id, req, result, params_hash) -> Evidence`
  - `db.add(row)` + `db.commit()` + `db.refresh(row)`
  - ip_breakdown에 `vdd_power` + `ip_power` 모두 저장 (D-06)
  - `yaml_sha256 = params_hash` (YAML 없는 sim evidence)
- `find_by_params_hash(db, params_hash) -> Evidence | None`
  - `filter(params_hash == ..., kind == 'evidence.simulation')`
  - `order_by(Evidence.id.desc())` — 최신 행 우선

## Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| tests/unit/test_simulation_schemas.py | 22 | PASS |
| tests/unit/ (기존) | 420 | PASS (regression 없음) |

## Deviations from Plan

### 자동 확인 항목

**1. [Rule 2 - Missing] `SimRunResult.ip_power` 필드 — 07-02 에이전트 선행 추가**
- **발견 시점:** Task 2 구현 중
- **상황:** D-06에 따라 `ip_power` 필드를 추가하려 했으나, Wave 1 병렬 실행 중인 07-02 에이전트(commit b767f49)가 먼저 `src/scenario_db/sim/models.py`에 해당 필드를 추가함
- **처리:** 이미 추가된 필드를 그대로 활용 (`default_factory=dict` — backward compatible)
- **영향:** 없음 (의도한 결과)

## Known Stubs

None — 모든 필드가 구체적인 타입과 기본값으로 정의됨.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| T-07-01 처리 예정 | db/repositories/simulation.py | save_sim_evidence()는 scenario_ref에 DB 존재 확인 없이 저장 — 07-03 라우터에서 loaders.py 404 처리로 완화 예정 |

## Self-Check: PASSED

| Item | Status |
|------|--------|
| alembic/versions/0003_params_hash.py | FOUND |
| src/scenario_db/api/schemas/simulation.py | FOUND |
| src/scenario_db/db/repositories/simulation.py | FOUND |
| tests/unit/test_simulation_schemas.py | FOUND |
| 59f6815 (migration commit) | FOUND |
| 02ffe8c (TDD RED commit) | FOUND |
| 1692f12 (GREEN commit) | FOUND |
