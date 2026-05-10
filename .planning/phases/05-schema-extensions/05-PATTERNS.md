# Phase 5: Schema Extensions — Pattern Map

**Mapped:** 2026-05-10
**Files analyzed:** 11 (8 modified + 3 new)
**Analogs found:** 11 / 11

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/scenario_db/models/capability/hw.py` | model | transform | `src/scenario_db/models/evidence/simulation.py` | role-match (같은 BaseScenarioModel 확장, list[Sub] 패턴) |
| `src/scenario_db/models/definition/usecase.py` | model | transform | `src/scenario_db/models/definition/usecase.py` (기존 Variant/Usecase 섹션) | exact (동일 파일 내 기존 패턴 반복) |
| `src/scenario_db/models/evidence/simulation.py` | model | transform | `src/scenario_db/models/evidence/simulation.py` (IpBreakdown) | exact (동일 파일, list[Model] + float 필드 패턴) |
| `src/scenario_db/db/models/capability.py` | ORM model | CRUD | `src/scenario_db/db/models/evidence.py` | exact (JSONB nullable 컬럼 추가) |
| `src/scenario_db/db/models/definition.py` | ORM model | CRUD | `src/scenario_db/db/models/evidence.py` | exact (JSONB nullable 컬럼 추가) |
| `src/scenario_db/db/models/evidence.py` | ORM model | CRUD | `src/scenario_db/db/models/evidence.py` (기존 ip_breakdown, run_info 컬럼) | exact |
| `alembic/versions/0002_schema_extensions.py` | migration | batch | `alembic/versions/0001_initial_schema.py` | role-match (op.add_column vs op.create_table) |
| `src/scenario_db/etl/mappers/capability.py` | ETL mapper | transform | `src/scenario_db/etl/mappers/capability.py` (upsert_ip) | exact (같은 파일 내 기존 패턴) |
| `src/scenario_db/etl/mappers/definition.py` | ETL mapper | transform | `src/scenario_db/etl/mappers/definition.py` (upsert_usecase) | exact |
| `src/scenario_db/etl/mappers/evidence.py` | ETL mapper | transform | `src/scenario_db/etl/mappers/evidence.py` (upsert_simulation) | exact |
| `tests/unit/test_schema_extensions.py` | test | request-response | `tests/unit/test_evidence_models.py` | exact (roundtrip helper + YAML fixture 패턴) |
| `tests/integration/test_alembic_migration.py` | test | batch | `tests/integration/test_validate_loaded.py` | role-match (engine fixture + Session 패턴) |

---

## Pattern Assignments

### `src/scenario_db/models/capability/hw.py` (model, transform)

**Analog:** `src/scenario_db/models/capability/hw.py` (기존 파일) + `src/scenario_db/models/evidence/simulation.py` (list[Sub] 패턴)

**Imports pattern** (hw.py lines 1-12):
```python
from __future__ import annotations

from typing import Literal
from enum import StrEnum

from pydantic import Field, model_validator

from scenario_db.models.common import (
    BaseScenarioModel,
    DocumentId,
    InstanceId,
    SchemaVersion,
)
```

**StrEnum 정의 패턴** (usecase.py lines 30-31 참조 — EdgeType):
```python
class PortType(StrEnum):
    DMA_READ  = "DMA_READ"
    DMA_WRITE = "DMA_WRITE"
    OTF_IN    = "OTF_IN"
    OTF_OUT   = "OTF_OUT"
```

**Sub-model 정의 패턴** (hw.py OperatingMode, lines 19-24):
```python
class OperatingMode(BaseScenarioModel):
    id: str
    throughput_mpps: float | None = None
    max_clock_mhz: float | None = None
    min_clock_mhz: float | None = None
    power_mW: float | None = None
```

**list[Sub] 필드 패턴** (simulation.py IpBreakdown, lines 26-31):
```python
class IpBreakdown(BaseScenarioModel):
    ip: DocumentId
    instance_index: int = 0
    power_mW: float
    submodules: list[SubmoduleBreakdown] = Field(default_factory=list)
