# Phase 1: DB Foundation - Research

**Researched:** 2026-05-06
**Domain:** SQLAlchemy ORM 쿼리 패턴 / Pydantic v2 DTO / ETL post-load validation
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**ETL Semantic Validation (DB-01)**
- D-01: Soft validation — 오류 목록 수집 후 리포트, DB 상태 유지
- D-02: `validate_loaded(session) -> ValidationReport` 반환 — `ValidationReport(errors: list[str], warnings: list[str])`
- D-03: `load_yaml_dir()` 내부 ETL 완료 후 자동 호출
- D-04: Validation 범위 (8가지 FK-like 규칙):
  1. `scenario.project_ref` → `projects.id` 존재 여부
  2. `scenario_variant.scenario_id` → `scenarios.id` 존재 여부
  3. `evidence.scenario_ref` + `evidence.variant_ref` → 대상 존재 여부
  4. `review.scenario_ref` + `review.variant_ref` + `review.evidence_refs` + `review.waiver_ref` 존재 여부
  5. `issue.affects[*].scenario_ref` → `*` wildcard 또는 존재하는 scenario_id
  6. `waiver.issue_ref` → `issues.id` 존재 여부
  7. `gate_rule` trigger/condition/action 형식 유효성
  8. `scenario.pipeline` 노드 ip_ref → `ip_catalog.id` 존재 여부

**CanonicalScenarioGraph DTO (DB-02)**
- D-05: `model_config = ConfigDict(extra='forbid')` 프로젝트 표준
- D-06: 위치 `src/scenario_db/db/repositories/scenario_graph.py` — DTO + 서비스 함께
- D-07: `model_validate(row.__dict__)` 패턴, 불일치 필드는 명시적 alias
- D-08: joinedload/selectinload N+1 방지, 단일 또는 최대 2번 쿼리
- D-09: 필드 구성 (docs §4.5):
  ```python
  class CanonicalScenarioGraph(BaseModel):
      scenario_id: str
      variant_id: str
      scenario: ScenarioRecord
      variant: VariantRecord
      project: ProjectRecord | None
      pipeline: dict
      ip_catalog: dict[str, IpRecord]
      sw_profiles: dict[str, SwProfileRecord]
      evidence: list[EvidenceRecord]
      issues: list[IssueRecord]
      waivers: list[WaiverRecord]
      reviews: list[ReviewRecord]
  ```

**Repository 확장 (DB-03)**
- D-10: `db/repositories/view_projection.py` 신규 — view_projection 쿼리
- D-11: `db/repositories/scenario_graph.py` 신규 — `get_canonical_graph(db, scenario_id, variant_id) -> CanonicalScenarioGraph | None`
- D-12: 기존 `db/repositories/definition.py` 수정 없이 유지

### Claude's Discretion
- CanonicalScenarioGraph 내부 Record 타입 네이밍
- Issues 스코핑: `issue.affects[*].scenario_ref == scenario_id` 또는 `"*"` wildcard 필터
- Waivers 스코핑: 선택된 issues의 issue_ref + scope에 해당 scenario/variant 포함 waivers
- ValidationReport 에러 메시지 포맷

### Deferred Ideas (OUT OF SCOPE)
- Issues/Waivers 스코핑 세부 로직 논의 생략 — Claude 재량 구현
- Validation CLI 통합 — Phase 1 이후 필요 시
- gate_executions 영속 테이블 — runtime 비영속 결정 유지
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DB-01 | ETL post-load semantic validation — FK-like 참조 무결성 8가지 규칙 검증 | `validate_loaded(session)` 모듈 신규 생성, `load_yaml_dir()` 반환값 또는 부수 호출로 통합 |
| DB-02 | CanonicalScenarioGraph builder — scenario + variant + project + evidence/issues/waivers/reviews 단일 DTO | `scenario_graph.py` 신규 레포지토리, N+1 없는 수동 다중 쿼리 전략 |
| DB-03 | Repository 확장 — view_projection, scenario_graph 쿼리 캡슐화 | `view_projection.py` + `scenario_graph.py` 신규, 기존 패턴 유지 |
</phase_requirements>

---

## Summary

Phase 1은 기존 ETL+ORM 기반(FastAPI 33 endpoints, 209 tests)에 **두 가지 신규 레이어**를 추가하는 작업이다. 첫째, ETL 완료 후 DB 상태를 의미론적으로 검증하는 `validate_loaded()` 모듈 — 8가지 FK-like 참조 무결성 규칙을 소프트하게 체크하고 `ValidationReport`를 반환한다. 둘째, `CanonicalScenarioGraph` Pydantic DTO와 이를 단일/2번 쿼리로 로드하는 `get_canonical_graph()` 서비스 — Phase 2~4 전체의 공통 입력 계약이다.

**핵심 발견:** ORM 모델에 `relationship()` 선언이 없다(`[VERIFIED: codebase grep]`). `joinedload`/`selectinload`는 relationship 없이 동작하지 않으므로, N+1 방지 전략은 **수동 다중 쿼리** (Query 1: Scenario+Variant+Project join, Query 2: Evidence+Issues+Waivers+Reviews 일괄 조회) 패턴으로 구현해야 한다.

**FHD30-SDR-H265 fixture 부재:** CONTEXT.md acceptance criteria에 `FHD30-SDR-H265`가 언급되나 demo/fixtures에는 없고(`[VERIFIED: grep]`), 실제 fixture에는 `UHD60-HDR10-H265`가 존재한다. 테스트는 `UHD60-HDR10-H265`로 작성하되, `FHD30-SDR-H265` fixture 추가는 Wave 0 갭으로 처리한다.

