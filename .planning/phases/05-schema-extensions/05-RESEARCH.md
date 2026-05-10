# Phase 5: Schema Extensions — Research

**Researched:** 2026-05-10
**Domain:** Pydantic v2 모델 확장 / SQLAlchemy ORM JSONB / Alembic migration / ETL backward compat
**Confidence:** HIGH (전체 코드베이스 직접 검증, docs/simulation-engine-integration.md 설계 문서 참조)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCH-01 | `IpCatalog.sim_params: IPSimParams \| None` — Pydantic 모델 + ORM 컬럼, 기존 YAML backward compat | §Standard Stack / §IpCatalog 확장 패턴 |
| SCH-02 | `Variant.sim_port_config` + `Variant.sim_config` — Pydantic 모델 + ORM JSONB 컬럼 | §Variant 확장 패턴 / §ORM JSONB 추가 규칙 |
| SCH-03 | `Usecase.sensor: SensorSpec \| None` — OTF v_valid_time 입력값 저장 (Usecase 레벨) | §Usecase / Scenario ORM 분리 이슈 |
| SCH-04 | `SimulationEvidence.dma_breakdown + timing_breakdown` 확장 — list[PortBWResult] + list[IPTimingResult] | §Evidence ORM 확장 패턴 / §기존 Evidence 컬럼 구조 |
| SCH-05 | Alembic migration → `alembic upgrade head`로 기존 DB에 스키마 적용 | §Alembic migration 패턴 / §downgrade 작성 규칙 |
</phase_requirements>

---

## Summary

Phase 5는 sim/ 패키지(Phase 6)가 소비할 5가지 스키마 확장을 Pydantic + ORM + Alembic migration 3개 레이어에 동시 반영하는 작업이다. 설계 문서(`docs/simulation-engine-integration.md §7`)에 모든 신규 모델 정의가 이미 확정되어 있으므로 "무엇을 만들지"가 아니라 "어떤 순서로, 어떤 파일을 어떻게 수정하는지"가 핵심이다.

기존 코드베이스 분석 결과: ORM 레이어(`db/models/`)는 이미 JSONB 컬럼을 폭넓게 사용 중이다. `ip_catalog` 테이블에 `sim_params JSONB` 컬럼 1개, `scenario_variants` 테이블에 `sim_port_config JSONB` + `sim_config JSONB` 컬럼 2개, `scenarios` 테이블에 `sensor JSONB` 컬럼 1개, `evidence` 테이블에 `dma_breakdown JSONB` + `timing_breakdown JSONB` 컬럼 2개를 추가하면 된다. 총 7개 신규 컬럼, 모두 nullable=True(기존 데이터 파괴 없음).

중요 발견: `Usecase.sensor` (Pydantic 모델 레벨)와 ORM `Scenario.sensor` 컬럼은 구조적으로 분리되어 있다. `upsert_usecase()` 매퍼가 `Usecase` 모델을 파싱해 `Scenario` ORM 행에 기록하는 구조이므로, Pydantic 모델(`models/definition/usecase.py`)과 ORM 모델(`db/models/definition.py`)을 독립적으로 수정하고 ETL 매퍼(`etl/mappers/definition.py`)에서 연결해야 한다.

**Primary recommendation:** 설계 문서 §7의 모델 정의를 그대로 구현한다. 신규 필드는 모두 `Optional(None default)`로 선언하여 기존 YAML fixture가 수정 없이 ETL을 통과하게 한다. Alembic migration은 `op.add_column()` 단위로 작성하고, 기존 테이블의 구조 변경이 없으므로 downgrade는 `op.drop_column()`이면 충분하다.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| IPSimParams / SensorSpec / PortBWResult / IPTimingResult 모델 정의 | Pydantic 모델 레이어 (`src/scenario_db/models/`) | — | 스키마 단일 진실 원천 |
| JSONB 컬럼 추가 (ip_catalog, scenario_variants, scenarios, evidence) | ORM 레이어 (`db/models/`) | Alembic migration | ORM이 shape 선언, migration이 DDL 실행 |
| ETL 매퍼에서 신규 필드 직렬화 | ETL 레이어 (`etl/mappers/`) | — | Pydantic → ORM 변환의 단일 경로 |
| Alembic migration 파일 | `alembic/versions/` | `alembic/env.py` | DDL 변경의 단일 경로, 롤백 지원 |
| YAML backward compat | ETL + Pydantic `Optional` 선언 | — | 기존 fixture 수정 없이 로드 보장 |

---

## Standard Stack