```

**신규 IPSimParams + PortSpec 작성 위치 및 패턴:**
```python
# hw.py 기존 IpCapabilities 블록 아래, IpCatalog 클래스 위에 삽입

class PortSpec(BaseScenarioModel):
    name: str
    type: PortType
    max_bw_gbps: float | None = None


class IPSimParams(BaseScenarioModel):
    hw_name_in_sim: str
    ppc: float
    unit_power_mw_mp: float
    idc: float = 0.0
    vdd: str
    dvfs_group: str
    latency_us: float = 0.0
    ports: list[PortSpec] = Field(default_factory=list)
```

**IpCatalog 수정 패턴** (hw.py lines 83-91, 신규 필드 추가):
```python
class IpCatalog(BaseScenarioModel):
    id: DocumentId
    schema_version: SchemaVersion
    kind: Literal["ip"]
    category: str
    hierarchy: IpHierarchy
    capabilities: IpCapabilities
    rtl_version: str | None = None
    compatible_soc: list[DocumentId] = Field(default_factory=list)
    sim_params: IPSimParams | None = None  # NEW — 기본값 None 필수 (backward compat)
```

---

### `src/scenario_db/models/definition/usecase.py` (model, transform)

**Analog:** `src/scenario_db/models/definition/usecase.py` (기존 Variant, Usecase 클래스)

**Imports pattern** (lines 1-16):
```python
from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from scenario_db.models.common import (
    BaseScenarioModel,
    DocumentId,
    FeatureFlagValue,
    SchemaVersion,
    Severity,
    ViolationAction,
    ViolationClassification,
)
```

**신규 PortInputConfig / IPPortConfig / SimGlobalConfig 작성 위치:**
Variant 클래스 **위** (Violation Policy 블록 아래)에 삽입.

**dict[str, SubModel] 필드 패턴** (IpRequirementSpec, lines 96-101):
```python
class IpRequirementSpec(BaseModel):
    model_config = ConfigDict(extra="allow")
    required_throughput_mpps: float | None = None
    required_bitdepth: int | None = None
    required_features: list[str] = Field(default_factory=list)
```

**신규 모델 패턴 (Literal 사용):**
```python
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
```

**Variant 수정 패턴** (lines 155-165, 신규 2개 필드 추가):
```python
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
    sim_port_config: dict[str, IPPortConfig] | None = None  # NEW
    sim_config: SimGlobalConfig | None = None               # NEW
```

**SensorSpec 작성 위치:** Usecase 클래스 **위** (UsecaseMetadata 아래). Usecase 수정:
```python
class SensorSpec(BaseScenarioModel):
    """OTF 그룹 타이밍 제약 기준 — v_valid_time 기반 처리량."""
    ip_ref: DocumentId
    frame_width: int
    frame_height: int
    fps: float
    v_valid_ratio: float = 0.85


class Usecase(BaseScenarioModel):
    id: DocumentId
    schema_version: SchemaVersion
    kind: Literal["scenario.usecase"]
    project_ref: DocumentId
    metadata: UsecaseMetadata
    pipeline: Pipeline
    size_profile: SizeProfile | None = None
    design_axes: list[DesignAxis] = Field(default_factory=list)
    variants: list[Variant] = Field(default_factory=list)
    inheritance_policy: InheritancePolicy | None = None
    parametric_sweeps: list[ParametricSweep] = Field(default_factory=list)
    references: UsecaseReferences | None = None
    sensor: SensorSpec | None = None  # NEW — Usecase 레벨 OTF 센서 스펙
    # ... 기존 model_validator 유지
```

---

### `src/scenario_db/models/evidence/simulation.py` (model, transform)

**Analog:** `src/scenario_db/models/evidence/simulation.py` (IpBreakdown, SubmoduleBreakdown)

**Imports pattern** (lines 1-17):
```python
from __future__ import annotations

import re
from typing import Literal