**Primary recommendation:** ORM relationship 없이 수동 join+다중 IN 쿼리로 `CanonicalScenarioGraph`를 구성한다. `validate_loaded()`는 `load_yaml_dir()` 내 `session.commit()` 직전에 삽입하여 D-03을 만족시킨다.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| ETL semantic validation | DB / ETL | — | YAML 로드 완료 후 DB 상태 검증 — DB layer 책임 |
| CanonicalScenarioGraph 조회 | DB / Repository | — | 서비스 레이어에 ORM 직접 노출 금지 — repository 캡슐화 |
| ValidationReport Pydantic 모델 | DB / ETL | — | DTO — Phase 3 API가 소비하나 정의는 ETL layer |
| view_projection 쿼리 | DB / Repository | — | Phase 3 view router가 소비, repository가 쿼리 소유 |
| FHD30-SDR-H265 fixture | ETL / Fixtures | — | Wave 0 에서 demo fixture 추가 필요 |

---

## Standard Stack

### Core (이미 설치됨)

[VERIFIED: uv run python --version / import check]

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.11.15 | 런타임 | 프로젝트 표준 |
| SQLAlchemy | 2.0.49 | ORM + 쿼리 | 기존 전체 코드베이스 |
| Pydantic | 2.13.2 | DTO 정의 | 프로젝트 표준 (`extra='forbid'`) |
| PostgreSQL (Docker) | 16-alpine | 통합 테스트 DB | testcontainers로 자동 기동 |
| testcontainers | 설치됨 | integration test 격리 | 기존 conftest.py 패턴 |
| pytest | 설치됨 | 테스트 | 프로젝트 표준 |

### 신규 모듈 (이번 Phase에서 생성)

| 파일 | 역할 |
|------|------|
| `src/scenario_db/etl/validate_loaded.py` | `validate_loaded(session) -> ValidationReport` |
| `src/scenario_db/db/repositories/scenario_graph.py` | `CanonicalScenarioGraph` DTO + `get_canonical_graph()` |
| `src/scenario_db/db/repositories/view_projection.py` | `view_projection` 쿼리 캡슐화 |

**Installation:** 신규 패키지 설치 불필요 — 기존 의존성만 사용.

---

## Architecture Patterns

### System Architecture Diagram

```
YAML fixtures (demo/fixtures/)
       |
       v
load_yaml_dir(directory, session)          [etl/loader.py]
  |-- SAVEPOINT per file (기존 패턴)
  |-- session.commit()
  |-- validate_loaded(session)  ← 신규 삽입 지점
         |
         v
     ValidationReport(errors, warnings)
         |
         +-- errors → logger.warning() + return
         +-- errors==[] → Phase 완료

                    DB (PostgreSQL)
                         |
                         v
           get_canonical_graph(db, scenario_id, variant_id)
           [db/repositories/scenario_graph.py]
                |
                |-- Query 1: Scenario JOIN Project (LEFT OUTER)
                |            + ScenarioVariant (WHERE scenario_id+id)
                |-- Query 2a: Evidence (WHERE scenario_ref + variant_ref)
                |-- Query 2b: Issues (WHERE affects JSONB contains scenario_id or '*')
                |-- Query 2c: Waivers (IN matched issue_refs)
                |-- Query 2d: Reviews (WHERE scenario_ref + variant_ref)
                |-- ip_catalog IDs from pipeline nodes → IN query
                |-- sw_profiles IDs from sw_requirements → IN query
                |
                v
         CanonicalScenarioGraph (Pydantic DTO)
                |
         (Phase 2: Resolver input)
         (Phase 3: API /graph endpoint)
         (Phase 4: Viewer DB-backed projection)
```

### Recommended Project Structure

```
src/scenario_db/
├── etl/
│   ├── loader.py          # 기존 — validate_loaded() 호출 추가
│   ├── validate_loaded.py # 신규 — ValidationReport + 8가지 검증
│   └── mappers/           # 기존 — 수정 없음
├── db/
│   ├── models/            # 기존 — 수정 없음
│   └── repositories/
│       ├── definition.py  # 기존 — 수정 없음
│       ├── evidence.py    # 기존 — 수정 없음
│       ├── decision.py    # 기존 — 수정 없음
│       ├── capability.py  # 기존 — 수정 없음
│       ├── scenario_graph.py  # 신규
│       └── view_projection.py # 신규
└── view/
    └── service.py         # 기존 — Phase 4에서 DB 연동 (Phase 1 수정 없음)
tests/
└── integration/
    ├── conftest.py        # 기존 — 수정 없음
    ├── test_validate_loaded.py  # 신규
    └── test_scenario_graph.py   # 신규
```

### Pattern 1: ValidationReport Pydantic 모델

**What:** ETL 완료 후 DB 상태 검증 결과를 구조화된 DTO로 반환  
**When to use:** `load_yaml_dir()` 완료 시 자동 호출 (D-03)

```python
# Source: CONTEXT.md D-02 + 프로젝트 표준 model_config
from pydantic import BaseModel, ConfigDict

class ValidationReport(BaseModel):
    model_config = ConfigDict(extra='forbid')

    errors: list[str] = []
    warnings: list[str] = []

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0
```

### Pattern 2: load_yaml_dir() 통합 지점

**What:** 기존 `session.commit()` 이후에 `validate_loaded()` 호출 삽입  
**When to use:** D-03 — 별도 CLI 없이 ETL 실행 시 항상 실행

