---
phase: "05-schema-extensions"
plan: "02"
subsystem: "db/orm + alembic"
tags: [orm, alembic, migration, jsonb, schema-extension]
dependency_graph:
  requires: []
  provides:
    - "IpCatalog.sim_params (JSONB nullable)"
    - "Scenario.sensor (JSONB nullable)"
    - "ScenarioVariant.sim_port_config (JSONB nullable)"
    - "ScenarioVariant.sim_config (JSONB nullable)"
    - "Evidence.dma_breakdown (JSONB nullable)"
    - "Evidence.timing_breakdown (JSONB nullable)"
    - "alembic/versions/0002_schema_extensions.py"
  affects:
    - "ETL mapper (Plan 05-03) — ORM 컬럼에 의존"
tech_stack:
  added: []
  patterns:
    - "SQLAlchemy Column(JSONB) nullable 확장"
    - "Alembic add_column/drop_column 대칭 migration"
key_files:
  created:
    - "alembic/versions/0002_schema_extensions.py"
  modified:
    - "src/scenario_db/db/models/capability.py"
    - "src/scenario_db/db/models/definition.py"
    - "src/scenario_db/db/models/evidence.py"
decisions:
  - "JSONB 컬럼은 nullable=True 기본값 사용 — 기존 레코드 호환성"
  - "autogenerate 금지 — migration 내용을 수동으로 완전히 제어"
  - "downgrade()는 upgrade()의 정확한 역순으로 구성"
metrics:
  duration: "~10min"
  completed: "2026-05-10"
  tasks: 2
  files_modified: 4
---

# Phase 05 Plan 02: ORM + Alembic Migration Schema Extensions Summary

**One-liner:** ORM 3개 파일에 6개 nullable JSONB 컬럼 추가 + Alembic migration 0002 수동 작성으로 `alembic upgrade head` 적용 가능 상태 달성

## Tasks Completed

### Task 1: ORM 3개 파일 nullable JSONB 컬럼 추가

수정된 파일:

| 파일 | 클래스 | 추가된 컬럼 | 요구사항 |
|------|--------|-------------|---------|
| `capability.py` | `IpCatalog` | `sim_params` | SCH-01 |
| `definition.py` | `Scenario` | `sensor` | SCH-03 |
| `definition.py` | `ScenarioVariant` | `sim_port_config`, `sim_config` | SCH-02 |
| `evidence.py` | `Evidence` | `dma_breakdown`, `timing_breakdown` | SCH-04 |

- 모든 컬럼: `Column(JSONB)` (nullable=True 기본값)
- `evidence.py`의 Computed 컬럼(`sw_version_hint`, `sweep_value_hint`) 수정 없음 확인

### Task 2: Alembic Migration 0002 수동 작성

생성된 파일: `alembic/versions/0002_schema_extensions.py`

- `revision = "0002"`, `down_revision = "0001"` — migration 체인 정확
- `upgrade()`: `op.add_column` 6개
- `downgrade()`: `op.drop_column` 6개 (upgrade 역순)
- autogenerate 미사용 — 수동 작성

## ORM 컬럼 ↔ Migration 대응표

| ORM 모델 | 컬럼 | DB 테이블 | Migration 작업 | 요구사항 |
|----------|------|-----------|----------------|---------|
| `IpCatalog.sim_params` | JSONB | `ip_catalog` | `add_column("ip_catalog", "sim_params")` | SCH-01 |
| `Scenario.sensor` | JSONB | `scenarios` | `add_column("scenarios", "sensor")` | SCH-03 |
| `ScenarioVariant.sim_port_config` | JSONB | `scenario_variants` | `add_column("scenario_variants", "sim_port_config")` | SCH-02 |
| `ScenarioVariant.sim_config` | JSONB | `scenario_variants` | `add_column("scenario_variants", "sim_config")` | SCH-02 |
| `Evidence.dma_breakdown` | JSONB | `evidence` | `add_column("evidence", "dma_breakdown")` | SCH-04 |
| `Evidence.timing_breakdown` | JSONB | `evidence` | `add_column("evidence", "timing_breakdown")` | SCH-04 |

## Migration Chain

```
None ← 0001 (initial_schema) ← 0002 (schema_extensions) ← HEAD
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — 모든 컬럼은 nullable JSONB로 선언. 데이터 채우기는 Plan 05-03 ETL mapper 담당.

## Threat Flags

None — 이번 변경은 내부 ORM/migration 레이어 수정이며 신규 네트워크 엔드포인트 없음.

## Self-Check

| 항목 | 결과 |
|------|------|
| `capability.py` IpCatalog.sim_params Column(JSONB) | FOUND (line 32) |
| `definition.py` Scenario.sensor Column(JSONB) | FOUND (line 30) |
| `definition.py` ScenarioVariant.sim_port_config Column(JSONB) | FOUND (line 45) |
| `definition.py` ScenarioVariant.sim_config Column(JSONB) | FOUND (line 46) |
| `evidence.py` Evidence.dma_breakdown Column(JSONB) | FOUND (line 42) |
| `evidence.py` Evidence.timing_breakdown Column(JSONB) | FOUND (line 43) |
| `evidence.py` Computed 컬럼 sw_version_hint 미수정 | CONFIRMED (line 48) |
| `evidence.py` Computed 컬럼 sweep_value_hint 미수정 | CONFIRMED (line 53) |
| `0002_schema_extensions.py` revision="0002" | FOUND (line 19) |
| `0002_schema_extensions.py` down_revision="0001" | FOUND (line 20) |
| `0002_schema_extensions.py` add_column 6개 | CONFIRMED |
| `0002_schema_extensions.py` drop_column 6개 | CONFIRMED |

## Self-Check: PASSED
