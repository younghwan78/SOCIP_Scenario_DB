# Phase 1: DB Foundation - Pattern Map

**Mapped:** 2026-05-06
**Files analyzed:** 9 (8 신규 + 1 수정)
**Analogs found:** 9 / 9

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/scenario_db/etl/validate_loaded.py` | utility (validator) | CRUD (read-only SELECT) | `src/scenario_db/etl/mappers/decision.py` | role-match (ETL layer, session 사용) |
| `src/scenario_db/db/repositories/scenario_graph.py` | repository + DTO | CRUD (multi-table read) | `src/scenario_db/db/repositories/definition.py` | exact (repository, Session 기반 쿼리) |
| `src/scenario_db/db/repositories/view_projection.py` | repository | CRUD (read-only) | `src/scenario_db/db/repositories/evidence.py` | exact (필터 기반 단순 쿼리) |
| `src/scenario_db/etl/loader.py` (수정) | utility (ETL orchestrator) | batch | `src/scenario_db/etl/loader.py` | self (수정 대상) |
| `tests/unit/test_validate_loaded.py` | test | — | `tests/unit/test_decision_models.py` | role-match (unit, Pydantic model 테스트) |
| `tests/integration/test_validate_loaded.py` | test | — | `tests/integration/test_api_definition.py` | role-match (integration, engine fixture 사용) |
| `tests/unit/test_scenario_graph_models.py` | test | — | `tests/unit/test_definition_models.py` | exact (unit, Pydantic round-trip 패턴) |
| `tests/integration/test_scenario_graph.py` | test | — | `tests/integration/test_api_definition.py` | role-match (integration, Session 직접 사용) |
| `tests/integration/test_view_projection.py` | test | — | `tests/integration/test_api_definition.py` | role-match (integration, Session 직접 사용) |

---

## Pattern Assignments

### `src/scenario_db/etl/validate_loaded.py` (utility, CRUD read-only)

**Analog:** `src/scenario_db/etl/mappers/decision.py` (ETL layer, Session + ORM 모델 조합 패턴)

**Imports pattern** (decision.py lines 1-8):
```python
from __future__ import annotations

from sqlalchemy.orm import Session

from scenario_db.db.models.decision import GateRule, Issue, Review, Waiver
from scenario_db.db.models.definition import Project, Scenario, ScenarioVariant
from scenario_db.db.models.capability import IpCatalog
from scenario_db.db.models.evidence import Evidence
```

**신규 모듈 imports (RESEARCH.md Pattern 3 기반):**
```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from sqlalchemy import select

from scenario_db.db.models.capability import IpCatalog
from scenario_db.db.models.decision import GateRule, Issue, Waiver
from scenario_db.db.models.definition import Project, Scenario, ScenarioVariant
from scenario_db.db.models.evidence import Evidence
from scenario_db.db.models.decision import Review
```

**ValidationReport Pydantic 모델 패턴** (RESEARCH.md Pattern 1):
```python
class ValidationReport(BaseModel):
    model_config = ConfigDict(extra='forbid')  # 프로젝트 표준

    errors: list[str] = []
    warnings: list[str] = []

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0
```

**Core validation 패턴 — set 집합 연산** (RESEARCH.md Pattern 3):
```python
def validate_loaded(session: Session) -> ValidationReport:
    errors: list[str] = []
    warnings: list[str] = []

    # Rule 1: project_ids 집합 먼저 수집 → 순회하며 참조 체크
    project_ids = {r[0] for r in session.execute(select(Project.id))}
    for scenario_id, project_ref in session.execute(
        select(Scenario.id, Scenario.project_ref)
    ):
        if project_ref not in project_ids:
            errors.append(
                f"scenario '{scenario_id}': project_ref '{project_ref}' not found in projects"
            )

    return ValidationReport(errors=errors, warnings=warnings)