```python
# Source: etl/loader.py load_yaml_dir() 현재 구조 분석 [VERIFIED]
def load_yaml_dir(directory: Path, session: Session) -> dict[str, int]:
    # ... 기존 로직 ...
    session.commit()  # ← 이 라인 존재 (line 98)

    # 신규 추가 — commit 후 validation
    from scenario_db.etl.validate_loaded import validate_loaded
    report = validate_loaded(session)
    if report.errors:
        for err in report.errors:
            logger.warning("Validation: %s", err)
    
    total = sum(counts.values())
    logger.info("ETL complete — %d loaded, %d skipped", total, len(skipped))
    return counts
```

### Pattern 3: validate_loaded() 8가지 규칙 구현

**What:** DB 상태를 쿼리하여 FK-like 참조 무결성 검증  
**핵심 패턴:** `session.query(Model.id)` → Python set으로 집합 연산

```python
# Source: ORM 모델 분석 [VERIFIED] + docs §4.4 [CITED]
from sqlalchemy.orm import Session
from sqlalchemy import select

def validate_loaded(session: Session) -> ValidationReport:
    errors: list[str] = []
    warnings: list[str] = []

    # Rule 1: scenario.project_ref → projects.id
    project_ids = {r[0] for r in session.execute(
        select(Project.id)
    )}
    for scenario_id, project_ref in session.execute(
        select(Scenario.id, Scenario.project_ref)
    ):
        if project_ref not in project_ids:
            errors.append(
                f"scenario '{scenario_id}': project_ref '{project_ref}' not found in projects"
            )

    # Rule 2: scenario_variant.scenario_id → scenarios.id
    scenario_ids = {r[0] for r in session.execute(select(Scenario.id))}
    for sv_scenario_id, sv_id in session.execute(
        select(ScenarioVariant.scenario_id, ScenarioVariant.id)
    ):
        if sv_scenario_id not in scenario_ids:
            errors.append(
                f"variant '{sv_id}': scenario_id '{sv_scenario_id}' not found in scenarios"
            )

    # Rule 5: issue.affects[*].scenario_ref → '*' 또는 존재하는 scenario_id
    # JSONB affects는 list[{scenario_ref, match_rule}] 구조 [VERIFIED: fixture 분석]
    for issue_id, affects in session.execute(
        select(Issue.id, Issue.affects)
    ):
        if affects:
            for entry in affects:
                ref = entry.get("scenario_ref", "")
                if ref != "*" and ref not in scenario_ids:
                    warnings.append(
                        f"issue '{issue_id}': affects.scenario_ref '{ref}' not found"
                    )

    # Rule 6: waiver.issue_ref → issues.id
    issue_ids = {r[0] for r in session.execute(select(Issue.id))}
    for waiver_id, issue_ref in session.execute(
        select(Waiver.id, Waiver.issue_ref)
    ):
        if issue_ref and issue_ref not in issue_ids:
            errors.append(
                f"waiver '{waiver_id}': issue_ref '{issue_ref}' not found in issues"
            )

    # Rule 7: gate_rule trigger/condition/action 필수 키 존재
    for rule_id, trigger, condition, action in session.execute(
        select(GateRule.id, GateRule.trigger, GateRule.condition, GateRule.action)
    ):
        if not trigger or "events" not in trigger:
            errors.append(f"gate_rule '{rule_id}': trigger missing 'events' key")
        if not condition or "match" not in condition:
            errors.append(f"gate_rule '{rule_id}': condition missing 'match' key")
        if not action or "gate_result" not in action:
            errors.append(f"gate_rule '{rule_id}': action missing 'gate_result' key")

    # Rule 8: scenario.pipeline 노드 ip_ref → ip_catalog.id
    ip_ids = {r[0] for r in session.execute(select(IpCatalog.id))}
    for scen_id, pipeline in session.execute(
        select(Scenario.id, Scenario.pipeline)
    ):
        for node in (pipeline or {}).get("nodes", []):
            ip_ref = node.get("ip_ref")
            if ip_ref and ip_ref not in ip_ids:
                errors.append(
                    f"scenario '{scen_id}': pipeline node ip_ref '{ip_ref}' not in ip_catalog"
                )

    return ValidationReport(errors=errors, warnings=warnings)
```

### Pattern 4: get_canonical_graph() — N+1 없는 수동 다중 쿼리

**핵심 발견:** ORM 모델에 `relationship()` 없음 `[VERIFIED: sa_inspect()]`  
→ `joinedload`/`selectinload` 사용 불가  
→ 수동 JOIN + 순차 IN 쿼리로 최대 2-3 round trip