### Core (기존 사용 중 — 변경 없음)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic v2 | 현재 프로젝트 사용 버전 | Pydantic 모델 정의 + validation | `BaseScenarioModel(extra='forbid')` 기반 이미 확립 |
| sqlalchemy | 현재 프로젝트 사용 버전 | ORM 모델 + JSONB 컬럼 | `JSONB` 타입 이미 `ip_breakdown`, `artifacts` 등에 사용 중 |
| alembic | 현재 프로젝트 사용 버전 | DB migration | `0001_initial_schema.py` 패턴 확립, `env.py` 설정 완료 |
| psycopg2 | 현재 프로젝트 사용 버전 | PostgreSQL 드라이버 | 기존 테스트 컨테이너에서 사용 |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| testcontainers (postgres) | 현재 프로젝트 사용 버전 | 통합 테스트용 PostgreSQL 컨테이너 | migration 통합 테스트에서 `alembic upgrade head` 실행 검증 |
| pytest | 현재 프로젝트 사용 버전 | 테스트 프레임워크 | 단위/통합 테스트 모두 |

**설치:** 신규 의존성 없음 — 기존 스택만 사용.

---

## Architecture Patterns

### System Architecture Diagram

```
YAML fixture (기존)
    │
    ▼
ETL loader (load_yaml_dir)
    │
    ├── upsert_ip()      ──► PydanticIpCatalog.model_validate()
    │       │                [sim_params: IPSimParams | None 신규 파싱]
    │       ▼
    │   ORM IpCatalog row
    │       └── sim_params = JSONB  ◄── [신규 컬럼]
    │
    ├── upsert_usecase() ──► PydanticUsecase.model_validate()
    │       │                [sensor: SensorSpec | None 신규 파싱]
    │       ▼
    │   ORM Scenario row
    │       └── sensor = JSONB       ◄── [신규 컬럼]
    │       │
    │   ORM ScenarioVariant rows
    │       ├── sim_port_config = JSONB ◄── [신규 컬럼]
    │       └── sim_config = JSONB      ◄── [신규 컬럼]
    │
    └── upsert_simulation()──► PydanticSimulationEvidence.model_validate()
            │                [dma_breakdown / timing_breakdown 신규 파싱]
            ▼
        ORM Evidence row
            ├── dma_breakdown = JSONB   ◄── [신규 컬럼]
            └── timing_breakdown = JSONB◄── [신규 컬럼]

Alembic migration 0002
    └── op.add_column() × 6 → alembic upgrade head
```

### Recommended Project Structure (변경되는 파일만 표시)

```
src/scenario_db/
├── models/
│   ├── capability/
│   │   └── hw.py          # IpCatalog에 sim_params 추가, IPSimParams/PortSpec 신규 정의
│   └── definition/
│       └── usecase.py     # Variant에 sim_port_config/sim_config 추가
│                          # Usecase에 sensor 추가
│                          # PortInputConfig/IPPortConfig/SimGlobalConfig/SensorSpec 신규 정의
├── models/evidence/
│   └── simulation.py      # SimulationEvidence에 dma_breakdown/timing_breakdown 추가
│                          # PortBWResult/IPTimingResult 신규 정의
├── db/models/
│   ├── capability.py      # IpCatalog ORM에 sim_params JSONB 컬럼 추가
│   ├── definition.py      # Scenario ORM에 sensor JSONB,
│   │                      # ScenarioVariant ORM에 sim_port_config/sim_config JSONB 추가
│   └── evidence.py        # Evidence ORM에 dma_breakdown/timing_breakdown JSONB 추가
├── etl/mappers/
│   ├── capability.py      # upsert_ip(): sim_params 직렬화 추가
│   ├── definition.py      # upsert_usecase(): sensor, sim_port_config, sim_config 직렬화 추가
│   └── evidence.py        # upsert_simulation(): dma_breakdown, timing_breakdown 직렬화 추가
alembic/versions/
└── 0002_schema_extensions.py  # 신규 migration 파일
```

---

## 현재 ORM 구조 — 수정 대상 파일 완전 목록

### Pattern 1: IpCatalog 확장 (SCH-01)

**현재 Pydantic 모델** (`models/capability/hw.py`):
```python
# [VERIFIED: 직접 파일 읽기]
class IpCatalog(BaseScenarioModel):
    id: DocumentId
    schema_version: SchemaVersion
    kind: Literal["ip"]
    category: str
    hierarchy: IpHierarchy
    capabilities: IpCapabilities
    rtl_version: str | None = None
    compatible_soc: list[DocumentId] = Field(default_factory=list)
    # sim_params 없음 — 신규 추가 필요
```

