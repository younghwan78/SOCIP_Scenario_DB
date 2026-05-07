# Phase 2: Resolver & Gate Engine — Context

**Gathered:** 2026-05-08
**Status:** Ready for planning

<domain>
## Phase Boundary

비영속 Resolver 엔진과 Gate 실행 엔진을 순수 Python으로 구현한다.
- Resolver: variant.ip_requirements → ip_catalog.capabilities 매핑 → ResolverResult
- Gate: CanonicalScenarioGraph + gate_rules → GateExecutionResult (PASS/WARN/BLOCK/WAIVER_REQUIRED)
- DB 쿼리 없음 — 모든 입력은 Phase 1 CanonicalScenarioGraph DTO + 별도 전달 GateRule 리스트
- 결과는 저장 안 함 (runtime only); Phase 3 API가 호출해 직접 반환

</domain>

<decisions>
## Implementation Decisions

### IP Capability Mode Matching (RES-02)

- **D-01:** All-matching modes 전략 — `operating_modes` 중 requirements를 만족하는 모든 모드를 리스트로 반환. First-fit/best-fit 아님. Phase 3 이후 downstream이 최종 선택
  - `throughput_mpps >= required_throughput_mpps` 조건 충족 → matched
  - `supported_features.bitdepth` containment, `supported_features.hdr_formats` containment 체크
- **D-02:** strict unresolved — `required_*` 필드에 대응하는 ip_catalog 필드가 없거나 (e.g. `required_codec` → MFC capabilities에 codec 필드 없음), 값 불일치 시 → `unresolved_requirements`에 기록 + `warnings`에 메시지. "lenient skip" 없음
- **D-03:** matched_modes 비어있으면 (모든 모드 불일치) → `unresolved_requirements`에 ip_ref 추가. fallback 모드 없음

### GateRule 평가 범위 (GATE-02)

- **D-04:** `applies_to.match`만 평가, `condition.match`는 Phase 2에서 스킵
  - `condition.match`는 evidence 데이터 참조 (`evidence.resolution_result.*`) → Phase 3에서 평가
  - `applies_to` 매칭 시 `action.gate_result`를 바로 사용 (PASS/WARN/BLOCK)
  - 코드 주석으로 "condition evaluation deferred to Phase 3" 명시
- **D-05:** `applies_to.match` 평가용 경량 `$`-DSL 평가기 신규 구현
  - 지원 오퍼레이터: `$in`, `$eq`, `$not_empty`, `$exists`
  - 지원 경로: `variant.severity`, `variant.design_conditions.*`
  - MatcherContext와 별개 모듈 — DSL 포맷이 다름 (`{"variant.severity": {"$in": [...]}}`)
- **D-06:** `applies_to`가 None이면 모든 variant에 적용 (unconditional rule)

### Gate Engine 입력 설계 (GATE-02/03)

- **D-07:** 순수 함수 시그니처 `evaluate_gate(graph: CanonicalScenarioGraph, gate_rules: list[GateRule]) -> GateExecutionResult`
  - GateRules는 별도 파라미터로 수신 — Phase 3 라우터가 RuleCache에서 주입
  - DB 쿼리 없음, FastAPI 의존성 없음
- **D-08:** Resolver와 Gate는 독립 — Gate 평가에 ResolverResult 불필요
  - `matched_issues`는 graph.issues (CanonicalScenarioGraph의 매칭된 이슈)를 직접 사용
  - 두 엔진을 독립적으로 호출하거나 조합 가능

### WAIVER_REQUIRED 트리거 조건 (GATE-04)

- **D-09:** `status=open` 또는 `status=deferred`인 issue에 적용 가능 waiver 없으면 → WAIVER_REQUIRED
  - `status=resolved`, `status=wontfix` issue는 waiver 불필요 (이미 처리됨)
- **D-10:** Waiver 적용 가능성 판단: `variant_scope` 평가 (기존 MatcherContext 재사용), `execution_scope`는 Phase 2에서 스킵
  - `WaiverScope.variant_scope.scenario_ref` 일치 + `match_rule` MatcherContext 평가
  - `WaiverScope.execution_scope` (evidence 데이터 필요) → Phase 3 이후 평가

### Final Status Aggregation (GATE-05)

- **D-11:** 우선순위 집계 BLOCK > WAIVER_REQUIRED > WARN > PASS
  - GateRule 평가: BLOCK rule 적용 → BLOCK; WARN rule → WARN
  - Issue 평가: open/deferred issue, waiver 없음 → WAIVER_REQUIRED
  - BLOCK이 하나라도 있으면 전체 status = BLOCK (나머지 무관)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Requirements