```python
# Source: ORM 모델 분석 [VERIFIED] + SQLAlchemy 2.0 패턴 [VERIFIED: import OK]
from sqlalchemy import select
from sqlalchemy.orm import Session

def get_canonical_graph(
    db: Session,
    scenario_id: str,
    variant_id: str,
) -> CanonicalScenarioGraph | None:
    # Query 1: Scenario + Project (LEFT OUTER JOIN) + ScenarioVariant
    scenario_row = db.execute(
        select(Scenario, Project)
        .join(Project, Scenario.project_ref == Project.id, isouter=True)
        .where(Scenario.id == scenario_id)
    ).first()
    if scenario_row is None:
        return None

    scenario, project = scenario_row
    variant = db.execute(
        select(ScenarioVariant)
        .where(
            ScenarioVariant.scenario_id == scenario_id,
            ScenarioVariant.id == variant_id,
        )
    ).scalar_one_or_none()
    if variant is None:
        return None

    # Query 2a: Evidence (scenario_ref + variant_ref 필터)
    evidence_rows = db.execute(
        select(Evidence).where(
            Evidence.scenario_ref == scenario_id,
            Evidence.variant_ref == variant_id,
        )
    ).scalars().all()

    # Query 2b: Issues (affects JSONB에서 scenario_id 또는 '*' 포함)
    # PostgreSQL JSONB @> 연산자: affects에 {scenario_ref: scenario_id} 항목 포함 여부
    # 또는 Python-level 필터 (소규모이므로 전체 로드 후 필터)
    all_issues = db.execute(select(Issue)).scalars().all()
    issues = [
        iss for iss in all_issues
        if _issue_affects_scenario(iss.affects, scenario_id)
    ]

    # Query 2c: Waivers (matched issue_refs + scope에 scenario 포함)
    matched_issue_ids = {iss.id for iss in issues}
    waivers = db.execute(
        select(Waiver).where(Waiver.issue_ref.in_(matched_issue_ids))
    ).scalars().all() if matched_issue_ids else []

    # Query 2d: Reviews (scenario_ref + variant_ref)
    reviews = db.execute(
        select(Review).where(
            Review.scenario_ref == scenario_id,
            Review.variant_ref == variant_id,
        )
    ).scalars().all()

    # Query 3: IP Catalog (pipeline 노드 ip_ref 목록)
    pipeline_ip_refs = {
        node["ip_ref"]
        for node in (scenario.pipeline or {}).get("nodes", [])
        if "ip_ref" in node
    }
    ip_catalog_rows = db.execute(
        select(IpCatalog).where(IpCatalog.id.in_(pipeline_ip_refs))
    ).scalars().all() if pipeline_ip_refs else []

    # DTO 조립
    return CanonicalScenarioGraph(
        scenario_id=scenario_id,
        variant_id=variant_id,
        scenario=ScenarioRecord.model_validate(scenario.__dict__),
        variant=VariantRecord.model_validate(variant.__dict__),
        project=ProjectRecord.model_validate(project.__dict__) if project else None,
        pipeline=scenario.pipeline or {},
        ip_catalog={ip.id: IpRecord.model_validate(ip.__dict__) for ip in ip_catalog_rows},
        sw_profiles={},  # sw_requirements 기반 조회 — Wave 1에서 구체화
        evidence=[EvidenceRecord.model_validate(e.__dict__) for e in evidence_rows],
        issues=[IssueRecord.model_validate(i.__dict__) for i in issues],
        waivers=[WaiverRecord.model_validate(w.__dict__) for w in waivers],
        reviews=[ReviewRecord.model_validate(r.__dict__) for r in reviews],
    )
```

### Pattern 5: ORM.__dict__ → Pydantic model_validate 매핑 주의사항

**What:** `row.__dict__`에는 `_sa_instance_state` 키가 포함됨  
**How to avoid:** Pydantic `ConfigDict(extra='forbid')` 사용 시 `_sa_instance_state` 가 오류 발생 → `exclude_private=True` 또는 수동 필드 매핑 필요

```python
# Source: Pydantic v2 문서 + 프로젝트 패턴 분석 [ASSUMED — 검증 필요]
# 방법 A: model_validate에서 _ prefix 필드 제외
data = {k: v for k, v in row.__dict__.items() if not k.startswith('_')}
record = ScenarioRecord.model_validate(data)

# 방법 B: from_orm (Pydantic v2는 model_validate(obj) 사용)
# model_config에 from_attributes=True 필요
class ScenarioRecord(BaseModel):
    model_config = ConfigDict(extra='forbid', from_attributes=True)
```

**권장:** `model_config = ConfigDict(extra='forbid', from_attributes=True)`로 설정하고 `model_validate(orm_obj)` 패턴 사용. `__dict__` 대신 ORM 객체 직접 전달.

### Pattern 6: ORM Column alias 처리

**What:** `metadata_` (Python) ↔ `"metadata"` (DB), `globals_` ↔ `"globals"` 등 alias 존재  
**How:** ORM 객체 속성 접근은 Python 이름(`metadata_`)으로, Pydantic 필드는 `Field(alias="metadata")` 또는 ORM 이름과 동일하게 설정

```python
# Source: ORM 모델 코드 직접 확인 [VERIFIED]
# Project ORM: metadata_ = Column("metadata", JSONB)
# Pydantic Record에서:
class ProjectRecord(BaseModel):
    model_config = ConfigDict(extra='forbid', from_attributes=True)
    id: str
    metadata_: dict = Field(alias="metadata_")  # ORM Python attr명과 일치
    # 또는 별도 validator로 처리
```

### Anti-Patterns to Avoid