**추가할 Pydantic 모델** (설계 문서 §7.1 기반):
```python
# Source: docs/simulation-engine-integration.md §7.1
class PortType(StrEnum):
    DMA_READ  = "DMA_READ"
    DMA_WRITE = "DMA_WRITE"
    OTF_IN    = "OTF_IN"
    OTF_OUT   = "OTF_OUT"

class PortSpec(BaseScenarioModel):
    name: str
    type: PortType
    max_bw_gbps: float | None = None

class IPSimParams(BaseScenarioModel):
    hw_name_in_sim: str       # SimEngine hw.yaml의 'name' 필드와 일치
    ppc: float                # Pixels Per Clock
    unit_power_mw_mp: float   # mW/MP@30fps
    idc: float = 0.0
    vdd: str                  # "VDD_CAM", "VDD_INT" 등
    dvfs_group: str           # DVFS 테이블 이름
    latency_us: float = 0.0
    ports: list[PortSpec] = Field(default_factory=list)

class IpCatalog(BaseScenarioModel):
    ...
    sim_params: IPSimParams | None = None  # NEW
```

**현재 ORM 모델** (`db/models/capability.py`):
```python
# [VERIFIED: 직접 파일 읽기]
class IpCatalog(Base):
    __tablename__ = "ip_catalog"
    id             = Column(Text, primary_key=True)
    schema_version = Column(Text, nullable=False)
    category       = Column(Text)
    hierarchy      = Column(JSONB)
    capabilities   = Column(JSONB)
    rtl_version    = Column(Text)
    compatible_soc = Column(JSONB)
    yaml_sha256    = Column(Text, nullable=False)
    # sim_params 컬럼 없음 — 신규 추가 필요
```

**추가할 ORM 컬럼:**
```python
sim_params = Column(JSONB)   # nullable (기존 데이터 호환)
```

**ETL 매퍼 수정** (`etl/mappers/capability.py`, `upsert_ip()`):
```python
# [VERIFIED: 직접 파일 읽기] 기존 패턴에 맞춰
row.sim_params = obj.sim_params.model_dump(exclude_none=True) if obj.sim_params else None
```

---

### Pattern 2: Variant 확장 (SCH-02)

**현재 Pydantic 모델** (`models/definition/usecase.py`):
```python
# [VERIFIED: 직접 파일 읽기]
class Variant(BaseScenarioModel):
    id: str
    severity: Severity
    design_conditions: dict[str, str | int | float] = Field(default_factory=dict)
    size_overrides: dict[str, str] = Field(default_factory=dict)
    ip_requirements: dict[str, IpRequirementSpec] = Field(default_factory=dict)
    sw_requirements: SwRequirements | None = None
    violation_policy: ViolationPolicy | None = None
    tags: list[str] = Field(default_factory=list)
    derived_from_variant: str | None = None
    design_conditions_override: dict[str, str | int | float] | None = None
    # sim_port_config, sim_config 없음 — 신규 추가 필요
```

**추가할 Pydantic 모델** (설계 문서 §7.2):
```python
# Source: docs/simulation-engine-integration.md §7.2
class PortInputConfig(BaseScenarioModel):
    port: str
    format: str
    bitwidth: int = 8
    width: int
    height: int
    compression: Literal["SBWC", "AFBC", "disable"] = "disable"
    comp_ratio: float = 1.0
    comp_ratio_min: float | None = None
    comp_ratio_max: float | None = None
    llc_enabled: bool = False
    llc_weight: float = 1.0
    r_w_rate: float = 1.0

class IPPortConfig(BaseScenarioModel):
    mode: str = "Normal"
    sw_margin_override: float | None = None
    inputs: list[PortInputConfig] = Field(default_factory=list)
    outputs: list[PortInputConfig] = Field(default_factory=list)

class SimGlobalConfig(BaseScenarioModel):
    asv_group: int = 4
    sw_margin: float = 0.25
    bw_power_coeff: float = 80.0
    vbat: float = 4.0
    pmic_eff: float = 0.85
    h_blank_margin: float = 0.05
    dvfs_overrides: dict[str, int] = Field(default_factory=dict)

class Variant(BaseScenarioModel):
    ...
    sim_port_config: dict[str, IPPortConfig] | None = None  # NEW
    sim_config: SimGlobalConfig | None = None               # NEW
```

**현재 ORM 모델** (`db/models/definition.py`):
```python
# [VERIFIED: 직접 파일 읽기]
class ScenarioVariant(Base):
    __tablename__ = "scenario_variants"
    scenario_id          = Column(Text, ForeignKey("scenarios.id"), primary_key=True)
    id                   = Column(Text, primary_key=True)
    severity             = Column(Text)
    design_conditions    = Column(JSONB)
    ip_requirements      = Column(JSONB)
    sw_requirements      = Column(JSONB)
    violation_policy     = Column(JSONB)
    tags                 = Column(JSONB)
    derived_from_variant = Column(Text)
    # sim_port_config, sim_config 없음 — 신규 추가 필요
```

**추가할 ORM 컬럼 2개:**
```python
sim_port_config = Column(JSONB)   # nullable
sim_config      = Column(JSONB)   # nullable
```