from pydantic import Field, model_validator

from scenario_db.models.common import BaseScenarioModel, DocumentId, InstanceId, SchemaVersion
from scenario_db.models.evidence.common import (
    Aggregation,
    Artifact,
    ExecutionContext,
    RunInfo,
    SweepContext,
)
from scenario_db.models.evidence.resolution import ResolutionResult
```

**신규 PortBWResult / IPTimingResult 작성 위치:** `IpBreakdown` 클래스 아래, `SimulationEvidence` 위.

**list[float field] 모델 패턴** (IpBreakdown lines 26-31):
```python
class IpBreakdown(BaseScenarioModel):
    ip: DocumentId
    instance_index: int = 0
    power_mW: float
    submodules: list[SubmoduleBreakdown] = Field(default_factory=list)
```

**신규 모델 (Literal["read","write"] — PortType import 없음):**
```python
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
```

**SimulationEvidence 수정 패턴** (lines 33-47, 신규 2개 필드 추가):
```python
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
    dma_breakdown: list[PortBWResult] = Field(default_factory=list)      # NEW
    timing_breakdown: list[IPTimingResult] = Field(default_factory=list)  # NEW
    # 기존 _validate_kpi_keys model_validator 유지
```

---

### `src/scenario_db/db/models/capability.py` (ORM model, CRUD)

**Analog:** `src/scenario_db/db/models/capability.py` (IpCatalog 클래스, lines 21-32)

**Imports pattern** (lines 1-6):
```python
from __future__ import annotations

from sqlalchemy import Column, Text
from sqlalchemy.dialects.postgresql import JSONB

from scenario_db.db.base import Base
```

**기존 IpCatalog ORM 컬럼 패턴** (lines 21-32):
```python
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
```

**신규 컬럼 추가 패턴** (nullable=True가 기본값이므로 `Column(JSONB)` 만으로 충분):
```python
    sim_params     = Column(JSONB)   # nullable — Phase 5 추가
```

---

### `src/scenario_db/db/models/definition.py` (ORM model, CRUD)

**Analog:** `src/scenario_db/db/models/definition.py` (Scenario, ScenarioVariant, lines 19-44)

**Imports pattern** (lines 1-6):
```python
from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB

from scenario_db.db.base import Base
```

**Scenario 신규 컬럼:**
```python
class Scenario(Base):
    __tablename__ = "scenarios"
    # ... 기존 컬럼 ...
    sensor         = Column(JSONB)   # nullable — Phase 5 추가 (Usecase.sensor → ORM)
```

**ScenarioVariant 신규 컬럼 2개:**
```python
class ScenarioVariant(Base):
    __tablename__ = "scenario_variants"
    # ... 기존 컬럼 ...
    sim_port_config = Column(JSONB)  # nullable — Phase 5 추가
    sim_config      = Column(JSONB)  # nullable — Phase 5 추가
```

---

### `src/scenario_db/db/models/evidence.py` (ORM model, CRUD)

**Analog:** `src/scenario_db/db/models/evidence.py` (Evidence 클래스, lines 24-55)

**Imports pattern** (lines 1-7):
```python
from __future__ import annotations

from sqlalchemy import Column, Computed, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB

from scenario_db.db.base import Base
```

**기존 sim-only JSONB 컬럼 패턴** (lines 40-43):
```python
    run_info            = Column(JSONB)             # sim only
    ip_breakdown        = Column(JSONB)             # sim only
    provenance          = Column(JSONB)             # meas only
    artifacts           = Column(JSONB)
```

**신규 컬럼 추가 — 기존 ip_breakdown 바로 아래에 삽입:**
```python
    dma_breakdown    = Column(JSONB)             # sim only — Phase 5 추가
    timing_breakdown = Column(JSONB)             # sim only — Phase 5 추가
