# Phase A — PostgreSQL + ETL 구현 계획

## Context

Phase 1~4 완료 (124개 테스트 통과). Pydantic 모델 레이어가 완성됐다.
Phase A는 v2.2 모델을 실제 PostgreSQL DB로 연결하고 YAML 임포트 파이프라인을 구축한다.
최종 목표: Swagger UI + 자동 Review Gate Demo를 위한 데이터 기반.

---

## 리뷰 반영 개선 사항 (rev.2)

| # | 개선 내용 | 적용 위치 |
|---|----------|----------|
| 1 | 파일 단위 SAVEPOINT — `session.begin_nested()` | `etl/loader.py` §4-1 |
| 2 | `PipelineEdge.from_` alias 직렬화 — `model_dump(by_alias=True)` 필수 | `etl/mappers/definition.py` §4-2 |
| 3 | Computed 컬럼 `::text` 캐스트 + `index=True` | `db/models/evidence.py` §2-5 |
| 4 | Alembic `compare_type=True` + `compare_server_default=True` | `alembic/env.py` §3 |

**Point 2 보충 설명**: 사용자가 지적한 파이프라인 경로 무결성 문제의 실제 ETL 위험은 Android 런타임(SurfaceFlinger/BufferQueue) 레벨이 아니라 **Pydantic Field alias 직렬화**에 있다. `PipelineEdge`의 `from_` 필드가 `by_alias=True` 없이 직렬화되면 JSONB에 `"from_"`으로 저장되어 YAML 원본 스키마(`"from"`)와 불일치. Pydantic `model_validate`가 파이프라인 edge 참조 무결성(`from_/to` → node id)을 이미 검증하므로 별도 ETL 레이어 재검증은 중복이다.

---

## 신규 파일 구조

```
02_ScenarioDB/
├── docker-compose.yml               # PostgreSQL 16 + pgAdmin 4
├── .env                             # DATABASE_URL, pgAdmin 자격증명
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 0001_initial_schema.py   # §22 전체 DDL
├── src/scenario_db/
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py                  # engine 팩토리, DeclarativeBase
│   │   ├── session.py               # SessionFactory, get_session()
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── capability.py        # ORM: SocPlatform, IpCatalog, SwProfile, SwComponent
│   │       ├── definition.py        # ORM: Project, Scenario, ScenarioVariant
│   │       ├── evidence.py          # ORM: Evidence, SweepJob
│   │       └── decision.py          # ORM: Review, Waiver, Issue, GateRule + audit logs
│   └── etl/
│       ├── __init__.py
│       ├── loader.py                # load_yaml_dir() 진입점
│       └── mappers/
│           ├── __init__.py
│           ├── capability.py        # soc / ip / sw_profile / sw_component
│           ├── definition.py        # project / scenario.usecase
│           ├── evidence.py          # evidence.simulation / evidence.measurement
│           └── decision.py          # decision.review / waiver / issue / gate_rule
└── demo/
    └── fixtures/
        ├── 00_hw/                   # SoC + IP (6개)
        ├── 01_sw/                   # SW Profile + 컴포넌트 (3개)
        ├── 02_definition/           # Project + Usecase (2개)
        ├── 03_evidence/             # Sim + Meas (3개)
        └── 04_decision/             # Issue / Waiver / Review / Rule (6개)
```

---

## 1. docker-compose.yml

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: scenario_db
      POSTGRES_USER: scenario_user
      POSTGRES_PASSWORD: scenario_pass
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U scenario_user -d scenario_db"]
      interval: 5s
      timeout: 5s
      retries: 5

  pgadmin:
    image: dpage/pgadmin4:latest
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@scenariodb.local
      PGADMIN_DEFAULT_PASSWORD: admin
    ports:
      - "5050:80"
    depends_on:
      postgres:
        condition: service_healthy

volumes:
  pgdata:
```

`.env`:
```
DATABASE_URL=postgresql+psycopg2://scenario_user:scenario_pass@localhost:5432/scenario_db
```

---

## 2. SQLAlchemy ORM (`src/scenario_db/db/`)

### 2-1. `base.py`

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

def make_engine(url: str):
    return create_engine(url, echo=False)
```

### 2-2. `session.py`

```python
from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker, Session

@contextmanager
def get_session(engine) -> Session:
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
```

### 2-3. `db/models/capability.py`