**ETL 매퍼 수정** (`etl/mappers/definition.py`, `upsert_usecase()` 내 variant loop):
```python
# [VERIFIED: 직접 파일 읽기] 기존 패턴 확인
vrow.sim_port_config = (
    {k: v.model_dump(exclude_none=True) for k, v in v.sim_port_config.items()}
    if v.sim_port_config else None
)
vrow.sim_config = v.sim_config.model_dump(exclude_none=True) if v.sim_config else None
```

---

### Pattern 3: Usecase.sensor 확장 (SCH-03)

**중요 이슈 — Pydantic Usecase ≠ ORM Scenario:**

Pydantic 레이어에서 `Usecase`는 `models/definition/usecase.py`에 정의되어 있고,
ORM 레이어에서는 `Scenario` 테이블(`db/models/definition.py`)로 매핑된다.
`upsert_usecase()` 매퍼가 `PydanticUsecase → ORM Scenario` 변환을 담당한다.

**현재 Pydantic Usecase:**
```python
# [VERIFIED: 직접 파일 읽기]
class Usecase(BaseScenarioModel):
    ...
    # sensor 없음 — 신규 추가 필요
```

**추가할 Pydantic 모델** (설계 문서 §7.2):
```python
# Source: docs/simulation-engine-integration.md §7.2
class SensorSpec(BaseScenarioModel):
    """OTF 그룹 타이밍 제약 기준 — v_valid_time 기반 처리량."""
    ip_ref: DocumentId
    frame_width: int
    frame_height: int
    fps: float
    v_valid_ratio: float = 0.85   # v_active / v_total

class Usecase(BaseScenarioModel):
    ...
    sensor: SensorSpec | None = None   # NEW
```

**현재 ORM Scenario:**
```python
# [VERIFIED: 직접 파일 읽기]
class Scenario(Base):
    __tablename__ = "scenarios"
    id             = Column(Text, primary_key=True)
    schema_version = Column(Text, nullable=False)
    project_ref    = Column(Text, ForeignKey("projects.id"), nullable=False)
    metadata_      = Column("metadata", JSONB, nullable=False)
    pipeline       = Column(JSONB, nullable=False)
    size_profile   = Column(JSONB)
    design_axes    = Column(JSONB)
    yaml_sha256    = Column(Text, nullable=False)
    # sensor 없음 — 신규 추가 필요
```

**추가할 ORM 컬럼:**
```python
sensor = Column(JSONB)   # nullable
```

**ETL 매퍼 수정** (`etl/mappers/definition.py`, `upsert_usecase()`):
```python
row.sensor = obj.sensor.model_dump(exclude_none=True) if obj.sensor else None
```

---

### Pattern 4: SimulationEvidence 확장 (SCH-04)

**현재 Pydantic SimulationEvidence:**
```python
# [VERIFIED: 직접 파일 읽기]
class SimulationEvidence(BaseScenarioModel):
    id: DocumentId
    schema_version: SchemaVersion
    kind: Literal["evidence.simulation"]
    scenario_ref: DocumentId
    variant_ref: str
    project_ref: DocumentId | None = None
    execution_context: ExecutionContext
    sweep_context: SweepContext | None = None
    resolution_result: ResolutionResult | None = None
    run: RunInfo
    aggregation: Aggregation
    kpi: dict[str, float | int] = Field(default_factory=dict)
    ip_breakdown: list[IpBreakdown] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    # dma_breakdown, timing_breakdown 없음 — 신규 추가 필요
```

**추가할 Pydantic 모델** (설계 문서 §7.4):
```python
# Source: docs/simulation-engine-integration.md §7.4
class PortBWResult(BaseScenarioModel):
    ip: str
    port: str
    direction: Literal["read", "write"]
    bw_mbs: float
    bw_mbs_worst: float | None = None
    bw_power_mw: float
    format: str | None = None
    compression: str | None = None
    llc_enabled: bool = False

class IPTimingResult(BaseScenarioModel):
    ip: str
    hw_time_ms: float
    required_clock_mhz: float
    set_clock_mhz: float
    set_voltage_mv: float
    feasible: bool

class SimulationEvidence(BaseScenarioModel):
    ...  # 기존 필드 유지
    dma_breakdown: list[PortBWResult] = Field(default_factory=list)      # NEW
    timing_breakdown: list[IPTimingResult] = Field(default_factory=list)  # NEW
```

**현재 ORM Evidence:**
```python
# [VERIFIED: 직접 파일 읽기]
class Evidence(Base):
    __tablename__ = "evidence"
    ...
    run_info     = Column(JSONB)   # sim only (기존)
    ip_breakdown = Column(JSONB)   # sim only (기존)
    provenance   = Column(JSONB)   # meas only (기존)
    artifacts    = Column(JSONB)   # (기존)
    # dma_breakdown, timing_breakdown 없음 — 신규 추가 필요
```

