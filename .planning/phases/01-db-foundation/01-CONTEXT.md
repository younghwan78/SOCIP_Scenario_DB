# Phase 1: DB Foundation - Context

**Gathered:** 2026-05-06
**Status:** Ready for planning

<domain>
## Phase Boundary

DB에서 scenario 전체 그래프를 안전하게 조회할 수 있는 기반 구축.
ETL이 FK-like 참조 무결성을 검증하고, `CanonicalScenarioGraph` Pydantic DTO로
scenario + variant + project + evidence + issues + waivers + reviews를 단일 쿼리로 반환한다.

**In scope:**
- ETL 완료 후 semantic validation (`etl/validate_loaded.py`)
- `CanonicalScenarioGraph` Pydantic v2 모델 + DB 조회 서비스 (`db/repositories/scenario_graph.py`)
- Repository 확장: `view_projection` 쿼리, `scenario_graph` 쿼리 캡슐화
- 존재하지 않는 scenario_id 요청 시 NotFound 처리

**Out of scope:**
- Resolver engine (Phase 2)
- GateExecutionResult (Phase 2)
- Level 0 DB 연동 viewer (Phase 4)
- gate_executions 영속 테이블 (STATE.md 결정: 비영속)

</domain>

<decisions>
## Implementation Decisions

### ETL Semantic Validation (DB-01)

- **D-01:** Soft validation 방식 채택 — 오류 발견 시 즉시 raise가 아닌 오류 목록 수집 후 리포트. DB 상태 유지. 현재 skip-and-continue SAVEPOINT 패턴과 일관성 유지.
- **D-02:** `validate_loaded(session) -> ValidationReport` 반환 — `ValidationReport(errors: list[str], warnings: list[str])` Pydantic 모델. 호출자가 logging/출력 방식 결정. pytest에서 `assert report.errors == []` 패턴 가능.
- **D-03:** `load_yaml_dir()` 내부에서 ETL 완료 후 자동 호출 — 별도 CLI 커맨드 없이 ETL 실행 시 항상 validation 실행됨.
- **D-04:** Validation 범위: FK-like 참조 전체 (docs §4.4의 8가지 규칙):
  1. `scenario.project_ref` → `projects.id` 존재 여부
  2. `scenario_variant.scenario_id` → `scenarios.id` 존재 여부
  3. `evidence.scenario_ref` + `evidence.variant_ref` → 대상 존재 여부
  4. `review.scenario_ref` + `review.variant_ref` + `review.evidence_refs` + `review.waiver_ref` 존재 여부
  5. `issue.affects[*].scenario_ref` → `*` wildcard 또는 존재하는 scenario_id
  6. `waiver.issue_ref` → `issues.id` 존재 여부
  7. `gate_rule` trigger/condition/action 형식 유효성
  8. `scenario.pipeline` 노드가 참조하는 IP → `ip_catalog.id` 존재 여부

### CanonicalScenarioGraph DTO (DB-02)

- **D-05:** Pydantic v2 모델로 정의 — `model_config = ConfigDict(extra='forbid')` 프로젝트 표준 적용.
- **D-06:** 위치: `src/scenario_db/db/repositories/scenario_graph.py` — DTO 정의 + DB 조회 서비스 함께 배치. docs §4.3 권장 구조.
- **D-07:** ORM → Pydantic 매핑: `model_validate(row.__dict__)` 패턴. ORM과 Pydantic 필드 네이밍이 일치하는 경우 적용. 불일치 필드는 명시적 alias.
- **D-08:** 쿼리 전략: `joinedload` / `selectinload` 적극 활용으로 N+1 쿼리 방지. 단일 쿼리 또는 최대 2번 쿼리로 전체 그래프 로드.
- **D-09:** CanonicalScenarioGraph 필드 구성 (docs §4.5 기준):
  ```python
  class CanonicalScenarioGraph(BaseModel):
      scenario_id: str
      variant_id: str
      scenario: ScenarioRecord       # ORM → Pydantic 변환
      variant: VariantRecord
      project: ProjectRecord | None
      pipeline: dict                 # scenario.pipeline JSONB
      ip_catalog: dict[str, IpRecord]  # pipeline에 참조된 IPs
      sw_profiles: dict[str, SwProfileRecord]
      evidence: list[EvidenceRecord]
      issues: list[IssueRecord]
      waivers: list[WaiverRecord]
      reviews: list[ReviewRecord]
  ```

### Repository 확장 (DB-03)

- **D-10:** `db/repositories/view_projection.py` 신규 생성 — `view_projection` 쿼리 캡슐화 (Level 0 lane data 조회용).
- **D-11:** `db/repositories/scenario_graph.py` 신규 생성 — `get_canonical_graph(db, scenario_id, variant_id) -> CanonicalScenarioGraph | None` 메서드.
- **D-12:** 기존 `db/repositories/definition.py` 는 수정 없이 유지 — 기존 CRUD 메서드는 변경 없음.