```python
from sqlalchemy import Column, Text
from sqlalchemy.dialects.postgresql import JSONB
from scenario_db.db.base import Base

class SocPlatform(Base):
    __tablename__ = "soc_platforms"
    id             = Column(Text, primary_key=True)
    schema_version = Column(Text, nullable=False)
    process_node   = Column(Text)
    memory_type    = Column(Text)
    bus_protocol   = Column(Text)
    ips            = Column(JSONB)             # list[{ref, instance_count}]
    yaml_sha256    = Column(Text, nullable=False)

class IpCatalog(Base):
    __tablename__ = "ip_catalog"
    id             = Column(Text, primary_key=True)
    schema_version = Column(Text, nullable=False)
    category       = Column(Text)
    hierarchy      = Column(JSONB)             # type, submodules
    capabilities   = Column(JSONB)             # operating_modes, supported_features
    rtl_version    = Column(Text)
    compatible_soc = Column(JSONB)             # list[str]
    yaml_sha256    = Column(Text, nullable=False)

class SwProfile(Base):
    __tablename__ = "sw_profiles"
    id             = Column(Text, primary_key=True)
    schema_version = Column(Text, nullable=False)
    metadata_      = Column("metadata", JSONB, nullable=False)
    components     = Column(JSONB, nullable=False)
    feature_flags  = Column(JSONB, nullable=False)
    compatibility  = Column(JSONB)
    yaml_sha256    = Column(Text, nullable=False)

class SwComponent(Base):
    __tablename__ = "sw_components"
    id             = Column(Text, primary_key=True)
    schema_version = Column(Text, nullable=False)
    category       = Column(Text)              # hal | kernel | firmware
    metadata_      = Column("metadata", JSONB)
    feature_flags  = Column(JSONB)
    capabilities   = Column(JSONB)
    yaml_sha256    = Column(Text, nullable=False)
```

### 2-4. `db/models/definition.py`

```python
class Project(Base):
    __tablename__ = "projects"
    id             = Column(Text, primary_key=True)
    schema_version = Column(Text, nullable=False)
    metadata_      = Column("metadata", JSONB, nullable=False)
    globals_       = Column("globals", JSONB)
    yaml_sha256    = Column(Text, nullable=False)

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

class ScenarioVariant(Base):
    __tablename__ = "scenario_variants"
    # Composite PK: scenario_id + id (variant id는 freeform)
    scenario_id          = Column(Text, ForeignKey("scenarios.id"), primary_key=True)
    id                   = Column(Text, primary_key=True)
    severity             = Column(Text)
    design_conditions    = Column(JSONB)
    ip_requirements      = Column(JSONB)
    sw_requirements      = Column(JSONB)
    violation_policy     = Column(JSONB)
    tags                 = Column(JSONB)             # list[str]
    derived_from_variant = Column(Text)
```

### 2-5. `db/models/evidence.py`

```python
from sqlalchemy import Computed   # generated columns

class SweepJob(Base):
    __tablename__ = "sweep_jobs"
    id             = Column(Text, primary_key=True)
    scenario_ref   = Column(Text, ForeignKey("scenarios.id"), nullable=False)
    variant_ref    = Column(Text, nullable=False)
    sweep_axis     = Column(Text, nullable=False)
    sweep_values   = Column(JSONB, nullable=False)
    total_runs     = Column(Integer, nullable=False)
    completed_runs = Column(Integer, default=0)
    status         = Column(Text)
    launched_at    = Column(DateTime(timezone=True))
    completed_at   = Column(DateTime(timezone=True))

class Evidence(Base):
    __tablename__ = "evidence"
    id                  = Column(Text, primary_key=True)
    schema_version      = Column(Text, nullable=False)
    kind                = Column(Text, nullable=False)  # evidence.simulation | evidence.measurement
    scenario_ref        = Column(Text, ForeignKey("scenarios.id"), nullable=False)
    variant_ref         = Column(Text, nullable=False)
    sw_baseline_ref     = Column(Text, ForeignKey("sw_profiles.id"))
    sweep_job_id        = Column(Text, ForeignKey("sweep_jobs.id"))
    execution_context   = Column(JSONB, nullable=False)
    sweep_context       = Column(JSONB)
    resolution_result   = Column(JSONB)
    overall_feasibility = Column(Text)              # 승격 컬럼 (쿼리 최적화)
    aggregation         = Column(JSONB, nullable=False)
    kpi                 = Column(JSONB, nullable=False)
    run_info            = Column(JSONB)             # sim only
    ip_breakdown        = Column(JSONB)             # sim only
    provenance          = Column(JSONB)             # meas only
    artifacts           = Column(JSONB)
    yaml_sha256         = Column(Text, nullable=False)
    # §22 Generated columns (PostgreSQL ≥12) — 개선 #3: ::text 캐스트 + index=True
    sw_version_hint  = Column(
        Text,
        Computed("(execution_context->>'sw_baseline_ref')::text", persisted=True),
        index=True,    # B-Tree 인덱스 자동 생성
    )
    sweep_value_hint = Column(
        Text,
        Computed("(sweep_context->>'sweep_value')::text", persisted=True),
        index=True,
    )
```

