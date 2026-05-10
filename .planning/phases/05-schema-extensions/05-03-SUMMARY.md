---
phase: "05-schema-extensions"
plan: "03"
subsystem: "etl/mappers + integration tests"
tags: [etl, integration-test, jsonb, alembic, backward-compat]
dependency_graph:
  requires:
    - "05-01 (Pydantic 모델 확장)"
    - "05-02 (ORM + Alembic migration 0002)"
  provides:
    - "capability.py upsert_ip() sim_params 직렬화"
    - "definition.py upsert_usecase() sensor/sim_port_config/sim_config 직렬화"
    - "evidence.py upsert_simulation() dma_breakdown/timing_breakdown 직렬화"
    - "tests/integration/test_schema_extensions.py (8 tests)"
  affects:
    - "ETL 전체 파이프라인 — Pydantic → ORM → DB JSONB 컬럼"
tech_stack:
  added: []
  patterns:
    - "model_dump(exclude_none=True) for Optional single model"
    - "list comprehension model_dump() for list[Model]"
    - "dict comprehension model_dump() for dict[str, Model]"
    - "pytestmark = pytest.mark.integration + testcontainers PostgresContainer"
key_files:
  created:
    - "tests/integration/test_schema_extensions.py"
  modified:
    - "src/scenario_db/etl/mappers/capability.py"
    - "src/scenario_db/etl/mappers/definition.py"
    - "src/scenario_db/etl/mappers/evidence.py"
decisions:
  - "obj.dma_breakdown은 Field(default_factory=list)이므로 None 체크 불필요 — 항상 list comprehension 직접 적용"
  - "통합 테스트에서 id 충돌 방지를 위해 upsert 시 별도 id 할당 (session scope engine 공유)"
  - "test_migration_downgrade_upgrade_cycle에서 inspect() 호출 시 engine.connect() 내 새 connection 사용 — 캐시 무효화 보장"
metrics:
  duration: "~15min"
  completed: "2026-05-10"
  tasks: 2
  files_modified: 4
---

# Phase 05 Plan 03: ETL 매퍼 확장 + 통합 테스트 Summary

**One-liner:** ETL 매퍼 3파일에 6개 신규 JSONB 필드 직렬화 추가 + Alembic 0002 migration과 ETL backward compat을 Docker PostgreSQL testcontainers로 8개 통합 테스트 검증 완료

## Tasks Completed

### Task 1: ETL 매퍼 3개 파일 신규 필드 직렬화 추가

**커밋:** `8d4f665` — `feat(05-03): ETL 매퍼 3파일 — 신규 필드 직렬화 추가`

#### 수정 내용

| 파일 | 함수 | 추가된 라인 | 패턴 |
|------|------|------------|------|
| `capability.py` | `upsert_ip()` | `row.sim_params = obj.sim_params.model_dump(exclude_none=True) if obj.sim_params else None` | Optional 단일 모델 |
| `definition.py` | `upsert_usecase()` | `row.sensor = obj.sensor.model_dump(exclude_none=True) if obj.sensor else None` | Optional 단일 모델 |
| `definition.py` | `upsert_usecase()` variant loop | `vrow.sim_port_config = {k: cfg.model_dump(...) for k, cfg in v.sim_port_config.items()} if v.sim_port_config else None` | dict[str, Model] |
| `definition.py` | `upsert_usecase()` variant loop | `vrow.sim_config = v.sim_config.model_dump(exclude_none=True) if v.sim_config else None` | Optional 단일 모델 |
| `evidence.py` | `upsert_simulation()` | `row.dma_breakdown = [b.model_dump(exclude_none=True) for b in obj.dma_breakdown]` | list[Model] |
| `evidence.py` | `upsert_simulation()` | `row.timing_breakdown = [t.model_dump(exclude_none=True) for t in obj.timing_breakdown]` | list[Model] |

#### 검증

- ETL mapper import: `ETL mapper imports OK`
- 단위 테스트: **357 passed, 0 failed** (회귀 없음)
- 금지 패턴(`vars()`, `__dict__`) 부재 확인

---

### Task 2: 통합 테스트 test_schema_extensions.py 작성

**커밋:** `5b4e28e` — `feat(05-03): 통합 테스트 test_schema_extensions.py 작성`

#### 테스트 목록