**추가할 ORM 컬럼 2개:**
```python
dma_breakdown    = Column(JSONB)   # sim only, nullable
timing_breakdown = Column(JSONB)   # sim only, nullable
```

**ETL 매퍼 수정** (`etl/mappers/evidence.py`, `upsert_simulation()`):
```python
row.dma_breakdown    = [b.model_dump(exclude_none=True) for b in obj.dma_breakdown]
row.timing_breakdown = [t.model_dump(exclude_none=True) for t in obj.timing_breakdown]
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSONB 컬럼 추가 DDL | 수동 SQL `ALTER TABLE` | `op.add_column(JSONB)` in Alembic | migration history 추적, rollback 지원 |
| Optional 필드 default | `if field: ...` 런타임 체크 | `Field(default_factory=list)` / `= None` Pydantic 선언 | extra='forbid' 환경에서 validation 오류 방지 |
| Pydantic → dict 직렬화 | `vars(obj)` / `obj.__dict__` | `obj.model_dump(exclude_none=True)` | `_sa_instance_state` extra='forbid' 위반 회피 (Phase 1 교훈) |
| 기존 테이블 컬럼 수정 | `op.alter_column()` | 신규 `op.add_column()` | nullable 추가가 non-destructive, lock-safe |

**Key insight:** 기존 YAML fixture는 신규 Optional 필드가 없어도 `model_validate()` 통과해야 한다. `BaseScenarioModel(extra='forbid')`이므로 **신규 필드는 반드시 `= None` 또는 `default_factory` 기본값을 가져야 한다.**

---

## Common Pitfalls

### Pitfall 1: extra='forbid' + 신규 필드 기본값 누락

**What goes wrong:** `BaseScenarioModel`은 `extra='forbid'`이다. 신규 Pydantic 필드에 기본값 없이 `required`로 선언하면 기존 YAML fixture(`sim_params` 없는 ip-*.yaml)가 `ValidationError`를 낸다.

**Why it happens:** Pydantic v2에서 기본값 없는 필드는 필수(required). YAML에 해당 키가 없으면 파싱 실패.

**How to avoid:** 모든 신규 필드는 `= None` (Optional) 또는 `Field(default_factory=list)` 기본값 필수. 기존 fixture YAML round-trip 테스트를 통과해야 backward compat 확인 완료.

**Warning signs:** `ValidationError: field required` 오류 메시지에 신규 필드 이름이 있으면 기본값 누락.

---

### Pitfall 2: ORM 수정 후 Alembic autogenerate 사용

**What goes wrong:** `alembic revision --autogenerate`가 ORM 모델과 DB 스키마 차이를 감지하지만, Computed 컬럼(`sw_version_hint`, `sweep_value_hint`)을 잘못 감지해 불필요한 `alter_column`을 생성하는 경우가 있다.

**Why it happens:** SQLAlchemy의 `Computed` 컬럼 비교 로직과 Alembic autogenerate 간 미세한 불일치.

**How to avoid:** autogenerate 결과를 항상 검토하고 `# noqa: autogenerated` 태그가 있어도 내용을 확인. 이번 Phase 5는 모든 변경이 `op.add_column()` 단순 추가이므로, autogenerate 대신 **수동 migration 파일 작성**이 더 안전하다.

**Warning signs:** 생성된 migration에 `op.alter_column("evidence", "sw_version_hint", ...)` 같은 Computed 컬럼 수정이 있으면 제거.

---

### Pitfall 3: ETL 매퍼에서 신규 필드 직렬화 누락

**What goes wrong:** Pydantic 모델과 ORM 컬럼을 모두 추가했지만, ETL 매퍼(`upsert_*()`)에서 `row.sim_params = ...` 라인을 빠뜨리면 DB에 `NULL`만 저장됨. 오류는 없고 데이터만 유실.

**Why it happens:** ETL 매퍼는 Pydantic 모델과 ORM 컬럼을 명시적으로 매핑하는 코드이므로, 둘 중 하나만 수정하면 반영되지 않는다.

**How to avoid:** 수정 대상 파일 체크리스트: (1) Pydantic 모델 → (2) ORM 모델 → (3) ETL 매퍼 → (4) Alembic migration. 4개 모두 수정 완료 여부 확인.

---

### Pitfall 4: Alembic migration의 downgrade 누락 또는 순서 역전

**What goes wrong:** `downgrade()`에서 컬럼 삭제 순서가 FK 의존성을 위반하거나, 추가한 컬럼을 누락함.

**Why it happens:** Phase 5에서 추가하는 컬럼은 모두 같은 테이블에 독립적이므로 FK 이슈는 없지만, 컬럼 수를 놓치기 쉽다.