### 2-6. `db/models/decision.py`

```python
class GateRule(Base):
    __tablename__ = "gate_rules"
    id             = Column(Text, primary_key=True)
    schema_version = Column(Text, nullable=False)
    metadata_      = Column("metadata", JSONB, nullable=False)
    trigger        = Column(JSONB, nullable=False)
    applies_to     = Column(JSONB)
    condition      = Column(JSONB, nullable=False)
    action         = Column(JSONB, nullable=False)
    yaml_sha256    = Column(Text, nullable=False)

class Issue(Base):
    __tablename__ = "issues"
    id             = Column(Text, primary_key=True)
    schema_version = Column(Text, nullable=False)
    metadata_      = Column("metadata", JSONB, nullable=False)
    affects        = Column(JSONB)
    affects_ip     = Column(JSONB)
    pmu_signature  = Column(JSONB)
    resolution     = Column(JSONB)
    yaml_sha256    = Column(Text, nullable=False)

class Waiver(Base):
    __tablename__ = "waivers"
    id                      = Column(Text, primary_key=True)
    yaml_sha256             = Column(Text, nullable=False)
    title                   = Column(Text, nullable=False)
    issue_ref               = Column(Text, ForeignKey("issues.id"))
    scope                   = Column(JSONB, nullable=False)
    justification           = Column(Text)
    status                  = Column(Text, nullable=False)
    # Track 1: Author Claim
    approver_claim          = Column(Text, nullable=False)
    claim_at                = Column(Date)
    # Track 2: Git
    git_commit_sha          = Column(Text)
    git_commit_author_email = Column(Text)
    git_signed              = Column(Boolean)
    # Track 3: Server (API 주입)
    approved_by_auth        = Column(Text)
    auth_method             = Column(Text)
    auth_timestamp          = Column(DateTime(timezone=True))
    auth_session_id         = Column(Text)
    approved_at             = Column(Date)
    expires_on              = Column(Date)

class WaiverAuditLog(Base):
    __tablename__ = "waiver_audit_log"
    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    waiver_id    = Column(Text, nullable=False)
    action       = Column(Text, nullable=False)   # created | approved | revoked | expired
    actor        = Column(Text)
    actor_method = Column(Text)
    timestamp    = Column(DateTime(timezone=True), server_default=func.now())
    before_state = Column(JSONB)
    after_state  = Column(JSONB)

class Review(Base):
    __tablename__ = "reviews"
    id                      = Column(Text, primary_key=True)
    yaml_sha256             = Column(Text, nullable=False)
    scenario_ref            = Column(Text, ForeignKey("scenarios.id"), nullable=False)
    variant_ref             = Column(Text, nullable=False)
    evidence_refs           = Column(JSONB)
    gate_result             = Column(Text)   # PASS | WARN | BLOCK
    auto_checks             = Column(JSONB)
    decision                = Column(Text)
    waiver_ref              = Column(Text, ForeignKey("waivers.id"))
    rationale               = Column(Text)
    review_scope            = Column(JSONB)
    validation_             = Column("validation", JSONB)
    status                  = Column(Text, nullable=False)
    # Triple-Track (Waiver와 동일 구조)
    approver_claim          = Column(Text, nullable=False)
    claim_at                = Column(Date)
    git_commit_sha          = Column(Text)
    git_commit_author_email = Column(Text)
    git_signed              = Column(Boolean)
    approved_by_auth        = Column(Text)
    auth_method             = Column(Text)
    auth_timestamp          = Column(DateTime(timezone=True))
    auth_session_id         = Column(Text)

class ReviewAuditLog(Base):
    __tablename__ = "review_audit_log"
    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    review_id    = Column(Text, nullable=False)
    action       = Column(Text, nullable=False)
    actor        = Column(Text)
    actor_method = Column(Text)
    timestamp    = Column(DateTime(timezone=True), server_default=func.now())
    before_state = Column(JSONB)
    after_state  = Column(JSONB)
```