### Claude's Discretion
- CanonicalScenarioGraph 내부 Record 타입 네이밍 (`ScenarioRecord` vs `ScenarioData` 등)
- Issues 스코핑: `issue.affects[*].scenario_ref == scenario_id` 또는 `"*"` 패턴으로 필터 (wildcard 지원 필수)
- Waivers 스코핑: 선택된 issues의 `issue_ref`로 연결된 waivers + `scope`에 해당 scenario/variant 포함된 waivers
- `ValidationReport` 모델의 정확한 에러 메시지 포맷

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 설계 명세
- `docs/implementation-roadmap-etl-resolver-api-viewer.md` §4 — Phase 1 ETL+DB 구현 지침, 신규 모듈 목록, post-load validation 8가지 규칙, CanonicalScenarioGraph DTO 제안 구조, acceptance criteria

### 기존 ETL 구조
- `src/scenario_db/etl/loader.py` — `load_yaml_dir()`, MAPPER_REGISTRY, LOAD_ORDER, SAVEPOINT per file 패턴
- `src/scenario_db/etl/mappers/` — 도메인별 upsert 함수 패턴

### ORM 모델 (참조 대상)
- `src/scenario_db/db/models/definition.py` — Project, Scenario, ScenarioVariant ORM
- `src/scenario_db/db/models/decision.py` — GateRule, Issue, Waiver, Review ORM
- `src/scenario_db/db/models/evidence.py` — Evidence ORM
- `src/scenario_db/db/models/capability.py` — IpCatalog, SwProfile ORM

### 기존 Repository 패턴
- `src/scenario_db/db/repositories/definition.py` — list_*/get_* 패턴, apply_sort 활용
- `src/scenario_db/db/repositories/evidence.py` — get_evidence 패턴

### 요구사항
- `.planning/REQUIREMENTS.md` §DB-01~DB-03 — ETL Validation, CanonicalScenarioGraph, Repository 확장 요구사항
- `.planning/ROADMAP.md` Phase 1 — Goal, Success Criteria, Depends on

### 현재 view stub (교체 대상)
- `src/scenario_db/view/service.py` — `project_level0()` stub (Phase 1에서 repository 구현, Phase 4에서 연동)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/scenario_db/etl/loader.py:load_yaml_dir()` — SAVEPOINT + MAPPER_REGISTRY 패턴. validation을 이 함수 끝에 추가하면 됨.
- `src/scenario_db/db/repositories/definition.py` — `get_scenario()`, `get_variant()` 이미 구현됨. `get_canonical_graph()`에서 내부적으로 재활용 가능.
- `src/scenario_db/api/pagination.py:apply_sort()` — 기존 repository들이 사용. scenario_graph에서는 불필요.
- Pydantic v2 `model_config = ConfigDict(extra='forbid')` — 프로젝트 전체 표준.

### Established Patterns
- JSONB-heavy schema + Promoted Columns — `scenario.pipeline`, `variant.ip_requirements` 등이 JSONB. `model_validate(row.__dict__)` 시 JSONB는 `dict`로 그대로 매핑됨.
- `scenario_variants` 복합 PK: `(scenario_id, id)` — `get_variant(db, scenario_id, variant_id)` 패턴 유지 필요.
- SHA256 추적: 모든 ORM 모델이 `yaml_sha256` 컬럼 보유. ValidationReport에서 활용 가능.
- `RuleCache` 패턴: 앱 시작 시 메모리 로드. `CanonicalScenarioGraph`는 request-scoped 쿼리이므로 캐시 불필요.

### Integration Points
- `load_yaml_dir(directory, session)` → 반환값에 `validation_report` 추가 또는 `ValidationReport`를 별도 반환
- `db/repositories/scenario_graph.py` → Phase 2 Resolver, Phase 3 API, Phase 4 Viewer가 모두 소비
- `db/repositories/view_projection.py` → Phase 3 view router가 소비 (`project_level0(db, scenario_id, variant_id)`)

</code_context>

<specifics>
## Specific Ideas

- 기존 ETL이 파일별 SAVEPOINT로 오류를 skip하므로, validation은 로드 성공 후 DB 상태를 검증하는 별도 단계. ETL 오류(파일 파싱 실패)와 semantic validation 오류(참조 무결성)는 분리됨.
- `CanonicalScenarioGraph`가 Phase 2~4 파이프라인의 핵심 입력 DTO이므로, 필드 추가/변경이 발생할 경우 하위 호환성 고려 필요 (Optional 필드 우선).
- demo 시나리오: `uc-camera-recording` + `FHD30-SDR-H265`가 acceptance criteria에 명시됨. 이 시나리오로 canonical graph 로드 테스트 필수.

</specifics>

<deferred>
## Deferred Ideas

- Issues/Waivers 스코핑 세부 로직 — 사용자가 논의 생략 선택. Claude 재량으로 `issue.affects[*].scenario_ref`와 wildcard `"*"` 기반 필터링 구현.
- Validation CLI 통합 (`python -m scenario_db.etl.validate <db_url>`) — Phase 1 이후 필요 시 추가. `load_yaml_dir()` 자동 실행으로 현재는 충분.
- `gate_executions` 영속 테이블 — STATE.md 결정: runtime 게이트 결과는 비영속. 히스토리 필요 시 미래 Phase.

</deferred>

---

*Phase: 1-DB Foundation*
*Context gathered: 2026-05-06*