**How to avoid:** migration 파일에서 `upgrade()`에 추가한 컬럼 수와 `downgrade()`에서 삭제하는 컬럼 수가 일치하는지 확인. 테이블별로 정리:
- `ip_catalog`: +1 (`sim_params`)
- `scenarios`: +1 (`sensor`)
- `scenario_variants`: +2 (`sim_port_config`, `sim_config`)
- `evidence`: +2 (`dma_breakdown`, `timing_breakdown`)
- 합계: **6개 컬럼 추가, downgrade에서 6개 삭제**

---

### Pitfall 5: Usecase.sensor vs Scenario.sensor 레이어 혼동

**What goes wrong:** `SensorSpec`이 `Usecase` 레벨에 정의되지만(Pydantic), ORM에는 `Scenario` 테이블 컬럼으로 저장된다. `uc-camera-recording.yaml`의 최상위 `sensor:` 키가 YAML → Pydantic Usecase → ORM Scenario 경로를 거쳐야 한다.

**Why it happens:** Pydantic 모델 이름(`Usecase`)과 ORM 테이블 이름(`scenarios`)이 다르고, ETL 매퍼가 그 변환을 담당함.

**How to avoid:** ETL `upsert_usecase()` 함수 내에서 `row.sensor = ...` 라인이 `Scenario` ORM 행에 기록되는 것을 확인. 별도 테이블이나 nested 구조가 필요하지 않음.

---

### Pitfall 6: `PortType` enum을 hw.py에 정의할 경우 순환 import

**What goes wrong:** `IPSimParams`가 `hw.py`에 있고, `PortBWResult`가 `evidence/simulation.py`에 있다. 둘 다 `PortType` enum을 참조하면 `hw.py`가 `evidence/simulation.py`를 import하는 순환이 발생할 수 있다.

**How to avoid:** `PortType` enum은 **`models/common.py`** 또는 `models/capability/hw.py`에만 정의하고, `evidence/simulation.py`의 `PortBWResult`에서는 `direction: Literal["read", "write"]` 같은 단순 Literal을 사용한다(설계 문서 §7.4 확인 — `PortBWResult`는 `PortType`을 import하지 않음).

---

## Code Examples

### Alembic migration 파일 구조 (0002_schema_extensions.py)

```python
# Source: docs/simulation-engine-integration.md §7 + alembic/versions/0001_initial_schema.py 패턴 [VERIFIED]
"""schema extensions for sim/ package

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-10
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IpCatalog — sim_params (SCH-01)
    op.add_column("ip_catalog",
        sa.Column("sim_params", JSONB, nullable=True))

    # Scenario — sensor (SCH-03)
    op.add_column("scenarios",
        sa.Column("sensor", JSONB, nullable=True))

    # ScenarioVariant — sim_port_config, sim_config (SCH-02)
    op.add_column("scenario_variants",
        sa.Column("sim_port_config", JSONB, nullable=True))
    op.add_column("scenario_variants",
        sa.Column("sim_config", JSONB, nullable=True))

    # Evidence — dma_breakdown, timing_breakdown (SCH-04)
    op.add_column("evidence",
        sa.Column("dma_breakdown", JSONB, nullable=True))
    op.add_column("evidence",
        sa.Column("timing_breakdown", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("evidence", "timing_breakdown")
    op.drop_column("evidence", "dma_breakdown")
    op.drop_column("scenario_variants", "sim_config")
    op.drop_column("scenario_variants", "sim_port_config")
    op.drop_column("scenarios", "sensor")
    op.drop_column("ip_catalog", "sim_params")
```

### YAML fixture 예시 — sim_params 추가 (ip-isp-v12.yaml 확장)

```yaml
# Source: docs/simulation-engine-integration.md §7.1 [CITED]
# 기존 필드 변경 없음 — sim_params 섹션만 추가
id: ip-isp-v12
schema_version: "2.2"
kind: ip
# ... 기존 내용 그대로 ...

sim_params:                        # NEW — 없어도 ETL 통과 (Optional)
  hw_name_in_sim: "ISP"
  ppc: 4
  unit_power_mw_mp: 10.5
  idc: 0.5
  vdd: "VDD_INTCAM"
  dvfs_group: "CAM"
  ports:
    - { name: "RDMA_FE", type: "DMA_READ",  max_bw_gbps: 25.6 }
    - { name: "WDMA_BE", type: "DMA_WRITE", max_bw_gbps: 12.8 }
    - { name: "CINFIFO", type: "OTF_IN" }
    - { name: "COUTFIFO",type: "OTF_OUT" }
```

### YAML fixture 예시 — sim_port_config + sim_config + sensor