- **joinedload/selectinload 사용 시도:** ORM relationship 없음 → AttributeError 발생. 수동 join 또는 다중 쿼리로 대체
- **row.__dict__ 직접 model_validate에 전달:** `_sa_instance_state` 포함으로 `extra='forbid'` 위반. `from_attributes=True` + ORM 객체 직접 전달 패턴 사용
- **metadata 필드명 충돌:** Python 예약 패턴 아니지만 Pydantic 내부와 충돌 가능. `metadata_` alias 처리 필수
- **Issue.affects JSONB 전체 in-DB 필터:** `affects @> '[{"scenario_ref": "X"}]'` JSONB 쿼리는 인덱스 없이 느림. 소규모 fixture에서는 Python-level 필터가 더 단순하고 안전함

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| FK-like 참조 무결성 | DB 레벨 FK trigger | Python validate_loaded() soft check | YAML 스키마가 FK 없는 설계. DB trigger는 ETL LOAD ORDER 위반 위험 |
| N+1 쿼리 방지 | ORM relationship 신규 추가 | 수동 JOIN + IN 쿼리 | relationship 추가는 기존 ORM 전체에 영향, 과잉 변경 |
| JSONB affects 필터링 | 복잡한 JSONB SQL 쿼리 | Python-level 필터 (소규모) | 현재 fixture는 소규모, SQL 복잡성 대비 이득 없음 |
| DTO 직렬화 | 수동 dict 변환 | `model_validate(orm_obj)` with `from_attributes=True` | Pydantic v2 공식 ORM 통합 패턴 |

**Key insight:** ORM relationship 없이도 수동 쿼리 조합으로 N+1을 방지할 수 있다. Issue 스코핑 (wildcard `*` 처리)은 JSONB SQL보다 Python 필터가 더 명확하고 테스트하기 쉽다.

---

## Critical Findings

### Finding 1: ORM relationship 부재 — joinedload 불가

[VERIFIED: `sa_inspect()` 실행]

모든 ORM 모델(`Scenario`, `ScenarioVariant`, `Review`, `Issue`, `Waiver`, `Evidence`)에 `relationship()` 선언이 없다. SQLAlchemy의 `joinedload`/`selectinload`는 relationship이 있어야 동작한다.

**영향:** D-08 "joinedload/selectinload 적극 활용"은 현재 코드베이스에서 직접 적용 불가. 대신 수동 JOIN 쿼리와 순차 IN 쿼리 (최대 2-3 round trip) 패턴으로 동등한 효과 달성.

**권장 쿼리 구조:**
- Round 1: `SELECT scenarios, projects JOIN + WHERE scenarios.id = ?`
- Round 1b: `SELECT scenario_variants WHERE scenario_id=? AND id=?`
- Round 2: `SELECT evidence, reviews WHERE scenario_ref=? AND variant_ref=?` (2개 별도 쿼리)
- Round 3: `SELECT issues` (전체 로드 후 Python 필터) + `SELECT waivers WHERE issue_ref IN (?)`
- Round 4: `SELECT ip_catalog WHERE id IN (?)`

총 6개 쿼리지만 모두 단순 index lookup 또는 소규모 테이블 스캔이므로 성능 문제 없음.

### Finding 2: FHD30-SDR-H265 fixture 미존재

[VERIFIED: `grep -r "FHD30"` 실행]

CONTEXT.md acceptance criteria와 `docs/implementation-roadmap-etl-resolver-api-viewer.md §4.6`에 `FHD30-SDR-H265`가 언급되나, `demo/fixtures/02_definition/uc-camera-recording.yaml`의 실제 variants는 `UHD60-HDR10-H265`, `8K120-HDR10plus-AV1-exploration`, `UHD60-HDR10-sustained-10min`이다. `FHD30-SDR-H265`는 `src/scenario_db/view/service.py`에서 hardcoded sample 용도로만 사용됨.

**영향:** 테스트는 실존하는 `UHD60-HDR10-H265`로 작성. Wave 0에서 `FHD30-SDR-H265` fixture 추가 또는 acceptance criteria 수정 결정 필요.

### Finding 3: Issue.affects JSONB 구조

[VERIFIED: fixture 파싱]

`Issue.affects`는 `list[{scenario_ref: str, match_rule: dict}]` 구조. `scenario_ref`는 구체적인 ID 또는 `"*"` wildcard. `_issue_affects_scenario(affects, scenario_id)` 헬퍼 구현 시:

```python
def _issue_affects_scenario(affects: list[dict] | None, scenario_id: str) -> bool:
    if not affects:
        return False
    return any(
        entry.get("scenario_ref") in ("*", scenario_id)
        for entry in affects
    )
```

### Finding 4: Waiver.scope JSONB 구조

[VERIFIED: fixture 파싱]

`Waiver.scope`는 `{variant_scope: {scenario_ref, match_rule}, execution_scope: {all: [...]}}` 구조. 단순 `issue_ref` 매칭만으로 waivers를 연결하는 것이 Phase 1의 범위이며, 정교한 match_rule 평가는 Phase 2 Resolver의 영역이다.

### Finding 5: GateRule validation 형식

[VERIFIED: fixture 파싱]

GateRule의 최소 유효성 기준:
- `trigger.events`: list 필수 (예: `["on_evidence_register"]`)
- `condition.match`: dict 필수
- `action.gate_result`: str 필수 (`"BLOCK"`, `"WARN"` 등)

Rule 7 구현 시 이 3개 키 존재 여부만 검증하면 충분.

### Finding 6: load_yaml_dir() 반환값 변경 불필요

[VERIFIED: loader.py 분석]

현재 `load_yaml_dir()` 반환값은 `dict[str, int]` (kind별 성공 건수). D-03에 따라 `validate_loaded()`는 자동 호출되고 `logger.warning()`으로 출력. 반환값 변경 없이 `load_yaml_dir()` 내부에서 부수효과로 처리 가능 — 기존 호출자 (integration tests, CLI main) 영향 없음.

---

## Common Pitfalls

### Pitfall 1: _sa_instance_state 필드 충돌

