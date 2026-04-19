# Phase A Completion Report — ScenarioDB PostgreSQL + ETL

> **작성일**: 2026-04-19  
> **작성자**: YHJOO  
> **프로젝트**: Mobile SoC Multimedia IP Scenario DB  
> **저장소**: `E:/15_ClaudeCode_IP_Modeling/02_ScenarioDB`  
> **커밋**: `9230f63`

---

## 1. Executive Summary

Phase A는 Phase 1~4에서 완성된 Pydantic v2 모델 레이어(124 tests)를 실제 PostgreSQL 데이터베이스와 연결하는 작업이다.

| 항목 | 결과 |
|------|------|
| PostgreSQL 테이블 수 | 15개 (§22 DDL 완전 적용) |
| ETL 적재 성공 | 20/20 YAML 파일, 0 skip |
| 기존 pytest | 124 passed, 0 failed (0.30s) |
| 데모 스토리 | LLC Thrashing Before/After — `exploration_only` → `production_ready` |
| 커밋 | 85 files, 8,815 insertions |

### 핵심 달성 사항

- **SQLAlchemy 2.0 ORM**: 4-Layer 스키마를 15개 테이블로 매핑. JSONB Computed column (`sw_version_hint`, `overall_feasibility`)으로 쿼리 최적화
- **Alembic migration**: 환경변수 기반 자격증명 (`%(DATABASE_URL)s`), 재현 가능한 DDL
- **ETL importer**: PostgreSQL SAVEPOINT 패턴으로 파일 단위 오류 격리. SHA256으로 미변경 파일 skip
- **demo/fixtures/**: 20개 YAML — LLC 버그 도입 → 이슈 등록 → waiver → 수정 → 재검증까지 end-to-end 시나리오

---

## 2. 설계 의사결정 흐름 (v1.0 → v2.2)

### 스키마 진화 배경

```
v1.0  단일 YAML 플랫파일 — HW/SW/scenario 혼재
  │   문제: SW 버전 변경 시 scenario 전체 복사 필요
  ↓
v2.0  HW Catalog 분리
  │   문제: SW capability 표현 부재, violation 정책 없음
  ↓
v2.1  SW Catalog 추가
  │   문제: Attestation 위조 가능, 자동 Gate 평가 없음
  ↓
v2.2  Triple-Track Attestation + Gate Rules + Matcher DSL
      현재 구현 버전
```

### 4-Layer 경계선 원칙

| 원칙 | 잘못된 이해 | 올바른 이해 |
|------|-------------|-------------|
| Variant ≠ Instance | variant마다 시뮬레이션 실행 | variant는 설계 공간, instance는 실행 컨텍스트 |
| Capability ≠ Requirement | IP 스펙 = 시나리오 요구사항 | `required_throughput_mpps` vs `throughput_mpps` (operating mode) |
| Canonical ≠ Derived | DB = YAML 사본 | YAML이 source of truth, DB는 derived (upsert) |

### Phase A 핵심 설계 결정

#### A-1. ETL 트랜잭션 경계: SAVEPOINT per-file

```python
# loader.py
with session.begin_nested():          # PostgreSQL SAVEPOINT
    MAPPER_REGISTRY[kind](raw, sha256, session)
```

- 대안: 전체 배치 단일 트랜잭션 → 1개 파일 오류로 전체 롤백
- 채택 이유: 시드 데이터 일부 교체 시 정상 파일 보존 필수

#### A-2. Evidence Computed columns (persisted=True)

```sql
sw_version_hint  TEXT GENERATED ALWAYS AS (execution_context->>'sw_baseline_ref') STORED
sweep_value_hint TEXT GENERATED ALWAYS AS (sweep_context->>'sweep_value') STORED
```

- `sw_baseline_ref`로 evidence 필터링이 핵심 쿼리 패턴
- JSONB 내부 키 추출을 매 쿼리마다 하지 않고 인덱스 가능한 컬럼으로 승격
- `persisted=True` 필수: `persisted=False`는 PostgreSQL에서 `VIRTUAL` — 인덱스 불가

#### A-3. PipelineEdge `by_alias=True`

```python
# definition.py mapper
row.pipeline = obj.pipeline.model_dump(by_alias=True, exclude_none=True)
```

- `PipelineEdge.from_`는 Python 예약어 `from` 우회를 위한 필드명
- `by_alias=True` 미적용 시 JSONB에 `"from_"` 저장 → 스키마 불일치

#### A-4. Alembic 자격증명 분리

```ini
# alembic.ini
sqlalchemy.url = %(DATABASE_URL)s
```

```python
# env.py
config.set_main_option("DATABASE_URL", os.environ.get("DATABASE_URL", ""))
```

- `.env` 파일은 `.gitignore` 처리 — 자격증명 레포 미포함

---

## 3. 구현 산출물

### 3-1. Pydantic 모델 레이어 (Phase 1~4)

| Phase | 레이어 | 파일 | 핵심 모델 | 테스트 |
|-------|--------|------|-----------|--------|
| 1 | Capability | `models/capability/hw.py`, `sw.py` | IpCatalog, SocPlatform, SwProfile, SwComponent | 45 |
| 2 | Definition | `models/definition/project.py`, `usecase.py` | Project, Usecase, Variant, ViolationPolicy | 26 |
| 3 | Evidence | `models/evidence/simulation.py`, `measurement.py`, `resolution.py` | SimulationEvidence, MeasurementEvidence, ResolutionResult | 27 |
| 4 | Decision | `models/decision/common.py`, `review.py`, `waiver.py`, `issue.py`, `gate_rule.py` | Review, Waiver, Issue, GateRule, MatchDSL | 26 |
| **계** | | **13 파일** | | **124** |

### 3-2. DB/ETL 레이어 (Phase A)

```
src/scenario_db/
├── db/
│   ├── base.py          # DeclarativeBase, make_engine()
│   ├── session.py       # get_session() contextmanager
│   └── models/
│       ├── capability.py    # SocPlatform, IpCatalog, SwProfile, SwComponent
│       ├── definition.py    # Project, Scenario, ScenarioVariant
│       ├── evidence.py      # Evidence (Computed columns), SweepJob
│       └── decision.py      # GateRule, Issue, Waiver, WaiverAuditLog,
│                            # Review, ReviewAuditLog
└── etl/
    ├── loader.py            # load_yaml_dir() — LOAD_ORDER, SAVEPOINT
    └── mappers/
        ├── capability.py    # upsert_soc/ip/sw_profile/sw_component
        ├── definition.py    # upsert_project/usecase (variants 포함)
        ├── evidence.py      # upsert_simulation/measurement
        └── decision.py      # upsert_gate_rule/issue/waiver/review
```

**ETL LOAD_ORDER (FK 의존 순서)**:

```
soc → ip → sw_profile → sw_component
  → project → scenario.usecase
    → evidence.simulation → evidence.measurement
      → decision.gate_rule → decision.issue → decision.waiver → decision.review
```

### 3-3. demo/fixtures/ (20개 YAML)

```
demo/fixtures/
├── 00_hw/       soc-exynos2500.yaml  ip-isp-v12.yaml  ip-mfc-v14.yaml
│                ip-llc-v2.yaml       ip-csis-v8.yaml  ip-dpu-v9.yaml
├── 01_sw/       sw-vendor-v1.2.3.yaml (LLC bug)
│                sw-vendor-v1.3.0.yaml (LLC fix, LLC_per_ip_partition: enabled)
│                hal-cam-v4.5.yaml
├── 02_definition/ proj-A-exynos2500.yaml  uc-camera-recording.yaml
├── 03_evidence/ sim-UHD60-A0-sw123.yaml   ← exploration_only, 2350 mW
│                sim-UHD60-A0-sw130.yaml   ← production_ready, 2150 mW
│                meas-UHD60-A0-sw123.yaml
└── 04_decision/ iss-LLC-thrashing-0221.yaml
                 waiver-LLC-thrashing.yaml   (status: approved, MFA Track3)
                 rev-sw123.yaml              (gate: WARN, approved_with_waiver)
                 rev-sw130.yaml             (gate: PASS, approved)
                 rule-feasibility-check.yaml
                 rule-known-issue-match.yaml
```

### 3-4. 인프라

| 파일 | 내용 |
|------|------|
| `docker-compose.yml` | PostgreSQL 16 + pgAdmin 4, healthcheck 포함 |
| `.env` | `DATABASE_URL` (gitignore 처리) |
| `alembic.ini` | `%(DATABASE_URL)s` 플레이스홀더 |
| `alembic/versions/0001_initial_schema.py` | §22 DDL 전체, GIN index, Computed columns |
| `.gitattributes` | 모든 텍스트 파일 LF 고정 |

---

## 4. 검증 결과

### 4-1. pytest — 124 passed

```
platform win32 -- Python 3.11.15, pytest-9.0.3
rootdir: E:\15_ClaudeCode_IP_Modeling\02_ScenarioDB

tests/test_capability_models.py    45 passed
tests/test_definition_models.py    26 passed
tests/test_evidence_models.py      27 passed
tests/test_decision_models.py      26 passed

========================= 124 passed in 0.30s =========================
```

### 4-2. ETL 적재 결과 — 20/20 성공

```
ETL 결과:
  soc                              1건
  ip                               5건
  sw_profile                       2건
  sw_component                     1건
  project                          1건
  scenario.usecase                 1건
  evidence.simulation              2건
  evidence.measurement             1건
  decision.gate_rule               2건
  decision.issue                   1건
  decision.waiver                  1건
  decision.review                  2건
```

### 4-3. PostgreSQL 테이블 레코드 수

```sql
SELECT tablename, COUNT(*) FROM ... GROUP BY tablename;
```

| 테이블 | 건수 | 비고 |
|--------|------|------|
| soc_platforms | 1 | soc-exynos2500 |
| ip_catalog | 5 | ISP/MFC/LLC/CSIS/DPU |
| sw_profiles | 2 | v1.2.3 (bug) + v1.3.0 (fix) |
| sw_components | 1 | hal-cam-v4.5 |
| projects | 1 | proj-A-exynos2500 |
| scenarios | 1 | uc-camera-recording |
| scenario_variants | 3 | UHD60, 8K, derived |
| sweep_jobs | 0 | (미사용) |
| evidence | 3 | 2 sim + 1 meas |
| gate_rules | 2 | feasibility-check + known-issue-match |
| issues | 1 | iss-LLC-thrashing-0221 |
| waivers | 1 | waiver-LLC-thrashing |
| reviews | 2 | sw123 (WARN) + sw130 (PASS) |
| waiver_audit_log | 0 | API 주입 시 채워짐 |
| review_audit_log | 0 | API 주입 시 채워짐 |

### 4-4. 핵심 Before/After 쿼리 결과

**LLC Thrashing 수정 전후 비교 (실제 DB 쿼리)**

```sql
SELECT sw_version_hint, overall_feasibility,
       kpi->>'total_power_mw' AS power_mw
FROM evidence
WHERE kind = 'evidence.simulation'
ORDER BY sw_version_hint;
```

| sw_version_hint | overall_feasibility | power_mw |
|-----------------|---------------------|----------|
| sw-vendor-v1.2.3 | **exploration_only** | 2350 mW |
| sw-vendor-v1.3.0 | **production_ready** | 2150 mW |

> `sw_version_hint`는 Computed column (`execution_context->>'sw_baseline_ref'`). 인덱스 지원.

**Review gate 결과 비교**

```sql
SELECT id, gate_result, decision, waiver_ref
FROM reviews ORDER BY id;
```

| id | gate_result | decision | waiver_ref |
|----|-------------|----------|------------|
| rev-camera-recording-...-sw123-... | **WARN** | approved_with_waiver | waiver-LLC-thrashing-... |
| rev-camera-recording-...-sw130-... | **PASS** | approved | — |

### 4-5. ScenarioVariant 확인

```sql
SELECT id, severity, tags FROM scenario_variants;
```

| variant_id | severity | tags |
|------------|----------|------|
| UHD60-HDR10-H265 | heavy | [thermal_sensitive, ddr_bw_critical] |
| 8K120-HDR10plus-AV1-exploration | critical | [] |
| UHD60-HDR10-sustained-10min | critical | [] |

---

## 5. 알려진 이슈 + 해결

### 5-1. `obj.globals_` AttributeError

| 항목 | 내용 |
|------|------|
| **증상** | `ETL: skip proj-A-exynos2500.yaml [project] 'Project' object has no attribute 'globals_'` |
| **원인** | `etl/mappers/definition.py`에서 `obj.globals_` 참조. Pydantic 모델은 `Project.globals` (언더스코어 없음). ORM 모델의 컬럼명이 `globals_`여서 혼동 |
| **수정** | `definition.py:17` `obj.globals_` → `obj.globals` |
| **영향** | project FK 실패 → scenario/evidence/review 연쇄 실패 (7건). 수정 후 20/20 성공 |

### 5-2. `severity: high` 유효하지 않은 값

| 항목 | 내용 |
|------|------|
| **증상** | Pydantic ValidationError — `severity: high` |
| **원인** | `Severity` StrEnum 값: `light / medium / heavy / critical`. `high`는 정의되지 않은 값 |
| **수정** | `tests/fixtures/decision/iss-LLC-thrashing-0221.yaml`, `rule-feasibility-check.yaml` → `severity: heavy` |

### 5-3. Docker Desktop PATH 미등록 (Windows)

| 항목 | 내용 |
|------|------|
| **증상** | 신규 bash 세션에서 `docker: command not found` |
| **원인** | Docker Desktop 설치 후 bash PATH 미반영 |
| **해결** | `export PATH="/c/Program Files/Docker/Docker/resources/bin:$PATH"` |

### 5-4. Alembic env.py Write 실패

| 항목 | 내용 |
|------|------|
| **증상** | Write 도구 — "File has not been read yet" |
| **원인** | Claude Code 정책: 파일 Read 없이 Write 불가 |
| **해결** | Read 후 Write 순서 준수 |

---

## 6. 다음 단계

### Phase B: Jupyter 탐색 노트북

목적: DB 적재 데이터의 빠른 탐색 + 쿼리 패턴 확정

```
notebooks/
├── 01_capability_overview.ipynb   # SoC/IP/SW 카탈로그 브라우징
├── 02_evidence_analysis.ipynb     # Before/After KPI 비교 시각화
└── 03_gate_review_flow.ipynb      # Review → Waiver 연결 흐름
```

**핵심 쿼리 패턴 (확정 필요)**:
- `sw_version_hint` 인덱스 활용 필터링
- `overall_feasibility` 별 집계
- Waiver 만료일 경고 쿼리

### Phase C: CLI (`typer` + `rich`)

```bash
scenario-db evidence list --scenario uc-camera-recording --sw sw-vendor-v1.3.0
scenario-db review show rev-camera-recording-UHD60-A0-sw130-20260419
scenario-db gate check --evidence sim-UHD60-A0-sw130
```

서브커맨드: `evidence list/show`, `review list/show`, `gate check`, `etl import`

### Phase D: FastAPI + Swagger UI

```
GET  /evidence?scenario_ref=&sw_baseline=&feasibility=
GET  /evidence/{id}
GET  /reviews?gate_result=PASS
POST /reviews/{id}/approve          ← Track 3 (server_attestation) 주입
GET  /gate-rules
POST /gate-rules/evaluate           ← 자동 Gate 평가 엔드포인트
```

**자동 Review Gate Demo 흐름**:
1. `POST /evidence` → ETL 트리거
2. GateRule 자동 평가 → `gate_result` 계산
3. `GET /reviews/{id}` → Swagger UI에서 결과 확인
4. `POST /reviews/{id}/approve` → Track 3 server_attestation 주입 + audit_log 기록

---

## Appendix

### A. 파일 목록

#### src/ — Python 소스

```
src/scenario_db/
├── __init__.py
├── models/
│   ├── common.py                   # DocumentId, SchemaVersion, FeatureFlagValue
│   ├── capability/
│   │   ├── hw.py                   # SocPlatform, IpCatalog, IpHierarchy
│   │   └── sw.py                   # SwProfile, SwComponent
│   ├── definition/
│   │   ├── project.py              # Project, ProjectGlobals
│   │   └── usecase.py              # Usecase, Variant, ViolationPolicy, Pipeline
│   ├── evidence/
│   │   ├── common.py               # ExecutionContext, SweepContext, Aggregation
│   │   ├── resolution.py           # ResolutionResult, FeatureCheck, Violation
│   │   ├── simulation.py           # SimulationEvidence, IpBreakdown
│   │   └── measurement.py          # MeasurementEvidence, MeasuredKpi, Provenance
│   └── decision/
│       ├── common.py               # Attestation, MatchDSL, AuthMethod
│       ├── gate_rule.py            # GateRule, GateTrigger, GateAction
│       ├── issue.py                # Issue, AffectsEntry, PmuSignature
│       ├── waiver.py               # Waiver, WaiverScope
│       └── review.py               # Review, AutoCheck, WaiverStatus, ReviewDecision
├── db/
│   ├── base.py                     # DeclarativeBase, make_engine()
│   ├── session.py                  # get_session()
│   └── models/
│       ├── capability.py           # ORM: SocPlatform, IpCatalog, SwProfile, SwComponent
│       ├── definition.py           # ORM: Project, Scenario, ScenarioVariant
│       ├── evidence.py             # ORM: Evidence (Computed), SweepJob
│       └── decision.py             # ORM: GateRule, Issue, Waiver, Review + AuditLog
└── etl/
    ├── loader.py                   # load_yaml_dir(), LOAD_ORDER, MAPPER_REGISTRY
    └── mappers/
        ├── capability.py
        ├── definition.py
        ├── evidence.py
        └── decision.py
```

#### tests/

```
tests/
├── fixtures/
│   ├── hw/          ip-isp-v12.yaml
│   ├── sw/          sw-vendor-v1.2.3.yaml  hal-cam-v4.5.yaml
│   ├── definition/  proj-A-exynos2500.yaml  uc-camera-recording.yaml
│   ├── evidence/    sim-camera-recording-UHD60-A0-sw123.yaml  meas-*.yaml
│   └── decision/    iss-LLC-thrashing-0221.yaml  rev-*.yaml  waiver-*.yaml  rule-*.yaml
├── test_capability_models.py    (45 tests)
├── test_definition_models.py    (26 tests)
├── test_evidence_models.py      (27 tests)
└── test_decision_models.py      (26 tests)
```

#### demo/fixtures/

```
demo/fixtures/
├── 00_hw/    soc-exynos2500  ip-isp-v12  ip-mfc-v14  ip-llc-v2  ip-csis-v8  ip-dpu-v9
├── 01_sw/    sw-vendor-v1.2.3  sw-vendor-v1.3.0  hal-cam-v4.5
├── 02_definition/  proj-A-exynos2500  uc-camera-recording
├── 03_evidence/    sim-sw123  sim-sw130  meas-sw123
└── 04_decision/    iss-LLC-thrashing  waiver-LLC-thrashing
                    rev-sw123  rev-sw130  rule-feasibility-check  rule-known-issue-match
```

### B. ER Diagram (Mermaid)

```mermaid
erDiagram
    soc_platforms {
        text id PK
        text schema_version
        text process_node
        text memory_type
        text bus_protocol
        jsonb ips
        text yaml_sha256
    }

    ip_catalog {
        text id PK
        text schema_version
        text category
        jsonb hierarchy
        jsonb capabilities
        text rtl_version
        jsonb compatible_soc
        text yaml_sha256
    }

    sw_profiles {
        text id PK
        text schema_version
        jsonb metadata
        jsonb components
        jsonb feature_flags
        jsonb compatibility
        text yaml_sha256
    }

    sw_components {
        text id PK
        text schema_version
        text category
        jsonb metadata
        jsonb feature_flags
        jsonb capabilities
        text yaml_sha256
    }

    projects {
        text id PK
        text schema_version
        jsonb metadata
        jsonb globals
        text yaml_sha256
    }

    scenarios {
        text id PK
        text schema_version
        text project_ref FK
        jsonb metadata
        jsonb pipeline
        jsonb size_profile
        jsonb design_axes
        text yaml_sha256
    }

    scenario_variants {
        text scenario_id PK, FK
        text id PK
        text severity
        jsonb design_conditions
        jsonb ip_requirements
        jsonb sw_requirements
        jsonb violation_policy
        jsonb tags
        text derived_from_variant
    }

    evidence {
        text id PK
        text schema_version
        text kind
        text scenario_ref FK
        text variant_ref
        text sw_baseline_ref FK
        text sweep_job_id FK
        jsonb execution_context
        jsonb sweep_context
        jsonb resolution_result
        text overall_feasibility
        jsonb aggregation
        jsonb kpi
        jsonb run_info
        jsonb ip_breakdown
        jsonb provenance
        jsonb artifacts
        text sw_version_hint
        text sweep_value_hint
        text yaml_sha256
    }

    gate_rules {
        text id PK
        text schema_version
        jsonb metadata
        jsonb trigger
        jsonb applies_to
        jsonb condition
        jsonb action
        text yaml_sha256
    }

    issues {
        text id PK
        text schema_version
        jsonb metadata
        jsonb affects
        jsonb affects_ip
        jsonb pmu_signature
        jsonb resolution
        text yaml_sha256
    }

    waivers {
        text id PK
        text title
        text issue_ref FK
        jsonb scope
        text justification
        text status
        text approver_claim
        date claim_at
        text git_commit_sha
        text git_commit_author_email
        boolean git_signed
        text approved_by_auth
        text auth_method
        text auth_session_id
        date approved_at
        date expires_on
        text yaml_sha256
    }

    reviews {
        text id PK
        text scenario_ref FK
        text variant_ref
        jsonb evidence_refs
        text gate_result
        jsonb auto_checks
        text decision
        text waiver_ref FK
        text rationale
        jsonb review_scope
        jsonb validation
        text status
        text approver_claim
        date claim_at
        text git_commit_sha
        text git_commit_author_email
        boolean git_signed
        text approved_by_auth
        text auth_method
        text auth_session_id
        text yaml_sha256
    }

    projects ||--o{ scenarios : "project_ref"
    scenarios ||--o{ scenario_variants : "scenario_id"
    scenarios ||--o{ evidence : "scenario_ref"
    sw_profiles ||--o{ evidence : "sw_baseline_ref"
    issues ||--o| waivers : "issue_ref"
    scenarios ||--o{ reviews : "scenario_ref"
    waivers ||--o| reviews : "waiver_ref"
```

### C. 의존성 (pyproject.toml)

```toml
[project]
dependencies = [
    "pydantic>=2.13.2",
    "pyyaml>=6.0.3",
    "sqlalchemy>=2.0",
    "psycopg2-binary>=2.9",
    "alembic>=1.13",
]
```

### D. 환경 재현 절차

```bash
# 1. Docker 기동 (PostgreSQL 16)
export PATH="/c/Program Files/Docker/Docker/resources/bin:$PATH"
docker compose up -d

# 2. 환경변수
export DATABASE_URL="postgresql+psycopg2://scenario_user:scenario_pass@localhost:5432/scenario_db"

# 3. 의존성 설치
uv sync

# 4. DB 스키마 적용
uv run alembic upgrade head

# 5. 시드 데이터 임포트
uv run python -m scenario_db.etl.loader demo/fixtures/

# 6. 검증
uv run pytest tests/ -q          # 124 passed
```
