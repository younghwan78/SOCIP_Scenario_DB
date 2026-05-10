---
phase: 05-schema-extensions
verified: 2026-05-10T00:00:00Z
status: passed
score: 17/17 must-haves verified
overrides_applied: 0
gaps: []
deferred: []
human_verification: []
---

# Phase 5: Schema Extensions — Verification Report

**Phase Goal:** sim/ 패키지가 필요로 하는 모든 추가 필드가 Pydantic 모델 + ORM + Alembic migration으로 반영된다
**Verified:** 2026-05-10
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| #   | Truth                                                                                             | Status     | Evidence                                                                              |
| --- | ------------------------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------- |
| SC1 | IpCatalog.sim_params: IPSimParams \| None 필드가 Pydantic + ORM에 존재, 기존 YAML 하위 호환       | ✓ VERIFIED | hw.py line 121; ORM capability.py line 32; backward compat test PASSED                |
| SC2 | Variant.sim_port_config + sim_config이 Pydantic 모델 + ORM JSONB 컬럼으로 존재                   | ✓ VERIFIED | usecase.py lines 202-203; ORM definition.py lines 45-46; integration test PASSED      |
| SC3 | Usecase.sensor: SensorSpec \| None 필드가 추가되어 OTF v_valid_time 입력값을 담는다               | ✓ VERIFIED | usecase.py line 262; ORM definition.py line 30; ETL definition.py line 35             |
| SC4 | SimulationEvidence가 dma_breakdown: list[PortBWResult] + timing_breakdown: list[IPTimingResult]를 포함 | ✓ VERIFIED | simulation.py lines 69-70; ORM evidence.py lines 42-43; ETL evidence.py lines 34-35  |
| SC5 | Alembic migration이 생성되어 alembic upgrade head로 스키마 적용 가능                              | ✓ VERIFIED | 0002_schema_extensions.py; integration test_migration_downgrade_upgrade_cycle PASSED  |

**Score:** 5/5 ROADMAP Success Criteria 모두 VERIFIED

---

### Plan 05-01 Must-Haves (Pydantic 모델 레이어)

| #  | Truth                                                                                           | Status     | Evidence                                                              |
| -- | ----------------------------------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------- |
| P1 | IPSimParams \| PortSpec \| PortType 모델이 hw.py에 존재, IpCatalog.sim_params: IPSimParams \| None = None | ✓ VERIFIED | hw.py lines 84-121; import 성공 확인                                  |
| P2 | PortInputConfig \| IPPortConfig \| SimGlobalConfig \| SensorSpec이 usecase.py에 존재, Variant.sim_port_config/sim_config + Usecase.sensor 추가 | ✓ VERIFIED | usecase.py lines 155-262; 모든 클래스 정의 + 필드 확인               |
| P3 | PortBWResult \| IPTimingResult가 simulation.py에 존재, SimulationEvidence.dma_breakdown/timing_breakdown 추가 | ✓ VERIFIED | simulation.py lines 33-70; Literal["read","write"] 사용, PortType 미import |
| P4 | 기존 fixture(sim_params 없는 ip-isp-v12.yaml, breakdown 없는 sim 파일)가 ValidationError 없이 파싱 | ✓ VERIFIED | 16개 단위 테스트 PASSED (backward compat 테스트 포함)                 |
| P5 | 신규 fixture(ip-isp-v12-with-sim.yaml, sim-FHD30-with-breakdown.yaml)가 round-trip 직렬화 통과 | ✓ VERIFIED | test_ip_catalog_sim_params_roundtrip + test_sim_evidence_with_breakdown_roundtrip PASSED |

---

### Plan 05-02 Must-Haves (ORM + Migration 레이어)

| #  | Truth                                                                                             | Status     | Evidence                                                                    |
| -- | ------------------------------------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------- |
| O1 | IpCatalog ORM 모델에 sim_params = Column(JSONB) 컬럼이 존재                                      | ✓ VERIFIED | capability.py line 32: `sim_params = Column(JSONB)` 확인                    |
| O2 | Scenario ORM 모델에 sensor = Column(JSONB) 컬럼이 존재                                           | ✓ VERIFIED | definition.py line 30: `sensor = Column(JSONB)` 확인                       |
| O3 | ScenarioVariant ORM 모델에 sim_port_config + sim_config = Column(JSONB) 2개 존재                 | ✓ VERIFIED | definition.py lines 45-46: 두 컬럼 모두 확인                               |
| O4 | Evidence ORM 모델에 dma_breakdown + timing_breakdown = Column(JSONB) 2개 존재                    | ✓ VERIFIED | evidence.py lines 42-43: 두 컬럼 모두 확인; Computed 컬럼 미수정 확인      |
| O5 | alembic/versions/0002_schema_extensions.py 존재, upgrade() 6개 add_column + downgrade() 6개 drop_column | ✓ VERIFIED | add_column 6개, drop_column 6개 카운트 일치                                |
| O6 | 0002 migration이 0001을 down_revision으로 참조                                                    | ✓ VERIFIED | 0002_schema_extensions.py line 20: `down_revision = "0001"` 확인           |