```

**주의:** `sw_version_hint`, `sweep_value_hint`의 `Computed` 컬럼은 절대 건드리지 않는다. Alembic autogenerate가 이를 잘못 감지할 수 있다 (RESEARCH.md Pitfall 2).

---

### `alembic/versions/0002_schema_extensions.py` (migration, batch)

**Analog:** `alembic/versions/0001_initial_schema.py`

**헤더 및 imports 패턴** (0001 lines 1-14):
```python
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
```

**upgrade() 패턴 — op.add_column 사용 (op.create_table 아님):**
```python
def upgrade() -> None:
    # ip_catalog — sim_params (SCH-01)
    op.add_column("ip_catalog",
        sa.Column("sim_params", JSONB, nullable=True))

    # scenarios — sensor (SCH-03)
    op.add_column("scenarios",
        sa.Column("sensor", JSONB, nullable=True))

    # scenario_variants — sim_port_config, sim_config (SCH-02)
    op.add_column("scenario_variants",
        sa.Column("sim_port_config", JSONB, nullable=True))
    op.add_column("scenario_variants",
        sa.Column("sim_config", JSONB, nullable=True))

    # evidence — dma_breakdown, timing_breakdown (SCH-04)
    op.add_column("evidence",
        sa.Column("dma_breakdown", JSONB, nullable=True))
    op.add_column("evidence",
        sa.Column("timing_breakdown", JSONB, nullable=True))
```

**downgrade() 패턴 — upgrade와 역순 삭제 (0001 lines 264-279 참조):**
```python
def downgrade() -> None:
    op.drop_column("evidence", "timing_breakdown")
    op.drop_column("evidence", "dma_breakdown")
    op.drop_column("scenario_variants", "sim_config")
    op.drop_column("scenario_variants", "sim_port_config")
    op.drop_column("scenarios", "sensor")
    op.drop_column("ip_catalog", "sim_params")
```

**컬럼 계수 체크:** upgrade 6개 add = downgrade 6개 drop.
(RESEARCH.md: 실제 7개라고 했으나 `Scenario.sensor`가 `scenarios` 테이블에 1개이므로 총 6 op.add_column — 확인 필요)

---

### `src/scenario_db/etl/mappers/capability.py` (ETL mapper, transform)

**Analog:** `src/scenario_db/etl/mappers/capability.py` (upsert_ip, lines 26-38)

**전체 upsert_ip() 패턴** (lines 26-38):
```python
def upsert_ip(raw: dict, sha256: str, session: Session) -> None:
    obj = PydanticIp.model_validate(raw)
    row = session.get(IpCatalog, obj.id) or IpCatalog(id=obj.id)
    if row.yaml_sha256 == sha256:
        return
    row.schema_version = obj.schema_version
    row.category       = obj.category
    row.hierarchy      = obj.hierarchy.model_dump(exclude_none=True)
    row.capabilities   = obj.capabilities.model_dump(exclude_none=True) if obj.capabilities else None
    row.rtl_version    = obj.rtl_version
    row.compatible_soc = list(obj.compatible_soc)
    row.yaml_sha256    = sha256
    session.add(row)
```

**신규 필드 직렬화 — `row.yaml_sha256 = sha256` 라인 바로 위에 삽입:**
```python
    row.sim_params     = obj.sim_params.model_dump(exclude_none=True) if obj.sim_params else None
```

**패턴 규칙:** Optional 단일 모델은 `obj.X.model_dump(exclude_none=True) if obj.X else None`.

---

### `src/scenario_db/etl/mappers/definition.py` (ETL mapper, transform)

**Analog:** `src/scenario_db/etl/mappers/definition.py` (upsert_usecase, lines 22-53)

**Scenario row 직렬화 패턴** (lines 28-37):
```python
    row.schema_version = obj.schema_version
    row.project_ref    = str(obj.project_ref)
    row.metadata_      = obj.metadata.model_dump(exclude_none=True)
    row.pipeline       = obj.pipeline.model_dump(by_alias=True, exclude_none=True)
    row.size_profile   = obj.size_profile.model_dump(exclude_none=True) if obj.size_profile else None
    row.design_axes    = [a.model_dump(exclude_none=True) for a in obj.design_axes]
    row.yaml_sha256    = sha256