```

**에러 메시지 포맷 규칙:**
- 패턴: `"<entity_type> '<id>': <field> '<value>' not found in <table>"`
- Warning용: `"<entity_type> '<id>': <field> '<value>' not found"` (약한 제약)

**GateRule validation** (Finding 5 기반):
```python
# Rule 7: trigger.events, condition.match, action.gate_result 키 존재 여부
for rule_id, trigger, condition, action in session.execute(
    select(GateRule.id, GateRule.trigger, GateRule.condition, GateRule.action)
):
    if not trigger or "events" not in trigger:
        errors.append(f"gate_rule '{rule_id}': trigger missing 'events' key")
    if not condition or "match" not in condition:
        errors.append(f"gate_rule '{rule_id}': condition missing 'match' key")
    if not action or "gate_result" not in action:
        errors.append(f"gate_rule '{rule_id}': action missing 'gate_result' key")
```

**Issue affects wildcard 헬퍼** (Finding 3 기반):
```python
def _issue_affects_scenario(affects: list[dict] | None, scenario_id: str) -> bool:
    if not affects:
        return False
    return any(
        entry.get("scenario_ref") in ("*", scenario_id)
        for entry in affects
    )
```

---

### `src/scenario_db/db/repositories/scenario_graph.py` (repository + DTO, multi-table read)

**Analog:** `src/scenario_db/db/repositories/definition.py` (repository, Session.query() 패턴)

**Imports pattern** (definition.py lines 1-7):
```python
from __future__ import annotations

from sqlalchemy.orm import Session

from scenario_db.api.pagination import apply_sort
from scenario_db.db.models.definition import Project, Scenario, ScenarioVariant
```

**신규 모듈 imports (RESEARCH.md Code Examples 기반):**
```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from scenario_db.db.models.capability import IpCatalog, SwProfile
from scenario_db.db.models.decision import Issue, Review, Waiver
from scenario_db.db.models.definition import Project, Scenario, ScenarioVariant
from scenario_db.db.models.evidence import Evidence
```

**Record DTO 패턴** (RESEARCH.md Pattern 5, 6 기반):
```python
# ORM 객체 직접 전달을 위해 from_attributes=True 필수
# metadata_ 필드: ORM Python 속성명(metadata_)과 동일하게 정의
class ScenarioRecord(BaseModel):
    model_config = ConfigDict(extra='forbid', from_attributes=True)
    id: str
    schema_version: str
    project_ref: str
    pipeline: dict
    size_profile: dict | None = None
    design_axes: list | None = None
    yaml_sha256: str
    metadata_: dict  # ORM: Column("metadata", JSONB) → Python attr: metadata_
```

**NotFound 처리 패턴** (definition.py get_variant() 기반):
```python
def get_canonical_graph(
    db: Session,
    scenario_id: str,
    variant_id: str,
) -> CanonicalScenarioGraph | None:
    # ScenarioVariant 복합 PK: (scenario_id, id) — 반드시 두 필드 모두 조건에 포함
    variant = (
        db.query(ScenarioVariant)
        .filter_by(scenario_id=scenario_id, id=variant_id)
        .one_or_none()
    )
    if variant is None:
        return None
    # ...
```

**수동 다중 쿼리 패턴** (RESEARCH.md Pattern 4, Finding 1 기반):
- ORM에 `relationship()` 없음 → `joinedload`/`selectinload` 사용 불가
- 최대 6개 단순 쿼리로 구성 (모두 PK/FK index lookup 또는 소규모 테이블 스캔)
- 기존 `session.query()` 스타일 또는 SQLAlchemy 2.0 `select()` 스타일 일관성 있게 선택

**ORM → Pydantic 변환 패턴** (RESEARCH.md Pattern 5 권장):
```python
# ConfigDict(from_attributes=True) + ORM 객체 직접 전달
# __dict__ 대신 ORM 객체를 model_validate에 직접 전달 → _sa_instance_state 자동 무시
scenario_record = ScenarioRecord.model_validate(scenario_orm_obj)
```

---

### `src/scenario_db/db/repositories/view_projection.py` (repository, read-only)

**Analog:** `src/scenario_db/db/repositories/evidence.py` (단순 필터 기반 쿼리)

**Imports pattern** (evidence.py lines 1-6):
```python
from __future__ import annotations