---

### Plan 05-03 Must-Haves (ETL 매퍼 레이어)

| #  | Truth                                                                                                 | Status     | Evidence                                                                         |
| -- | ----------------------------------------------------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------- |
| E1 | upsert_ip()가 IpCatalog.sim_params를 ip_catalog.sim_params JSONB 컬럼에 직렬화                        | ✓ VERIFIED | capability.py line 37: `row.sim_params = obj.sim_params.model_dump(...)...`      |
| E2 | upsert_usecase()가 Usecase.sensor → Scenario.sensor, Variant.sim_port_config/sim_config → ScenarioVariant 직렬화 | ✓ VERIFIED | definition.py lines 35, 54-58: 3개 직렬화 라인 확인                            |
| E3 | upsert_simulation()이 SimulationEvidence.dma_breakdown/timing_breakdown → Evidence JSONB 직렬화       | ✓ VERIFIED | evidence.py lines 34-35: list comprehension 패턴 확인                           |
| E4 | alembic upgrade head가 오류 없이 실행되고 신규 컬럼 6개가 DB 스키마에 반영                           | ✓ VERIFIED | test_new_columns_exist_after_migration PASSED (Docker PostgreSQL)                |
| E5 | 365+ 테스트가 회귀 없이 통과 (357 unit + 8 integration schema extensions)                            | ✓ VERIFIED | unit: 357 PASSED; integration/test_schema_extensions.py: 8 PASSED               |

---

## Required Artifacts

| Artifact                                                    | 제공 기능                                        | 레벨 1: 존재 | 레벨 2: 내용 | 레벨 3: 연결 | 레벨 4: 데이터 흐름 | 최종 상태  |
| ----------------------------------------------------------- | ------------------------------------------------ | ------------ | ------------ | ------------ | ------------------- | ---------- |
| `src/scenario_db/models/capability/hw.py`                   | PortType/PortSpec/IPSimParams + IpCatalog.sim_params | ✓            | ✓            | ✓            | ✓                   | ✓ VERIFIED |
| `src/scenario_db/models/definition/usecase.py`              | PortInputConfig/IPPortConfig/SimGlobalConfig/SensorSpec + Variant/Usecase 필드 | ✓ | ✓ | ✓ | ✓ | ✓ VERIFIED |
| `src/scenario_db/models/evidence/simulation.py`             | PortBWResult/IPTimingResult + SimulationEvidence 필드 확장 | ✓         | ✓            | ✓            | ✓                   | ✓ VERIFIED |
| `src/scenario_db/db/models/capability.py`                   | IpCatalog.sim_params JSONB 컬럼                  | ✓            | ✓            | ✓            | ✓                   | ✓ VERIFIED |
| `src/scenario_db/db/models/definition.py`                   | Scenario.sensor + ScenarioVariant sim_port_config/sim_config JSONB | ✓ | ✓ | ✓ | ✓ | ✓ VERIFIED |
| `src/scenario_db/db/models/evidence.py`                     | Evidence dma_breakdown/timing_breakdown JSONB    | ✓            | ✓            | ✓            | ✓                   | ✓ VERIFIED |
| `alembic/versions/0002_schema_extensions.py`                | add_column 6개 + drop_column 6개 + down_revision="0001" | ✓       | ✓            | ✓            | N/A                 | ✓ VERIFIED |
| `src/scenario_db/etl/mappers/capability.py`                 | upsert_ip() sim_params 직렬화                    | ✓            | ✓            | ✓            | ✓                   | ✓ VERIFIED |
| `src/scenario_db/etl/mappers/definition.py`                 | upsert_usecase() sensor/sim_port_config/sim_config 직렬화 | ✓     | ✓            | ✓            | ✓                   | ✓ VERIFIED |
| `src/scenario_db/etl/mappers/evidence.py`                   | upsert_simulation() dma_breakdown/timing_breakdown 직렬화 | ✓     | ✓            | ✓            | ✓                   | ✓ VERIFIED |
| `tests/unit/test_schema_extensions.py`                      | 16개 단위 테스트 (round-trip + backward compat)  | ✓            | ✓            | N/A          | N/A                 | ✓ VERIFIED |
| `tests/unit/fixtures/hw/ip-isp-v12-with-sim.yaml`           | sim_params 포함 IpCatalog 테스트 fixture         | ✓            | ✓            | N/A          | N/A                 | ✓ VERIFIED |
| `tests/unit/fixtures/evidence/sim-FHD30-with-breakdown.yaml` | dma_breakdown/timing_breakdown 포함 fixture      | ✓            | ✓            | N/A          | N/A                 | ✓ VERIFIED |
| `tests/integration/test_schema_extensions.py`               | 8개 통합 테스트 (DB schema + ETL + migration cycle) | ✓         | ✓            | N/A          | N/A                 | ✓ VERIFIED |