**What goes wrong:** `model_validate(row.__dict__)` 호출 시 `ConfigDict(extra='forbid')` 설정된 Pydantic 모델이 `_sa_instance_state` 키를 거부하여 `ValidationError` 발생
**Why it happens:** SQLAlchemy ORM 객체의 `__dict__`에는 인스턴스 상태 추적용 내부 키가 포함됨
**How to avoid:** `ConfigDict(from_attributes=True)` 설정 + ORM 객체 직접 전달 (`model_validate(orm_obj)`)
**Warning signs:** `ValidationError: extra fields not permitted` 오류

### Pitfall 2: metadata_ vs metadata 필드명

**What goes wrong:** ORM에서 `metadata_` (Python) / `"metadata"` (DB column)로 alias된 컬럼이 Pydantic DTO에서 잘못 매핑됨
**Why it happens:** `from_attributes=True` 사용 시 Python 속성명 (`metadata_`)으로 접근
**How to avoid:** Pydantic Record 모델에서 필드명을 `metadata_`로 정의하거나 `Field(alias="metadata")` 사용
**Warning signs:** `AttributeError: 'Project' object has no attribute 'metadata'`

### Pitfall 3: ScenarioVariant 복합 PK 순서

**What goes wrong:** `session.get(ScenarioVariant, variant_id)` 단일 키로 조회 시 not found
**Why it happens:** `scenario_variants` 테이블은 복합 PK `(scenario_id, id)` — `[VERIFIED: ORM 모델]`
**How to avoid:** 항상 `filter_by(scenario_id=scenario_id, id=variant_id)` 또는 `select().where(...AND...)` 패턴 사용
**Warning signs:** None returned when record visually exists in DB

### Pitfall 4: validate_loaded()를 commit() 이전에 호출

**What goes wrong:** commit 전에 validate하면 이번 ETL 배치의 변경사항이 반영되지 않아 false negative
**Why it happens:** SAVEPOINT+flush만으로는 query가 uncommitted data를 볼 수 있지만, 다른 session에서는 불가
**How to avoid:** `session.commit()` 이후에 `validate_loaded(session)` 호출
**Warning signs:** validate_loaded()가 항상 오류 0건 반환

### Pitfall 5: Issue.affects가 None인 경우

**What goes wrong:** fixture에 `affects: null` 또는 `affects: []`인 issue가 있으면 `None.iter()` 에러
**Why it happens:** JSONB 컬럼 nullable — ORM 정의에 `nullable=True` 암묵적
**How to avoid:** `_issue_affects_scenario()` 헬퍼에서 `if not affects: return False` 방어 처리

---

## Code Examples

### validate_loaded 모듈 골격

```python
# Source: CONTEXT.md D-01~D-04 + ORM 모델 분석 [VERIFIED]
# 위치: src/scenario_db/etl/validate_loaded.py

from __future__ import annotations
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from sqlalchemy import select

from scenario_db.db.models.capability import IpCatalog
from scenario_db.db.models.decision import GateRule, Issue, Waiver
from scenario_db.db.models.definition import Project, Scenario, ScenarioVariant
from scenario_db.db.models.evidence import Evidence
from scenario_db.db.models.decision import Review


class ValidationReport(BaseModel):
    model_config = ConfigDict(extra='forbid')
    errors: list[str] = []
    warnings: list[str] = []

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


def validate_loaded(session: Session) -> ValidationReport:
    errors: list[str] = []
    warnings: list[str] = []
    # ... 8가지 규칙 구현 ...
    return ValidationReport(errors=errors, warnings=warnings)
```

### CanonicalScenarioGraph Record 타입 예시

```python
# Source: CONTEXT.md D-05~D-09 + ORM 모델 분석 [VERIFIED]
# 위치: src/scenario_db/db/repositories/scenario_graph.py

from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field


class ScenarioRecord(BaseModel):
    model_config = ConfigDict(extra='forbid', from_attributes=True)
    id: str
    schema_version: str
    project_ref: str
    pipeline: dict
    size_profile: dict | None = None
    design_axes: list | None = None
    yaml_sha256: str
    # metadata_ 처리: ORM 속성명 그대로
    metadata_: dict = Field(alias="metadata_")


class VariantRecord(BaseModel):
    model_config = ConfigDict(extra='forbid', from_attributes=True)
    scenario_id: str
    id: str
    severity: str | None = None
    design_conditions: dict | None = None
    ip_requirements: dict | None = None
    sw_requirements: dict | None = None
    violation_policy: dict | None = None
    tags: list[str] | None = None
    derived_from_variant: str | None = None


class CanonicalScenarioGraph(BaseModel):
    model_config = ConfigDict(extra='forbid')
    scenario_id: str
    variant_id: str
    scenario: ScenarioRecord
    variant: VariantRecord
    project: ProjectRecord | None = None
    pipeline: dict
    ip_catalog: dict[str, IpRecord]
    sw_profiles: dict[str, SwProfileRecord]
    evidence: list[EvidenceRecord]
    issues: list[IssueRecord]
    waivers: list[WaiverRecord]
    reviews: list[ReviewRecord]
```

### Integration test 패턴 (기존 conftest.py 재활용)