```

**신규 sensor 필드 — `row.yaml_sha256 = sha256` 라인 바로 위에 삽입:**
```python
    row.sensor         = obj.sensor.model_dump(exclude_none=True) if obj.sensor else None
```

**Variant loop 패턴** (lines 39-53):
```python
    session.query(ScenarioVariant).filter_by(scenario_id=obj.id).delete()
    for v in obj.variants:
        vrow = ScenarioVariant(scenario_id=obj.id, id=v.id)
        vrow.severity            = str(v.severity)
        vrow.design_conditions   = v.design_conditions or {}
        vrow.ip_requirements     = {
            k: vv.model_dump(exclude_none=True)
            for k, vv in v.ip_requirements.items()
        }
        vrow.sw_requirements     = v.sw_requirements.model_dump(exclude_none=True) if v.sw_requirements else None
        vrow.violation_policy    = v.violation_policy.model_dump(exclude_none=True) if v.violation_policy else None
        vrow.tags                = list(v.tags)
        vrow.derived_from_variant = v.derived_from_variant
        session.add(vrow)
```

**신규 Variant 필드 — `session.add(vrow)` 바로 위에 삽입:**
```python
        vrow.sim_port_config = (
            {k: cfg.model_dump(exclude_none=True) for k, cfg in v.sim_port_config.items()}
            if v.sim_port_config else None
        )
        vrow.sim_config = v.sim_config.model_dump(exclude_none=True) if v.sim_config else None
```

**dict[str, SubModel] 직렬화 패턴** (ip_requirements, line 44-46):
```python
        vrow.ip_requirements = {
            k: vv.model_dump(exclude_none=True)
            for k, vv in v.ip_requirements.items()
        }
```
sim_port_config도 같은 dict comprehension 패턴을 따른다.

---

### `src/scenario_db/etl/mappers/evidence.py` (ETL mapper, transform)

**Analog:** `src/scenario_db/etl/mappers/evidence.py` (upsert_simulation, lines 10-35)

**list[Model] 직렬화 패턴** (lines 31-32):
```python
    row.ip_breakdown = [b.model_dump(exclude_none=True) for b in obj.ip_breakdown]
    row.artifacts    = [a.model_dump(exclude_none=True) for a in obj.artifacts]
```

**신규 list[Model] 필드 — `row.yaml_sha256 = sha256` 라인 바로 위에 삽입:**
```python
    row.dma_breakdown    = [b.model_dump(exclude_none=True) for b in obj.dma_breakdown]
    row.timing_breakdown = [t.model_dump(exclude_none=True) for t in obj.timing_breakdown]
```

**패턴 규칙:** `Field(default_factory=list)` 필드는 None 체크 없이 직접 list comprehension.

---

### `tests/unit/test_schema_extensions.py` (test, NEW)

**Analog:** `tests/unit/test_evidence_models.py`

**파일 구조 패턴** (lines 1-50):
```python
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from scenario_db.models.capability.hw import IpCatalog, IPSimParams, PortSpec, PortType
from scenario_db.models.definition.usecase import (
    Usecase, Variant, SensorSpec, SimGlobalConfig, IPPortConfig, PortInputConfig,
)
from scenario_db.models.evidence.simulation import (
    SimulationEvidence, PortBWResult, IPTimingResult,
)

FIXTURES = Path(__file__).parent / "fixtures"
```

**roundtrip helper 패턴** (test_evidence_models.py lines 44-50):
```python
def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def roundtrip(model_cls, path: Path, **dump_kwargs):
    raw = load_yaml(path)
    obj = model_cls.model_validate(raw)
    serialised = obj.model_dump(exclude_none=True, **dump_kwargs)
    obj2 = model_cls.model_validate(serialised)
    assert obj == obj2
    return obj