from sqlalchemy.orm import Session

from scenario_db.api.pagination import apply_sort
from scenario_db.db.models.evidence import Evidence
```

**Core query 패턴** (evidence.py list_evidence() 기반):
```python
def list_evidence(
    db: Session,
    *,
    scenario_ref: str | None = None,
    variant_ref: str | None = None,
    ...
) -> tuple[list[Evidence], int]:
    q = db.query(Evidence)
    if scenario_ref is not None:
        q = q.filter(Evidence.scenario_ref == scenario_ref)
    if variant_ref is not None:
        q = q.filter(Evidence.variant_ref == variant_ref)
    # ...
    return q.offset(offset).limit(limit).all(), total
```

**view_projection 함수 시그니처** (CONTEXT.md D-10, view/service.py project_level0 기반):
```python
def get_view_projection(
    db: Session,
    scenario_id: str,
    variant_id: str,
) -> dict | None:
    """Level 0 lane data 조회 — Phase 3 view router가 소비."""
    ...
```

---

### `src/scenario_db/etl/loader.py` 수정 (lines 98-102)

**현재 코드** (loader.py lines 96-102):
```python
        counts[kind] = success

    session.commit()

    total = sum(counts.values())
    logger.info("ETL complete — %d loaded, %d skipped", total, len(skipped))
    return counts
```

**수정 후** (D-03: commit() 이후 자동 호출, Finding 6: 반환값 변경 없음):
```python
        counts[kind] = success

    session.commit()

    # 신규: semantic validation — commit 이후 DB 상태 검증
    from scenario_db.etl.validate_loaded import validate_loaded
    report = validate_loaded(session)
    if report.errors:
        for err in report.errors:
            logger.warning("Validation: %s", err)
    if report.warnings:
        for warn in report.warnings:
            logger.debug("Validation warning: %s", warn)

    total = sum(counts.values())
    logger.info("ETL complete — %d loaded, %d skipped", total, len(skipped))
    return counts
```

**주의:** `validate_loaded` import는 circular import 방지를 위해 함수 내부 지역 import로 배치.

---

### `tests/unit/test_validate_loaded.py` (unit test)

**Analog:** `tests/unit/test_decision_models.py` (unit, Pydantic 모델 테스트, `fixtures/` 로컬 데이터 사용)

**Imports pattern** (test_decision_models.py lines 1-15):
```python
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from scenario_db.models.decision.common import (...)
```

**Unit test 구조 패턴** (DB 없이 ValidationReport 모델 로직만 테스트):
```python
from __future__ import annotations

import pytest
from scenario_db.etl.validate_loaded import ValidationReport


def test_validation_report_empty_is_valid():
    report = ValidationReport()
    assert report.is_valid is True
    assert report.errors == []
    assert report.warnings == []


def test_validation_report_with_errors_is_invalid():
    report = ValidationReport(errors=["something wrong"])
    assert report.is_valid is False


def test_validation_report_extra_fields_forbidden():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ValidationReport(errors=[], unexpected_field="oops")
```

---

### `tests/integration/test_validate_loaded.py` (integration test)

**Analog:** `tests/integration/test_api_definition.py` (integration, `pytestmark`, `api_client` 또는 `engine` fixture 사용)

**Imports + marker pattern** (test_api_definition.py lines 1-7):
```python
"""Definition 레이어 API — 실 DB 검증."""
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

SCENARIO_ID = "uc-camera-recording"
VARIANT_ID = "UHD60-HDR10-H265"
```

**Integration test 구조 패턴** (conftest.py의 `engine` fixture 재활용):
```python
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session
from scenario_db.etl.validate_loaded import validate_loaded

pytestmark = pytest.mark.integration

SCENARIO_ID = "uc-camera-recording"
VARIANT_ID = "UHD60-HDR10-H265"