```python
# Source: tests/integration/conftest.py 분석 [VERIFIED]
# 위치: tests/integration/test_validate_loaded.py

import pytest
from sqlalchemy.orm import Session
from scenario_db.etl.validate_loaded import validate_loaded

pytestmark = pytest.mark.integration


def test_validate_loaded_no_errors(engine):
    """demo fixtures 로드 후 semantic validation 오류 없음."""
    with Session(engine) as session:
        report = validate_loaded(session)
    assert report.errors == [], f"Validation errors: {report.errors}"


def test_canonical_graph_demo_scenario(engine):
    """uc-camera-recording + UHD60-HDR10-H265 canonical graph 로드."""
    from scenario_db.db.repositories.scenario_graph import get_canonical_graph
    with Session(engine) as session:
        graph = get_canonical_graph(session, "uc-camera-recording", "UHD60-HDR10-H265")
    assert graph is not None
    assert graph.scenario_id == "uc-camera-recording"
    assert graph.variant_id == "UHD60-HDR10-H265"
    assert graph.project is not None
    assert len(graph.evidence) >= 1
    assert len(graph.issues) >= 1


def test_canonical_graph_not_found(engine):
    """존재하지 않는 scenario_id → None 반환."""
    from scenario_db.db.repositories.scenario_graph import get_canonical_graph
    with Session(engine) as session:
        graph = get_canonical_graph(session, "no-such-scenario", "no-variant")
    assert graph is None
```

---

## Runtime State Inventory

이 Phase는 기존 코드베이스에 새 모듈을 추가하는 greenfield 작업이므로 rename/refactor 해당 없음.

단, Wave 0에서 demo fixture `FHD30-SDR-H265` 추가 여부를 결정해야 함:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | demo fixture variants: UHD60-HDR10-H265, 8K120-..., UHD60-...-sustained | FHD30-SDR-H265 추가 여부 결정 |
| Live service config | 없음 | — |
| OS-registered state | 없음 | — |
| Secrets/env vars | `DATABASE_URL` — testcontainers가 주입 | 변경 없음 |
| Build artifacts | 없음 | — |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SQLAlchemy 1.x `session.query()` | SQLAlchemy 2.0 `select()` stmt | SA 2.0 | 기존 코드는 1.x 스타일 혼용 — 신규 코드는 2.0 스타일 권장 |
| `model.from_orm()` (Pydantic v1) | `model.model_validate(obj)` (Pydantic v2) | Pydantic v2 | 기존 코드가 v2 사용 중 [VERIFIED] |
| `joinedload` with relationships | 수동 JOIN + IN 쿼리 | relationship 없음 | 이 프로젝트 특수 사정 |

**주의:** 기존 repositories (`definition.py`, `evidence.py` 등)는 SQLAlchemy 1.x 스타일 `session.query()` 사용. 신규 모듈은 2.0 스타일 `select()` 권장이나 일관성을 위해 기존 스타일 따를 수도 있음 — planner 결정.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `model_validate(orm_obj)` + `from_attributes=True` 패턴이 `_sa_instance_state` 없이 동작 | Pattern 5 | 구현 시 `ValidationError` → `__dict__` 필터링으로 fallback |
| A2 | `FHD30-SDR-H265` fixture는 Wave 0 작업으로 추가해야 함 (현재 없음) | Finding 2 | acceptance criteria 조정 필요 |
| A3 | Issue 조회는 전체 로드 후 Python 필터로 충분 (소규모 fixture) | Pattern 4 | 대규모 데이터 시 DB-side JSONB 필터로 교체 필요 |

---

## Open Questions (All Resolved)

1. **FHD30-SDR-H265 fixture 처리 방법** — RESOLVED
   - What we know: CONTEXT.md acceptance criteria에 언급되나 fixture에 없음 [VERIFIED]
   - Resolution: PLAN-01 Task 1에서 `FHD30-SDR-H265` variant를 `uc-camera-recording.yaml`에 추가하는 것으로 결정. acceptance criteria 원문 준수.

2. **load_yaml_dir() 반환값 확장 여부** — RESOLVED
   - What we know: D-03은 자동 호출만 요구, 반환값 변경 명시 없음
   - Resolution: Finding 6 결정 — `load_yaml_dir()` 반환값 `dict[str, int]` 불변 유지. `validate_loaded()`는 `session.commit()` 이후 부수 효과로 자동 호출되어 `logger.warning()` 출력. 기존 호출자 영향 없음.

3. **sw_profiles 조회 전략** — RESOLVED
   - What we know: `CanonicalScenarioGraph.sw_profiles` 필드 존재, `variant.sw_requirements.profile_constraints` 에 ref 정보
   - Resolution: Phase 1에서는 `sw_profiles={}` empty dict 허용 (기본값). PLAN-02 Task 2에서 `variant.sw_requirements.profile_constraints[*].profile_ref` 경로를 시도하되, 해당 키가 없거나 결과가 없는 경우 빈 dict 반환. sw_requirements JSONB 정확한 스키마 확인은 실행 시점에 검증.

---

## Environment Availability

[VERIFIED: 직접 실행]

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11 | 전체 | ✓ | 3.11.15 | — |
| SQLAlchemy | ORM 쿼리 | ✓ | 2.0.49 | — |
| Pydantic v2 | DTO 정의 | ✓ | 2.13.2 | — |
| Docker | integration test (testcontainers) | ✓ | 29.4.0 | — |
| testcontainers | integration test | ✓ | 설치됨 | — |
| PostgreSQL 16 | integration test | ✓ (Docker) | 16-alpine via container | — |
| pytest | 테스트 | ✓ | 설치됨 | — |

**Missing dependencies with no fallback:** 없음

**Missing dependencies with fallback:** 없음

---

## Validation Architecture