```yaml
# Source: docs/simulation-engine-integration.md §7.2 [CITED]
# uc-camera-recording.yaml 의 variants 섹션 예시
variants:
  - id: FHD30-SDR-H265
    severity: light
    # ... 기존 필드 ...
    sim_port_config:               # NEW — 없어도 ETL 통과 (Optional)
      isp0:
        mode: "Normal"
        inputs:
          - port: "RDMA_FE"
            format: "BAYER"
            bitwidth: 12
            width: 4000
            height: 2252
        outputs:
          - port: "WDMA_BE"
            format: "NV12"
            bitwidth: 8
            width: 1920
            height: 1080
    sim_config:                    # NEW — 없어도 ETL 통과 (Optional)
      asv_group: 4
      sw_margin: 0.25

# usecase 최상위 sensor 섹션 예시
sensor:                            # NEW — 없어도 ETL 통과 (Optional)
  ip_ref: ip-csis-v8
  frame_width: 4000
  frame_height: 3000
  fps: 60.0
  v_valid_ratio: 0.85
```

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | `pyproject.toml` (pytest 설정) |
| Quick run command | `uv run pytest tests/unit/ -q` |
| Full suite command | `uv run pytest -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCH-01 | IPSimParams Pydantic round-trip | unit | `uv run pytest tests/unit/test_capability_models.py -k sim_params -x` | ❌ Wave 0 신규 |
| SCH-01 | 기존 ip-*.yaml fixture가 sim_params 없이 ETL 통과 | unit | `uv run pytest tests/unit/test_capability_models.py -k backward_compat -x` | ❌ Wave 0 신규 |
| SCH-02 | Variant sim_port_config/sim_config Pydantic round-trip | unit | `uv run pytest tests/unit/test_definition_models.py -k sim_port_config -x` | ❌ Wave 0 신규 |
| SCH-03 | SensorSpec Pydantic round-trip | unit | `uv run pytest tests/unit/test_definition_models.py -k sensor_spec -x` | ❌ Wave 0 신규 |
| SCH-04 | PortBWResult/IPTimingResult Pydantic round-trip | unit | `uv run pytest tests/unit/test_evidence_models.py -k dma_breakdown -x` | ❌ Wave 0 신규 |
| SCH-04 | SimulationEvidence 기존 fixture backward compat | unit | `uv run pytest tests/unit/test_evidence_models.py::test_sim_evidence_roundtrip -x` | ✅ 기존 통과 확인 필요 |
| SCH-05 | Alembic migration 0002 upgrade/downgrade 성공 | integration | `uv run pytest tests/integration/ -k migration -x` | ❌ Wave 0 신규 |
| SCH-05 | ETL full load 후 신규 컬럼에 데이터 반영 확인 | integration | `uv run pytest tests/integration/test_schema_extensions.py -x` | ❌ Wave 0 신규 |
| SCH-01~04 | 기존 209 테스트 회귀 없음 | integration | `uv run pytest -q --tb=short` | ✅ 기존 — 통과 확인 필요 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/unit/ -q` (단위 테스트, Docker 불필요)
- **Per wave merge:** `uv run pytest -q` (전체 스위트, Docker 필요)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/unit/test_capability_models.py` — `IPSimParams` round-trip + backward compat 테스트 추가 (기존 파일에 함수 추가)
- [ ] `tests/unit/test_definition_models.py` — `SensorSpec`, `PortInputConfig`, `IPPortConfig`, `SimGlobalConfig`, `Variant.sim_port_config` 테스트 추가
- [ ] `tests/unit/test_evidence_models.py` — `PortBWResult`, `IPTimingResult`, `SimulationEvidence.dma_breakdown` 테스트 추가
- [ ] `tests/integration/test_schema_extensions.py` — 신규 파일: Alembic migration 0002 upgrade/downgrade + ETL full load + DB 컬럼 확인
- [ ] `tests/unit/fixtures/evidence/sim-*.yaml` — `dma_breakdown`/`timing_breakdown` 있는 버전 + 없는 버전 fixture 2종

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `ip_breakdown`에 BW/타이밍 통합 저장 | `dma_breakdown` + `timing_breakdown` 분리 | Phase 5 | 타입 안전성 + Phase 7 분석 API 필터링 용이 |
| DVFS 파라미터 CSV | `dvfs-projectA.yaml` YAML화 | Phase 6에서 구현 | 버전 관리 가능, ETL 가능 |
| 수동 KPI 입력 | sim/ 패키지 자동 계산 → SimulationEvidence 적재 | Phase 6~7 | Phase 5는 컬럼만 추가, 데이터는 Phase 7에서 채워짐 |

**Deprecated/outdated:**
- `artifacts` 필드에 BW JSON inline_data 임시 저장 전략 (설계 문서 §12.15 언급): Phase 5에서 `dma_breakdown`/`timing_breakdown` 전용 컬럼이 생기므로 이 임시 전략은 사용하지 않는다.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `SensorSpec`은 `Usecase` YAML의 최상위 키 `sensor:`에 위치한다 (Variant 레벨이 아님) | Pattern 3 | sensor가 Variant 레벨이면 ORM 매핑 위치가 ScenarioVariant 테이블로 변경 |
| A2 | `PortBWResult.direction`은 `Literal["read","write"]`이고 `PortType` enum을 재사용하지 않는다 | Pattern 4 | PortType 재사용 시 import 경로 재설계 필요 |

---

## Open Questions (RESOLVED)

1. **SensorSpec의 YAML 위치 확정 필요**
   - What we know: 설계 문서 §7.2에서 `Usecase.sensor: SensorSpec | None`으로 Usecase 최상위 레벨
   - What's unclear: Variant마다 다른 센서를 사용하는 경우 (멀티 카메라) — Phase 5 범위 밖인지?
   - RESOLVED: Phase 5에서는 Usecase 레벨 단일 센서로 구현. 멀티 카메라는 Phase 6 어댑터가 처리하도록 위임. Plan 05-01 Task 2에 반영됨.

2. **기존 sim-*.yaml fixture 업데이트 여부**
   - What we know: 기존 `demo/fixtures/03_evidence/sim-UHD60-A0-sw123.yaml`에는 `dma_breakdown`/`timing_breakdown` 없음
   - What's unclear: Phase 5 테스트에서 이 fixture를 유지하거나 새 확장 fixture를 추가?
   - RESOLVED: 기존 fixture는 **수정하지 않고** backward compat 테스트에 사용. 신규 필드가 있는 `sim-FHD30-with-breakdown.yaml` fixture를 별도 추가. Plan 05-01 Task 4 + 05-03 Task 2에 반영됨.

---

## Environment Availability

Step 2.6: SKIPPED (Phase 5는 순수 코드/스키마 변경 — 신규 외부 의존성 없음)

기존 testcontainers + PostgreSQL 환경이 Alembic migration 통합 테스트에 그대로 사용된다.

---

## Security Domain

`security_enforcement` 설정 불명확 — 해당 Phase는 내부 스키마 확장이며 API 엔드포인트 신규 추가 없음. 기존 보안 경계 변경 없음.

---

## Sources

### Primary (HIGH confidence)

- `src/scenario_db/models/capability/hw.py` — 직접 읽기: IpCatalog Pydantic 구조 확인 [VERIFIED]
- `src/scenario_db/models/definition/usecase.py` — 직접 읽기: Usecase/Variant Pydantic 구조 확인 [VERIFIED]
- `src/scenario_db/models/evidence/simulation.py` — 직접 읽기: SimulationEvidence Pydantic 구조 확인 [VERIFIED]
- `src/scenario_db/db/models/capability.py` — 직접 읽기: IpCatalog ORM 구조 확인 [VERIFIED]
- `src/scenario_db/db/models/definition.py` — 직접 읽기: Scenario/ScenarioVariant ORM 구조 확인 [VERIFIED]
- `src/scenario_db/db/models/evidence.py` — 직접 읽기: Evidence ORM 구조 확인 [VERIFIED]
- `alembic/versions/0001_initial_schema.py` — 직접 읽기: 기존 migration 패턴 확인 [VERIFIED]
- `src/scenario_db/etl/mappers/capability.py` — 직접 읽기: ETL 직렬화 패턴 확인 [VERIFIED]
- `src/scenario_db/etl/mappers/definition.py` — 직접 읽기: upsert_usecase() 패턴 확인 [VERIFIED]
- `src/scenario_db/etl/mappers/evidence.py` — 직접 읽기: upsert_simulation() 패턴 확인 [VERIFIED]
- `docs/simulation-engine-integration.md §7` — 설계 문서 직접 읽기: 모든 신규 모델 정의 [CITED]

### Secondary (MEDIUM confidence)

- `tests/integration/conftest.py` — 직접 읽기: Alembic migration 통합 테스트 패턴 확인 [VERIFIED]
- `tests/unit/test_evidence_models.py` — 직접 읽기: 기존 단위 테스트 패턴 확인 [VERIFIED]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 기존 코드베이스에서 직접 확인된 패턴
- Architecture: HIGH — 설계 문서 §7과 기존 코드 구조 교차 검증 완료
- Pitfalls: HIGH — Phase 1~4 누적 교훈 + extra='forbid' 패턴 직접 검증
- Migration 패턴: HIGH — `0001_initial_schema.py` 직접 읽기로 패턴 확인

**Research date:** 2026-05-10
**Valid until:** 2026-06-10 (안정적 스택, 변경 가능성 낮음)