def test_validate_loaded_no_errors(engine):
    """demo fixtures 로드 후 semantic validation 오류 없음."""
    with Session(engine) as session:
        report = validate_loaded(session)
    assert report.errors == [], f"Validation errors: {report.errors}"
```

**주의:** `engine` fixture는 `tests/integration/conftest.py`에서 session-scoped로 제공됨.  
ETL 로드 + migration 이미 완료된 상태. `Session(engine)` 으로 직접 연결.

---

### `tests/unit/test_scenario_graph_models.py` (unit test)

**Analog:** `tests/unit/test_definition_models.py` (unit, Pydantic round-trip 패턴, `roundtrip()` 헬퍼)

**round-trip helper 패턴** (test_definition_models.py lines 35-45):
```python
def roundtrip(model_cls, path: Path, **dump_kwargs):
    raw = load_yaml(path)
    obj = model_cls.model_validate(raw)
    serialised = obj.model_dump(exclude_none=True, **dump_kwargs)
    obj2 = model_cls.model_validate(serialised)
    assert obj == obj2
    return obj
```

**Pydantic model 단위 테스트 패턴:**
```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from scenario_db.db.repositories.scenario_graph import (
    CanonicalScenarioGraph,
    ScenarioRecord,
    VariantRecord,
)


def test_scenario_record_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        ScenarioRecord.model_validate({"id": "x", "unexpected": "oops"})


def test_canonical_graph_construct():
    """최소 필수 필드로 CanonicalScenarioGraph 생성."""
    graph = CanonicalScenarioGraph(
        scenario_id="uc-camera-recording",
        variant_id="UHD60-HDR10-H265",
        scenario=ScenarioRecord(...),
        variant=VariantRecord(...),
        ...
    )
    assert graph.scenario_id == "uc-camera-recording"
```

---

### `tests/integration/test_scenario_graph.py` + `tests/integration/test_view_projection.py`

**Analog:** `tests/integration/test_api_definition.py` (동일 패턴)

**Integration test 구조** (RESEARCH.md Code Examples 기반):
```python
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session
from scenario_db.db.repositories.scenario_graph import get_canonical_graph

pytestmark = pytest.mark.integration

SCENARIO_ID = "uc-camera-recording"
VARIANT_ID = "UHD60-HDR10-H265"


def test_canonical_graph_demo_scenario(engine):
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, VARIANT_ID)
    assert graph is not None
    assert graph.scenario_id == SCENARIO_ID
    assert graph.variant_id == VARIANT_ID
    assert graph.project is not None


def test_canonical_graph_not_found(engine):
    with Session(engine) as session:
        graph = get_canonical_graph(session, "no-such-scenario", "no-variant")
    assert graph is None
```

---

## Shared Patterns

### 프로젝트 표준: Pydantic model_config

**Source:** 전체 코드베이스 (`test_definition_models.py`, `test_decision_models.py`, CLAUDE.md)
**Apply to:** `ValidationReport`, 모든 `*Record` DTO 클래스

```python
from pydantic import BaseModel, ConfigDict

class AnyModel(BaseModel):
    model_config = ConfigDict(extra='forbid')  # 기본
    # ORM 객체에서 직접 생성하는 Record DTO는:
    # model_config = ConfigDict(extra='forbid', from_attributes=True)
```

### ORM Query 패턴 — session.query() 스타일

**Source:** `src/scenario_db/db/repositories/definition.py` (lines 18-24, 40-41, 59-64)
**Apply to:** `scenario_graph.py`, `view_projection.py`

```python
# 단일 PK 조회
def get_project(db: Session, project_id: str) -> Project | None:
    return db.query(Project).filter_by(id=project_id).one_or_none()

# 복합 PK 조회 — ScenarioVariant
def get_variant(db: Session, scenario_id: str, variant_id: str) -> ScenarioVariant | None:
    return (
        db.query(ScenarioVariant)
        .filter_by(scenario_id=scenario_id, id=variant_id)
        .one_or_none()
    )