---

## Key Link Verification

| From                            | To                                  | Via                                            | Status     | Evidence                                              |
| ------------------------------- | ----------------------------------- | ---------------------------------------------- | ---------- | ----------------------------------------------------- |
| IpCatalog.sim_params            | IPSimParams                         | 타입 어노테이션 `sim_params: IPSimParams \| None = None` | ✓ WIRED | hw.py line 121                                       |
| Variant.sim_port_config         | IPPortConfig                        | `dict[str, IPPortConfig] \| None = None`       | ✓ WIRED    | usecase.py line 202                                   |
| SimulationEvidence.dma_breakdown | PortBWResult                       | `list[PortBWResult] = Field(default_factory=list)` | ✓ WIRED | simulation.py line 69                                |
| upsert_ip() → ORM.sim_params    | ip_catalog.sim_params JSONB         | `row.sim_params = obj.sim_params.model_dump(...)` | ✓ WIRED | capability.py line 37                                |
| upsert_usecase() → ORM.sensor   | scenarios.sensor JSONB              | `row.sensor = obj.sensor.model_dump(...)`      | ✓ WIRED    | definition.py line 35                                 |
| upsert_usecase() → variant loop | scenario_variants.sim_port_config   | dict comprehension model_dump()                | ✓ WIRED    | definition.py lines 54-57                             |
| upsert_simulation() → Evidence  | evidence.dma_breakdown JSONB        | list comprehension model_dump()                | ✓ WIRED    | evidence.py lines 34-35                               |
| 0002_schema_extensions.py       | 0001_initial_schema.py              | `down_revision = "0001"`                       | ✓ WIRED    | migration file line 20                                |

---

## Data-Flow Trace (Level 4)

| Artifact                         | 데이터 변수         | 소스                                                | 실 데이터 생성 | 상태        |
| -------------------------------- | ------------------- | --------------------------------------------------- | -------------- | ----------- |
| ETL capability.py upsert_ip()    | row.sim_params      | obj.sim_params (Pydantic IpCatalog)                 | model_dump()   | ✓ FLOWING   |
| ETL definition.py upsert_usecase() | row.sensor        | obj.sensor (Pydantic Usecase)                       | model_dump()   | ✓ FLOWING   |
| ETL definition.py variant loop   | vrow.sim_port_config | v.sim_port_config (Pydantic Variant)               | dict comprehension model_dump() | ✓ FLOWING |
| ETL evidence.py upsert_simulation() | row.dma_breakdown | obj.dma_breakdown (Pydantic SimulationEvidence)     | list comprehension model_dump() | ✓ FLOWING |

---

## Behavioral Spot-Checks

| Behavior                                                        | Command                                                       | Result       | Status  |
| --------------------------------------------------------------- | ------------------------------------------------------------- | ------------ | ------- |
| 모든 신규 모델 import 성공 (순환 import 없음)                    | `uv run python -c "from ... import ..."`                      | ALL IMPORTS OK | ✓ PASS |
| ORM 컬럼 6개 Python 레벨 검증                                   | `assert 'sim_params' in OrmIp.__table__.columns.keys()`       | 모두 True    | ✓ PASS  |
| 단위 테스트 16개 PASSED                                         | `uv run pytest tests/unit/test_schema_extensions.py -q`       | 16 passed    | ✓ PASS  |
| 기존 단위 테스트 357개 회귀 없음                                 | `uv run pytest tests/unit/ -q`                                | 357 passed   | ✓ PASS  |
| Migration revision 체인 검증                                    | `importlib → m.revision="0002", m.down_revision="0001"`       | Migration OK | ✓ PASS  |
| 통합 테스트 8개 PASSED (DB schema + ETL + downgrade cycle)      | `uv run pytest tests/integration/test_schema_extensions.py -q` | 8 passed    | ✓ PASS  |