```

**backward compat 테스트 패턴** (기존 fixture + 신규 Optional 필드):
```python
def test_ip_catalog_backward_compat_no_sim_params():
    """기존 ip-isp-v12.yaml (sim_params 없음)이 ValidationError 없이 파싱된다."""
    obj = roundtrip(IpCatalog, FIXTURES / "hw" / "ip-isp-v12.yaml")
    assert obj.sim_params is None


def test_ip_catalog_sim_params_roundtrip():
    """sim_params가 있는 fixture가 round-trip 직렬화를 통과한다."""
    obj = roundtrip(IpCatalog, FIXTURES / "hw" / "ip-isp-v12-with-sim.yaml")
    assert obj.sim_params.hw_name_in_sim == "ISP"
    assert obj.sim_params.ppc == 4.0
    assert len(obj.sim_params.ports) == 4
```

**extra='forbid' 검증 패턴** (test_evidence_models.py lines 373-378):
```python
def test_extra_fields_forbidden_sim():
    raw = load_yaml(FIXTURES / "evidence" / "sim-camera-recording-UHD60-A0-sw123.yaml")
    raw["unknown_field"] = "oops"
    with pytest.raises(ValidationError):
        SimulationEvidence.model_validate(raw)
```

**inline dict 검증 패턴** (test_evidence_models.py lines 306-323):
```python
def test_sim_kpi_key_invalid_camelcase():
    with pytest.raises(ValidationError, match="lowercase snake_case"):
        SimulationEvidence.model_validate({
            "id": "sim-test-01",
            ...
        })
```

**신규 테스트 추가 위치:** 기존 `test_capability_models.py`, `test_definition_models.py`, `test_evidence_models.py` 각 파일에 함수를 **추가**하거나 `test_schema_extensions.py` 신규 파일에 집약한다. RESEARCH.md Wave 0 Gaps 기준으로 신규 파일 방식 권장.

---

### `tests/integration/test_alembic_migration.py` (test, NEW)

**Analog:** `tests/integration/test_validate_loaded.py` + `tests/integration/conftest.py`

**모듈 선언 패턴** (test_validate_loaded.py lines 1-11):
```python
"""Alembic migration 0002 upgrade/downgrade + ETL 신규 컬럼 반영 통합 테스트."""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration
```

**engine fixture 사용 패턴** (conftest.py lines 41-63):
```python
@pytest.fixture(scope="session")
def engine(pg):
    url = pg.get_connection_url()
    # ... psycopg2 URL 변환 ...
    from alembic import command
    from alembic.config import Config
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")  # 0002까지 적용됨
    # ...
```

**DB 컬럼 직접 확인 패턴:**
```python
def test_new_columns_exist_after_migration(engine):
    """migration 0002 적용 후 신규 컬럼이 DB 스키마에 존재한다."""
    from sqlalchemy import inspect
    insp = inspect(engine)
    ip_cols = {c["name"] for c in insp.get_columns("ip_catalog")}
    assert "sim_params" in ip_cols
    # ...
```

**ETL 로드 후 컬럼 데이터 확인 패턴:**
```python
def test_sim_params_column_populated(engine):
    """sim_params가 있는 fixture 로드 후 DB 컬럼에 데이터가 저장된다."""
    from scenario_db.db.models.capability import IpCatalog as OrmIpCatalog
    with Session(engine) as session:
        row = session.get(OrmIpCatalog, "ip-isp-v12")
    # sim_params fixture가 없으면 None — backward compat 확인
    assert row is not None
```

---

## Shared Patterns

### BaseScenarioModel (extra='forbid')
**Source:** `src/scenario_db/models/common.py` lines 81-83
**Apply to:** 모든 신규 Pydantic 모델 (IPSimParams, PortSpec, PortInputConfig, IPPortConfig, SimGlobalConfig, SensorSpec, PortBWResult, IPTimingResult)
```python
class BaseScenarioModel(BaseModel):
    """All scenario-db models inherit this to enforce extra='forbid'."""
    model_config = ConfigDict(extra="forbid")