- `.planning/REQUIREMENTS.md` §RES-01~RES-03, §GATE-01~GATE-05 — Phase 2 요구사항 전체
- `.planning/ROADMAP.md` §Phase 2 — Success Criteria 5개 항목

### Pydantic 모델 (재사용 + 확장 기반)
- `src/scenario_db/models/capability/hw.py` — IpCatalog, IpCapabilities, OperatingMode, SupportedFeatures
- `src/scenario_db/models/decision/gate_rule.py` — GateRule, GateAppliesTo, GateCondition, GateAction
- `src/scenario_db/models/decision/issue.py` — Issue, IssueStatus, AffectsItem
- `src/scenario_db/models/decision/waiver.py` — Waiver, WaiverScope, WaiverVariantScope
- `src/scenario_db/models/decision/common.py` — GateResultStatus (PASS/WARN/BLOCK)

### Matcher DSL (Phase 2에서 재사용)
- `src/scenario_db/matcher/runner.py` — `evaluate(rule, ctx)` — Issue.affects match_rule 평가
- `src/scenario_db/matcher/context.py` — MatcherContext — variant JSONB 필드 접근자
- `src/scenario_db/api/cache.py` — `RuleCache`, `match_issues_for_variant()` — 재사용 가능

### Phase 1 산출물 (입력 DTO)
- `src/scenario_db/db/repositories/scenario_graph.py` — CanonicalScenarioGraph DTO + Record 타입들

### Demo Fixtures (동작 이해용)
- `demo/fixtures/02_definition/uc-camera-recording.yaml` — ip_requirements, sw_requirements 예시
- `demo/fixtures/00_hw/ip-isp-v12.yaml` — IpCatalog capabilities.operating_modes 예시
- `demo/fixtures/04_decision/rule-feasibility-check.yaml` — applies_to.match + condition.match 예시
- `demo/fixtures/04_decision/rule-known-issue-match.yaml` — GateRule WARN 예시
- `demo/fixtures/04_decision/waiver-LLC-thrashing.yaml` — Waiver scope 구조 예시

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `matcher.runner.evaluate(rule, ctx)` — Issue.affects[*].match_rule 평가 → Waiver variant_scope.match_rule 평가에도 재사용 가능
- `matcher.context.MatcherContext.from_variant(variant)` — variant ORM 또는 dict에서 context 생성
- `api.cache.match_issues_for_variant(ctx, issues, scenario_id)` — scenario_id 필터 + evaluate() 통합 — Phase 2 issue matching에 직접 사용
- `models.decision.common.GateResultStatus` — PASS/WARN/BLOCK StrEnum — GateExecutionResult.status에 재사용 (WAIVER_REQUIRED 추가 필요)

### New Module Locations (Suggested)
- `src/scenario_db/resolver/` — Resolver 엔진 (ResolverResult 모델 + resolve() 함수)
- `src/scenario_db/gate/` — Gate 엔진 (GateExecutionResult 모델 + evaluate_gate() 함수 + $-DSL 평가기)

### Established Patterns
- `ConfigDict(extra='forbid')` — 모든 Pydantic 모델에 필수 (D-05, D-07 준수)
- `Field(default_factory=list)` — list 타입 필드 기본값
- 비영속 설계 — `scenario_graph.py`의 CanonicalScenarioGraph처럼 DB 저장 없음

### Integration Points
- Phase 2 출력 → Phase 3 API 라우터 (`GET /resolve`, `GET /gate`)가 CanonicalScenarioGraph + RuleCache 로드 후 Phase 2 함수 호출
- Phase 2는 Phase 1 CanonicalScenarioGraph를 입력으로 받음 — Phase 1 완료 전제

</code_context>

<specifics>
## Specific Ideas

- `$`-DSL 평가기는 fixture에서 확인한 오퍼레이터 (`$in`, `$not_empty`)를 기반으로 최소 구현
- GateRule.condition.match 스킵 시 matched_rules에 "condition_not_evaluated=True" flag 추가 고려 (Phase 3 디버깅 용이)
- `IssueStatus.open` + `IssueStatus.deferred` → 임포트 시 `from scenario_db.models.decision.issue import IssueStatus` 사용

</specifics>

<deferred>
## Deferred Ideas

- `condition.match` 평가 (evidence.resolution_result.* 참조) → Phase 3으로 이동
- `WaiverScope.execution_scope` 평가 (evidence 데이터 필요) → Phase 3으로 이동
- GateRule 평가 결과 영속화 (gate_executions 테이블) → v2 requirements (ROADMAP Out of Scope)

</deferred>

---

*Phase: 02-Resolver-Gate-Engine*
*Context gathered: 2026-05-08*