---

## Requirements Coverage

| REQ-ID | 소스 Plan           | 설명                                                          | 상태        | 증거                                            |
| ------ | ------------------- | ------------------------------------------------------------- | ----------- | ----------------------------------------------- |
| SCH-01 | 05-01, 05-02, 05-03 | IpCatalog.sim_params: IPSimParams \| None (Optional, backward compat) | ✓ SATISFIED | Pydantic hw.py line 121; ORM capability.py line 32; ETL capability.py line 37 |
| SCH-02 | 05-01, 05-02, 05-03 | Variant.sim_port_config: dict[str, IPPortConfig] \| None      | ✓ SATISFIED | Pydantic usecase.py line 202; ORM definition.py line 45; ETL definition.py lines 54-57 |
| SCH-03 | 05-01, 05-02, 05-03 | Variant.sim_config (REQUIREMENTS.md) / Usecase.sensor (PLAN 표기) — 실제 두 필드 모두 구현됨 | ✓ SATISFIED | 모든 레이어에서 두 필드 확인 |
| SCH-04 | 05-01, 05-02, 05-03 | Usecase.sensor (REQUIREMENTS.md) / SimulationEvidence 확장 (PLAN 표기) — 실제 두 기능 모두 구현됨 | ✓ SATISFIED | usecase.py line 262; simulation.py lines 69-70 |
| SCH-05 | 05-02, 05-03        | alembic upgrade head로 신규 컬럼 6개 적용 가능                | ✓ SATISFIED | 0002_schema_extensions.py; integration test PASSED |

**NOTE:** REQUIREMENTS.md 정의와 PLAN 번호 표기 간 경미한 불일치 발견:
- REQUIREMENTS.md: SCH-02=sim_port_config, SCH-03=sim_config, SCH-04=sensor, SCH-05=SimEvidence 확장
- PLAN 05-01/03: SCH-02=sim_port_config+sim_config, SCH-03=sensor, SCH-04=dma/timing, SCH-05=migration
- 결론: 번호 표기 불일치이며, 모든 기능은 실제로 구현되어 REQUIREMENTS.md의 5개 요구사항 전체를 충족한다. BLOCKER 아님.

---

## Anti-Patterns Found

| 파일 | 패턴 | 분류 | 영향 |
| ---- | ---- | ---- | ---- |
| (없음) | — | — | — |

- `vars()` / `__dict__` 금지 패턴: 3개 ETL 매퍼 모두 부재 확인
- 순환 import: simulation.py에서 hw.py import 없음 확인 (`direction: Literal["read","write"]` 사용)
- Computed 컬럼 미수정: evidence.py의 sw_version_hint/sweep_value_hint 변경 없음 확인

---

## Human Verification Required

없음 — 모든 must-have가 프로그래밍적으로 검증 가능하며, 통합 테스트가 DB 수준까지 커버한다.

---

## Gaps Summary

없음. 모든 17개 must-have가 VERIFIED 상태이다.

Phase 5의 3-Layer 연결 완성:
```
Pydantic 모델 (05-01) → ETL 매퍼 (05-03) → ORM 컬럼 (05-02) → DB JSONB
IpCatalog.sim_params   → row.sim_params    → ip_catalog.sim_params JSONB    ✓
Usecase.sensor         → row.sensor        → scenarios.sensor JSONB          ✓
Variant.sim_port_config → vrow.sim_port_config → scenario_variants.sim_port_config JSONB ✓
Variant.sim_config     → vrow.sim_config   → scenario_variants.sim_config JSONB ✓
SimEvidence.dma_breakdown → row.dma_breakdown → evidence.dma_breakdown JSONB ✓
SimEvidence.timing_breakdown → row.timing_breakdown → evidence.timing_breakdown JSONB ✓
```

---

_Verified: 2026-05-10_
_Verifier: Claude (gsd-verifier)_