```

### Optional 필드 기본값 규칙
**Source:** `src/scenario_db/models/capability/hw.py` lines 86-91
**Apply to:** 모든 신규 필드 (backward compat 보장)
```python
# Optional 단일 모델
sim_params: IPSimParams | None = None

# Optional list
dma_breakdown: list[PortBWResult] = Field(default_factory=list)

# Optional dict
sim_port_config: dict[str, IPPortConfig] | None = None
```

### ETL 직렬화 3가지 패턴
**Source:** `src/scenario_db/etl/mappers/capability.py` lines 21-38
**Apply to:** 모든 ETL mapper 수정

```python
# 1. Optional 단일 모델 → dict
row.X = obj.X.model_dump(exclude_none=True) if obj.X else None

# 2. list[Model] → list[dict]
row.X = [item.model_dump(exclude_none=True) for item in obj.X]

# 3. dict[str, Model] → dict[str, dict]
row.X = {k: v.model_dump(exclude_none=True) for k, v in obj.X.items()} if obj.X else None
```

### JSONB nullable 컬럼 추가 패턴
**Source:** `src/scenario_db/db/models/capability.py` lines 21-32
**Apply to:** 모든 ORM 수정 파일 (capability, definition, evidence)
```python
# nullable=True가 Column()의 기본값 — 명시적으로 쓰지 않아도 됨
new_field = Column(JSONB)   # nullable — Phase 5 추가
```

### Alembic op.add_column 패턴
**Source:** `alembic/versions/0001_initial_schema.py` (create_table 구조 참조)
**Apply to:** `0002_schema_extensions.py`
```python
op.add_column("table_name",
    sa.Column("column_name", JSONB, nullable=True))
```

### 테스트 roundtrip helper
**Source:** `tests/unit/test_evidence_models.py` lines 44-50
**Apply to:** `tests/unit/test_schema_extensions.py`
```python
def roundtrip(model_cls, path: Path, **dump_kwargs):
    raw = load_yaml(path)
    obj = model_cls.model_validate(raw)
    serialised = obj.model_dump(exclude_none=True, **dump_kwargs)
    obj2 = model_cls.model_validate(serialised)
    assert obj == obj2
    return obj
```

### 통합 테스트 engine fixture 사용
**Source:** `tests/integration/conftest.py` lines 41-63
**Apply to:** `tests/integration/test_alembic_migration.py`
```python
pytestmark = pytest.mark.integration

def test_something(engine):   # conftest.py session-scope engine fixture 주입
    with Session(engine) as session:
        ...
```

---

## No Analog Found

해당 없음 — 모든 파일에 대해 정확한 또는 역할 일치 analog가 발견되었다.

---

## Critical Constraints (RESEARCH.md 기반)

| 제약 | 위반 시 결과 | 적용 대상 |
|---|---|---|
| 신규 Pydantic 필드는 반드시 `= None` 또는 `default_factory` 기본값 | 기존 YAML fixture `ValidationError` | 모든 Pydantic 모델 수정 |
| ETL 매퍼에서 신규 필드 직렬화 누락 금지 | DB에 NULL만 저장, 오류 없음 — 데이터 유실 | 모든 ETL mapper |
| Alembic 수동 작성 (autogenerate 사용 금지) | Computed 컬럼 잘못 감지 → 불필요한 alter_column | 0002 migration |
| `PortBWResult.direction`은 `Literal["read","write"]` (PortType enum 재사용 금지) | hw.py ↔ simulation.py 순환 import | simulation.py |
| `model_dump(exclude_none=True)` 사용 (vars() 금지) | extra='forbid' 위반 | 모든 ETL mapper |

---

## Metadata

**Analog search scope:** `src/scenario_db/models/`, `src/scenario_db/db/models/`, `src/scenario_db/etl/mappers/`, `alembic/versions/`, `tests/unit/`, `tests/integration/`
**Files scanned:** 14개 직접 읽음
**Pattern extraction date:** 2026-05-10