`workflow.nyquist_validation: true` (`.planning/config.json` [VERIFIED])

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (버전 확인됨) |
| Config file | `pyproject.toml` 또는 `pytest.ini` (기존 markers: `integration`) |
| Quick run command | `uv run pytest tests/unit/ -q` |
| Integration run command | `uv run pytest tests/integration/ -q -m integration` |
| Full suite command | `uv run pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DB-01 | `validate_loaded()` 반환값 `errors==[]` (demo fixtures 기준) | integration | `uv run pytest tests/integration/test_validate_loaded.py -x` | ❌ Wave 0 |
| DB-01 | `validate_loaded()` 오류 감지 — 존재하지 않는 project_ref | unit | `uv run pytest tests/unit/test_validate_loaded.py::test_missing_project_ref -x` | ❌ Wave 0 |
| DB-02 | `get_canonical_graph("uc-camera-recording", "UHD60-HDR10-H265")` 반환 그래프 구조 검증 | integration | `uv run pytest tests/integration/test_scenario_graph.py::test_canonical_graph_demo_scenario -x` | ❌ Wave 0 |
| DB-02 | `get_canonical_graph` NotFound 처리 | integration | `uv run pytest tests/integration/test_scenario_graph.py::test_canonical_graph_not_found -x` | ❌ Wave 0 |
| DB-02 | `CanonicalScenarioGraph` Pydantic round-trip | unit | `uv run pytest tests/unit/test_scenario_graph_models.py -x` | ❌ Wave 0 |
| DB-03 | `view_projection.py` 기본 쿼리 동작 | integration | `uv run pytest tests/integration/test_view_projection.py -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/unit/ -q`
- **Per wave merge:** `uv run pytest tests/integration/ -q -m integration`
- **Phase gate:** `uv run pytest tests/ -q` (기존 209개 + 신규 테스트 모두 green)

### Wave 0 Gaps

- [ ] `tests/unit/test_validate_loaded.py` — DB 없이 ValidationReport 로직 단위 테스트 (DB-01)
- [ ] `tests/integration/test_validate_loaded.py` — demo fixtures 로드 후 validate_loaded 통합 테스트 (DB-01)
- [ ] `tests/unit/test_scenario_graph_models.py` — CanonicalScenarioGraph Pydantic round-trip (DB-02)
- [ ] `tests/integration/test_scenario_graph.py` — get_canonical_graph 통합 테스트 (DB-02, DB-03)
- [ ] `tests/integration/test_view_projection.py` — view_projection 쿼리 (DB-03)
- [ ] (선택) `demo/fixtures/02_definition/uc-camera-recording.yaml` — `FHD30-SDR-H265` variant 추가 (acceptance criteria 원문 준수 시)

---

## Security Domain

이 Phase는 DB 읽기 전용 쿼리 추가 (read-path)이며 사용자 입력을 받는 엔드포인트가 없음. 신규 엔드포인트는 Phase 3에서 추가됨.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — Phase 3에서 |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes (제한적) | `scenario_id`, `variant_id` 파라미터 — SQLAlchemy parameterized query (기존 패턴) |
| V6 Cryptography | no | — |

**Phase 1 specific:** `validate_loaded(session)` 쿼리는 read-only SELECT만 사용. `get_canonical_graph()` 역시 SELECT only. SQL injection 위험 없음 — 모든 값이 SQLAlchemy ORM bind parameter로 처리됨.

---

## Sources

### Primary (HIGH confidence)

- `src/scenario_db/etl/loader.py` — load_yaml_dir() 구조, SAVEPOINT 패턴, 반환값 [VERIFIED: 직접 읽음]
- `src/scenario_db/db/models/*.py` — 모든 ORM 모델 컬럼명, 타입, relationship 부재 [VERIFIED: 직접 읽음 + sa_inspect()]
- `src/scenario_db/db/repositories/*.py` — 기존 query 패턴, apply_sort 활용 [VERIFIED: 직접 읽음]
- `tests/integration/conftest.py` — testcontainers + session scope fixture 패턴 [VERIFIED: 직접 읽음]
- `demo/fixtures/**/*.yaml` — Issue.affects, Waiver.scope, GateRule 구조 [VERIFIED: 직접 파싱]
- `uv run python -c "..."` — SQLAlchemy 2.0.49, Pydantic 2.13.2, testcontainers 가용성 [VERIFIED: 직접 실행]

### Secondary (MEDIUM confidence)

- `docs/implementation-roadmap-etl-resolver-api-viewer.md §4` — Phase 1 구현 지침, CanonicalScenarioGraph 구조 [CITED: 공식 프로젝트 문서]
- `.planning/phases/01-db-foundation/01-CONTEXT.md` — 모든 locked decisions [CITED: 프로젝트 결정 문서]

### Tertiary (LOW confidence)

- `model_validate(orm_obj)` + `from_attributes=True` 동작 — Pydantic v2 공식 ORM 통합 기능이나 `_sa_instance_state` 필터링 동작은 [ASSUMED] — 구현 시 검증 필요

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — 직접 import 확인
- Architecture (query 전략): HIGH — ORM inspect로 relationship 부재 확인, 수동 쿼리 전략 도출
- Validation rules: HIGH — fixture YAML 직접 파싱으로 JSONB 구조 확인
- ORM-to-Pydantic 매핑: MEDIUM — `from_attributes=True` 패턴은 Pydantic v2 공식 기능이나 `_sa_instance_state` 처리는 구현 시 검증 필요
- Test patterns: HIGH — 기존 conftest.py 패턴 완전 파악

**Research date:** 2026-05-06
**Valid until:** 2026-06-06 (안정적 스택 — 30일)