# 필터 기반 목록 조회
def list_evidence(db: Session, *, scenario_ref: str | None = None, ...) -> tuple[list, int]:
    q = db.query(Evidence)
    if scenario_ref is not None:
        q = q.filter(Evidence.scenario_ref == scenario_ref)
    return q.all(), q.count()
```

### ORM Column alias 처리

**Source:** `src/scenario_db/db/models/definition.py` (line 14), `src/scenario_db/db/models/decision.py` (line 16)
**Apply to:** `ScenarioRecord`, `ProjectRecord` 등 모든 Record DTO

```python
# ORM 정의: metadata_ = Column("metadata", JSONB)
# Python attr명: metadata_ (DB column명: "metadata")
# Pydantic에서: from_attributes=True + 필드명 metadata_ 로 정의
class ProjectRecord(BaseModel):
    model_config = ConfigDict(extra='forbid', from_attributes=True)
    id: str
    metadata_: dict   # ORM python attr명과 동일 — DB column alias 포함

# 동일 패턴: globals_ (Project), validation_ (Review)
```

### ETL Layer import 패턴

**Source:** `src/scenario_db/etl/loader.py` (lines 1-27), `src/scenario_db/etl/mappers/decision.py` (lines 1-9)
**Apply to:** `validate_loaded.py`

```python
from __future__ import annotations
import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
```

### Integration test fixture 접근

**Source:** `tests/integration/conftest.py` (lines 31-65)
**Apply to:** 모든 `tests/integration/test_*.py` 신규 파일

- `engine` fixture: session-scoped PostgreSQL (testcontainers), ETL 완료 상태
- `api_client` fixture: FastAPI TestClient (session-scoped)
- 신규 테스트가 Session 직접 사용 시: `engine` fixture만 의존, `api_client` 불필요
- `Session(engine)` 컨텍스트 매니저로 사용

```python
# conftest.py에서 이미 ETL 로드 완료:
# with Session(eng) as session:
#     counts = load_yaml_dir(DEMO_FIXTURES, session)
```

---

## Critical Anti-Patterns (피해야 할 패턴)

| Anti-Pattern | 이유 | 대안 |
|-------------|------|------|
| `joinedload(Scenario.variants)` | ORM에 `relationship()` 없음 → `AttributeError` | `db.query(ScenarioVariant).filter_by(scenario_id=x)` |
| `model_validate(row.__dict__)` with `extra='forbid'` | `_sa_instance_state` 키 → `ValidationError` | `ConfigDict(from_attributes=True)` + `model_validate(orm_obj)` |
| `session.get(ScenarioVariant, variant_id)` | 복합 PK `(scenario_id, id)` → 단일 키로 조회 불가 | `filter_by(scenario_id=x, id=y).one_or_none()` |
| `validate_loaded()` 를 `session.commit()` 이전 호출 | uncommitted 데이터 미반영 → false negative | 반드시 `commit()` 이후 호출 |
| `Issue.affects JSONB SQL 필터` | 인덱스 없음, 소규모 fixture에서 불필요한 복잡성 | Python-level `_issue_affects_scenario()` 헬퍼 |

---

## No Analog Found

없음 — 모든 파일에 대해 역할/데이터 흐름 기준 적합한 analog 발견됨.

---

## Metadata

**Analog search scope:** `src/scenario_db/etl/`, `src/scenario_db/db/repositories/`, `tests/unit/`, `tests/integration/`
**Files scanned:** 12
**Pattern extraction date:** 2026-05-06

**Key ORM facts (RESEARCH.md Finding 1 검증):**
- `Scenario`, `ScenarioVariant`, `Evidence`, `Issue`, `Waiver`, `Review`: `relationship()` 선언 없음
- `ScenarioVariant`: 복합 PK `(scenario_id, id)`
- `metadata_`, `globals_`, `validation_`: Python alias 컬럼 (DB column명과 다름)
- `Evidence.sw_version_hint`, `sweep_value_hint`: Computed column — DTO에서 `Optional` 처리 필요