---

## 3. Alembic DDL (`alembic/versions/0001_initial_schema.py`)

§22 DDL을 Alembic op으로 구현. 테이블 생성 순서는 FK 의존성 기준:

```
soc_platforms → ip_catalog → sw_profiles → sw_components
→ projects → scenarios → scenario_variants → sweep_jobs
→ evidence → gate_rules → issues → waivers → waiver_audit_log
→ reviews → review_audit_log
```

**핵심 DDL 포인트**:
- `sw_profiles.feature_flags`: GIN 인덱스 (`USING gin`)
- `evidence.sw_version_hint`: `GENERATED ALWAYS AS ((execution_context->>'sw_baseline_ref')::text) STORED` — `::text` 캐스트 명시 (개선 #3)
- `waiver_audit_log.id`: `UUID DEFAULT gen_random_uuid()`
- `alembic.ini`의 URL은 `%(DATABASE_URL)s` → `env.py`에서 환경변수 주입

**`alembic/env.py` — compare 옵션 (개선 #4)**:

```python
def run_migrations_online() -> None:
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,              # 컬럼 타입 변경 감지
            compare_server_default=True,    # server_default 변경 감지
            include_schemas=True,
        )
        with context.begin_transaction():
            context.run_migrations()
```

`compare_type=True` 없으면 `Text` → `VARCHAR(255)` 같은 타입 변경이 autogenerate에서 누락.
`compare_server_default=True` 없으면 `server_default=func.now()` 추가 변경이 감지 안 됨.

---

## 4. ETL Importer (`src/scenario_db/etl/`)

### 4-1. `loader.py` 핵심 설계 — 파일 단위 SAVEPOINT (개선 #1)

```python
import logging
logger = logging.getLogger(__name__)

LOAD_ORDER = [
    "soc", "ip", "submodule",
    "sw_profile", "sw_component",
    "project", "scenario.usecase",
    "evidence.simulation", "evidence.measurement",
    "decision.gate_rule",    # gate_rule 먼저 — review의 auto_checks FK
    "decision.issue",
    "decision.waiver",
    "decision.review",
]

def load_yaml_dir(directory: Path, session: Session) -> dict[str, int]:
    by_kind: dict[str, list[tuple[Path, dict, str]]] = defaultdict(list)
    for path in sorted(directory.rglob("*.yaml")):
        sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        kind = raw.get("kind")
        if kind in MAPPER_REGISTRY:
            by_kind[kind].append((path, raw, sha256))

    counts: dict[str, int] = {}
    errors: list[str] = []
    for kind in LOAD_ORDER:
        success = 0
        for path, raw, sha256 in by_kind.get(kind, []):
            try:
                with session.begin_nested():         # PostgreSQL SAVEPOINT
                    MAPPER_REGISTRY[kind](raw, sha256, session)
                success += 1
            except Exception as exc:
                logger.error("skip %s [%s]: %s", path.name, kind, exc)
                errors.append(f"{path.name}: {exc}")
        counts[kind] = success
    session.commit()
    if errors:
        logger.warning("%d file(s) skipped due to errors", len(errors))
    return counts
```

**SAVEPOINT 패턴 이유**: `begin_nested()`는 PostgreSQL SAVEPOINT를 생성한다. 개별 파일 오류 시 해당 SAVEPOINT만 롤백 — 나머지 정상 파일의 변경은 보존. 마지막 `session.commit()`이 외부 트랜잭션 확정.

### 4-2. 각 mapper 공통 패턴 — `by_alias=True` 직렬화 (개선 #2)

```python
def upsert_sw_profile(raw: dict, sha256: str, session: Session) -> None:
    # 1. Pydantic 검증 — pipeline 에지 참조 무결성 포함
    obj = PydanticSwProfile.model_validate(raw)
    # 2. SHA256 미변경 시 skip
    existing = session.get(DbSwProfile, obj.id)
    if existing and existing.yaml_sha256 == sha256:
        return
    # 3. upsert — exclude_none=True로 null 필드 제거
    row = existing or DbSwProfile(id=obj.id)
    row.schema_version = obj.schema_version
    row.metadata_      = obj.metadata.model_dump(exclude_none=True)
    row.components     = obj.components.model_dump(exclude_none=True)
    row.feature_flags  = dict(obj.feature_flags)
    row.compatibility  = obj.compatibility.model_dump(exclude_none=True) if obj.compatibility else None
    row.yaml_sha256    = sha256
    session.add(row)
```

**`scenario.usecase` mapper — pipeline 직렬화 주의점**:

`PipelineEdge`는 Python 예약어 우회를 위해 `from_: str = Field(alias="from")`를 사용한다.
`model_dump()` 기본 호출은 Python 속성명(`from_`)으로 직렬화 → JSONB에 `"from_"` 저장 → YAML 스키마(`"from"`)와 불일치.

```python
def upsert_usecase(raw: dict, sha256: str, session: Session) -> None:
    obj = PydanticUsecase.model_validate(raw)

    # Scenario 행
    row = session.get(DbScenario, obj.id) or DbScenario(id=obj.id)
    row.project_ref  = str(obj.project_ref)
    row.metadata_    = obj.metadata.model_dump(exclude_none=True)
    # ↓ by_alias=True 필수 — PipelineEdge.from_ → "from"으로 직렬화
    row.pipeline     = obj.pipeline.model_dump(by_alias=True, exclude_none=True)
    row.design_axes  = [a.model_dump() for a in obj.design_axes]
    row.yaml_sha256  = sha256
    session.add(row)

    # ScenarioVariant 행 — usecase 전체가 source of truth → 전량 재삽입
    session.query(DbScenarioVariant).filter_by(scenario_id=obj.id).delete()
    for v in obj.variants:
        vrow = DbScenarioVariant(scenario_id=obj.id, id=v.id)
        vrow.severity           = str(v.severity)
        vrow.design_conditions  = v.design_conditions
        vrow.ip_requirements    = {k: vv.model_dump(exclude_none=True) for k, vv in v.ip_requirements.items()}
        vrow.sw_requirements    = v.sw_requirements.model_dump(exclude_none=True) if v.sw_requirements else None
        vrow.violation_policy   = v.violation_policy.model_dump(exclude_none=True) if v.violation_policy else None
        vrow.tags               = list(v.tags)
        vrow.derived_from_variant = v.derived_from_variant
        session.add(vrow)
```

**`evidence` mapper**:
- `overall_feasibility` 승격 추출: `obj.resolution_result.overall_feasibility if obj.resolution_result else None`
- `sw_baseline_ref` 추출: `str(obj.execution_context.sw_baseline_ref)`
- `run_info` (sim only): `obj.run.model_dump(exclude_none=True) if hasattr(obj, 'run') else None`

---

## 5. Demo Seed Data (`demo/fixtures/`)

### 5-1. The Demo Story: LLC Thrashing Bug Before/After

| 단계 | 파일 | 핵심 내용 |
|------|------|----------|
| 1 | `sw-vendor-v1.2.3.yaml` | `LLC_per_ip_partition: disabled` (버그) |
| 2 | `iss-LLC-thrashing-0221.yaml` | `fixed_in_sw: sw-vendor-v1.3.0` |
| 3 | `sim-UHD60-A0-sw123.yaml` | SW violation, `overall_feasibility: exploration_only` |
| 4 | `waiver-LLC-thrashing.yaml` | `status: approved`, Track 3 채워진 완전한 형태 |
| 5 | `rev-sw123.yaml` | `gate_result: WARN`, `decision: approved_with_waiver` |
| 6 | `sw-vendor-v1.3.0.yaml` 🆕 | `LLC_per_ip_partition: enabled` (수정) |
| 7 | `sim-UHD60-A0-sw130.yaml` 🆕 | violations 없음, `overall_feasibility: production_ready` |
| 8 | `rev-sw130.yaml` 🆕 | `gate_result: PASS`, `decision: approved` |

### 5-2. `00_hw/` — 신규 필요 IP들

기존 `tests/fixtures/hw/ip-isp-v12.yaml` 외, usecase pipeline에서 참조하는 IP 모두 충족:

| 파일 | kind | 참조 위치 |
|------|------|----------|
| `soc-exynos2500.yaml` | `soc` | 이슈 scope |
| `ip-isp-v12.yaml` | `ip` | usecase pipeline, sim ip_breakdown |
| `ip-mfc-v14.yaml` 🆕 | `ip` | usecase pipeline, sim ip_breakdown |
| `ip-llc-v2.yaml` 🆕 | `ip` | 이슈 affects_ip |
| `ip-csis-v8.yaml` 🆕 | `ip` | usecase pipeline |
| `ip-dpu-v9.yaml` 🆕 | `ip` | usecase pipeline |

### 5-3. `01_sw/`

| 파일 | 핵심 차이점 |
|------|-----------|
| `sw-vendor-v1.2.3.yaml` | `LLC_per_ip_partition: disabled`, `known_issues_at_release: [{ref: iss-LLC-thrashing-0221, status: workaround_applied}]` |
| `sw-vendor-v1.3.0.yaml` 🆕 | `LLC_per_ip_partition: enabled`, `known_issues_at_release: []`, `compatibility.replaces: sw-vendor-v1.2.3` |
| `hal-cam-v4.5.yaml` | 기존 복사 |

### 5-4. `03_evidence/` — Before/After 핵심

**`sim-UHD60-A0-sw123.yaml`** (기존 fixtures 개선 — LLC 위반 반영):
```yaml
execution_context:
  sw_baseline_ref: sw-vendor-v1.2.3   # LLC 버그 버전
resolution_result:
  sw_resolution:
    violations:
      - feature: LLC_per_ip_partition
        required: enabled
        actual: disabled
        action_taken: WARN_AND_EMULATE
  overall_feasibility: exploration_only   # ← 핵심
  violation_summary: { total: 1, warn_and_emulate: 1 }
kpi:
  total_power_mw: 2350    # LLC 비효율 → 전력 증가
```

**`sim-UHD60-A0-sw130.yaml`** 🆕 (sw1.3.0 — 수정 후):
```yaml
execution_context:
  sw_baseline_ref: sw-vendor-v1.3.0   # LLC 수정 버전
resolution_result:
  sw_resolution:
    violations: []
  overall_feasibility: production_ready   # ← 핵심
  violation_summary: { total: 0 }
kpi:
  total_power_mw: 2150    # LLC 정상화 → 전력 감소
```

### 5-5. `04_decision/`

| 파일 | 특이점 |
|------|-------|
| `iss-LLC-thrashing-0221.yaml` | `metadata.status: resolved`, `resolution.fix_sw_ref: sw-vendor-v1.3.0` |
| `waiver-LLC-thrashing.yaml` | `status: approved`, `server_attestation.approved_by_auth: "leesr@company.internal"` (Track 3 채움) |
| `rev-sw123.yaml` | `gate_result: WARN`, `decision: approved_with_waiver`, `waiver_ref: waiver-LLC-thrashing-...` |
| `rev-sw130.yaml` 🆕 | `gate_result: PASS`, `decision: approved`, `waiver_ref: null` |
| `rule-feasibility-check.yaml` | 기존 복사 |
| `rule-known-issue-match.yaml` 🆕 | known_issue_match 룰 (auto_checks 참조용) |

---

## 6. 의존성 추가

```bash
uv add sqlalchemy psycopg2-binary alembic
```

```toml
# pyproject.toml 결과
dependencies = [
    "pydantic>=2.13.2",
    "pyyaml>=6.0.3",
    "sqlalchemy>=2.0",
    "psycopg2-binary>=2.9",
    "alembic>=1.13",
]
```

---

## 7. 검증 순서

```bash
# 1. DB 기동
docker compose up -d
docker compose ps   # postgres: healthy 확인

# 2. 의존성 설치
uv add sqlalchemy psycopg2-binary alembic

# 3. alembic 초기화 + migration
uv run alembic upgrade head
# → 15개 테이블 생성 확인

# 4. demo 시드 데이터 임포트
uv run python -m scenario_db.etl.loader demo/fixtures/
# → 각 kind별 임포트 건수 출력

# 5. pgAdmin 확인 (http://localhost:5050)
# - sw_profiles.feature_flags GIN 인덱스
# - evidence.overall_feasibility 컬럼 값 확인
# - evidence: sw123 → exploration_only, sw130 → production_ready

# 6. 기존 테스트 회귀 없음 확인
uv run pytest tests/ -v
```

---

## 구현 순서 (8단계)

| # | 작업 | 결과물 |
|---|------|-------|
| 1 | `docker-compose.yml` + `.env` | DB 기동 |
| 2 | `uv add` 의존성 | pyproject.toml 업데이트 |
| 3 | `src/scenario_db/db/` ORM 모델 전체 | 4개 모델 파일 |
| 4 | `alembic/` 초기화 + `0001_initial_schema.py` | §22 DDL |
| 5 | `alembic upgrade head` 실행 확인 | 15개 테이블 |
| 6 | `src/scenario_db/etl/` loader + 4개 mapper | ETL 파이프라인 |
| 7 | `demo/fixtures/` 13개 YAML 파일 | 실제 동작 시드 데이터 |
| 8 | ETL 임포트 + pgAdmin 검증 | Demo 완성 |