| 테스트 | 검증 내용 | 결과 |
|--------|-----------|------|
| `test_new_columns_exist_after_migration` | ip_catalog/scenarios/scenario_variants/evidence 신규 컬럼 6개 존재 | PASSED |
| `test_sim_params_etl_null_backward_compat` | sim_params 없는 기존 fixture → ip_catalog.sim_params = NULL | PASSED |
| `test_sim_params_etl_populated` | ip-isp-v12-with-sim.yaml → sim_params JSONB 저장, hw_name_in_sim/ports 확인 | PASSED |
| `test_sensor_etl_null_backward_compat` | sensor 없는 uc-camera-recording.yaml → scenarios.sensor = NULL | PASSED |
| `test_variant_sim_config_etl_null_backward_compat` | variant에 sim_port_config 없음 → NULL 저장 | PASSED |
| `test_dma_breakdown_etl_empty_default` | breakdown 없는 기존 sim evidence → dma_breakdown = NULL 또는 [] | PASSED |
| `test_dma_breakdown_etl_populated` | sim-FHD30-with-breakdown.yaml → dma_breakdown JSONB 저장, feasible 확인 | PASSED |
| `test_migration_downgrade_upgrade_cycle` | downgrade 0001 → sim_params 컬럼 삭제 확인 → upgrade head → sim_params 복원 확인 | PASSED |

**8 passed, 0 failed** (Docker PostgreSQL testcontainers 사용)

## ETL 직렬화 패턴 grep 확인

```
capability.py:37:    row.sim_params     = obj.sim_params.model_dump(exclude_none=True) if obj.sim_params else None
definition.py:35:    row.sensor         = obj.sensor.model_dump(exclude_none=True) if obj.sensor else None
definition.py:54:        vrow.sim_port_config = (
definition.py:55:            {k: cfg.model_dump(exclude_none=True) for k, cfg in v.sim_port_config.items()}
definition.py:56:            if v.sim_port_config else None
definition.py:58:        vrow.sim_config = v.sim_config.model_dump(exclude_none=True) if v.sim_config else None
evidence.py:34:    row.dma_breakdown       = [b.model_dump(exclude_none=True) for b in obj.dma_breakdown]
evidence.py:35:    row.timing_breakdown    = [t.model_dump(exclude_none=True) for t in obj.timing_breakdown]
```

## 3-Layer 연결 완성

```
Pydantic 모델 (05-01) → ETL 매퍼 (05-03) → ORM 컬럼 (05-02) → DB JSONB
IpCatalog.sim_params   → row.sim_params    → ip_catalog.sim_params JSONB
Usecase.sensor         → row.sensor        → scenarios.sensor JSONB
Variant.sim_port_config → vrow.sim_port_config → scenario_variants.sim_port_config JSONB
Variant.sim_config     → vrow.sim_config   → scenario_variants.sim_config JSONB
SimEvidence.dma_breakdown → row.dma_breakdown → evidence.dma_breakdown JSONB
SimEvidence.timing_breakdown → row.timing_breakdown → evidence.timing_breakdown JSONB
```

## Deviations from Plan

### Auto-fixed Issues

**[Rule 2 - Missing critical functionality] id 충돌 방지 로직 추가**
- **Found during:** Task 2 통합 테스트 작성
- **Issue:** session scope engine을 모든 테스트가 공유하므로, 기존 ETL 로드된 데이터와 id 충돌 가능
- **Fix:** 테스트별로 고유 id를 할당하여 upsert 시 충돌 방지
- **Files modified:** `tests/integration/test_schema_extensions.py`

**[Rule 2 - Missing critical functionality] inspect() 캐시 무효화 처리**
- **Found during:** Task 2 downgrade/upgrade cycle 테스트
- **Issue:** engine-level Inspector 캐시 때문에 downgrade 후 컬럼 목록이 갱신되지 않을 수 있음
- **Fix:** `engine.connect()` 컨텍스트 내 새 connection으로 inspect 호출
- **Files modified:** `tests/integration/test_schema_extensions.py`

## Known Stubs

None — 모든 ETL 직렬화 로직이 실제 model_dump()로 구현됨.

## Threat Flags

None — ETL mapper 수정과 통합 테스트는 내부 레이어이며 신규 네트워크 엔드포인트 없음.

## Self-Check: PASSED

| 항목 | 결과 |
|------|------|
| `capability.py` row.sim_params model_dump 라인 | FOUND (line 37) |
| `definition.py` row.sensor model_dump 라인 | FOUND (line 35) |
| `definition.py` vrow.sim_port_config 라인 | FOUND (line 54-57) |
| `definition.py` vrow.sim_config 라인 | FOUND (line 58) |
| `evidence.py` row.dma_breakdown list comprehension | FOUND (line 34) |
| `evidence.py` row.timing_breakdown list comprehension | FOUND (line 35) |
| 통합 테스트 8개 PASSED | CONFIRMED |
| 단위 테스트 357개 PASSED (회귀 없음) | CONFIRMED |
| 커밋 8d4f665 존재 | CONFIRMED |
| 커밋 5b4e28e 존재 | CONFIRMED |
