# Phase 2: Resolver & Gate Engine — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-08
**Phase:** 02-Resolver-Gate-Engine
**Areas discussed:** Mode Matching 알고리즘, GateRule 평가 범위, Gate Engine 입력 설계, WAIVER_REQUIRED 트리거 조건

---

## Mode Matching 알고리즘 (RES-02)

### Q1: IP mode matching 알고리즘

| Option | Description | Selected |
|--------|-------------|----------|
| First-fit | 정의 순서대로 첫 번째 조건 충족 모드 선택 | |
| Best-fit (min headroom) | 충족 모드 중 요구치와 가장 가까운 것 선택 | |
| All-matching modes | 충족하는 모든 모드 리스트 반환 | ✓ |

**User's choice:** All-matching modes
**Notes:** Gate/선택 로직은 downstream이 담당. `matched_modes: [normal, high_throughput]` 형태로 반환

### Q2: required_* 필드 대응 ip_catalog 필드 없는 경우 처리

| Option | Description | Selected |
|--------|-------------|----------|
| strict: unresolved_requirements에 기록 | 대응 필드 없거나 값 불일치 → unresolved | ✓ |
| lenient: 대응 필드 없으면 skip (warn only) | 무시하고 warning만 기록 | |

**User's choice:** strict

### Q3: matched_modes 비어있는 경우 (모든 모드 불일치)

| Option | Description | Selected |
|--------|-------------|----------|
| unresolved_requirements로 이동 | ip_ref를 unresolved에 추가, fallback 없음 | ✓ |
| fallback: 가장 가까운 모드 + 경고 | 최대 throughput 모드를 matched로 리포트하되 경고 | |

**User's choice:** unresolved_requirements로 이동

---

## GateRule 평가 범위 (GATE-02)

### Q1: condition.match 평가 전략

| Option | Description | Selected |
|--------|-------------|----------|
| applies_to만 평가, condition 스킵 | applies_to 매칭 시 action.gate_result 직접 사용 | ✓ |
| condition도 구현 (부분 평가) | evidence 참조 키는 None, non-evidence 키만 평가 | |
| GateRule 평가 전체를 Phase 3으로 지연 | Phase 2는 Issue + Waiver만 처리 | |

**User's choice:** applies_to만 평가, condition 스킵

### Q2: applies_to.match 평가기 구현 전략

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 2용 경량 $-DSL 평가기 신규 구현 | variant.severity, variant.design_conditions.* 지원 | ✓ |
| applies_to None 아니면 항상 match로 간주 | 모든 rule이 variant에 적용된다고 가정 | |

**User's choice:** Phase 2용 경량 $-DSL 평가기 신규 구현

---

## Gate Engine 입력 설계

### Q1: GateRules 수신 방식

| Option | Description | Selected |
|--------|-------------|----------|
| GateRule 리스트를 별도 파라미터로 | evaluate_gate(graph, gate_rules) 순수 함수 | ✓ |
| GateEngine이 내부에서 RuleCache 직접 사용 | GateEngine 생성 시 RuleCache 주입 | |
| CanonicalScenarioGraph에 GateRules 포함 | Phase 1 CanonicalScenarioGraph 확장 | |

**User's choice:** GateRule 리스트를 별도 파라미터로

### Q2: Resolver-Gate 의존성

| Option | Description | Selected |
|--------|-------------|----------|
| Gate는 Resolver로부터 독립 | evaluate_gate(graph, gate_rules), Resolver 불필요 | ✓ |
| Gate는 Resolver 다음에 단계 | evaluate_gate(resolver_result, graph, gate_rules) | |

**User's choice:** Gate는 Resolver로부터 독립

---

## WAIVER_REQUIRED 트리거 조건 (GATE-04)

### Q1: WAIVER_REQUIRED 발생 조건

| Option | Description | Selected |
|--------|-------------|----------|
| open + deferred 이슈만 | status=open 또는 deferred + waiver 없음 | ✓ |
| severity 기준 (heavy/critical만) | severity >= heavy인 open issue만 | |
| 매칭된 모든 issue (status 무관) | resolved/wontfix도 포함 | |

**User's choice:** open + deferred 이슈만

### Q2: Waiver 적용 가능성 판단

| Option | Description | Selected |
|--------|-------------|----------|
| variant_scope 평가, execution_scope 스킵 | MatcherContext 재사용, execution_scope는 Phase 3 | ✓ |
| variant_scope + execution_scope 모두 평가 | evidence 참조 항목은 selective skip | |

**User's choice:** variant_scope 평가, execution_scope 스킵

---

## Claude's Discretion

- Module 배치: `src/scenario_db/resolver/` + `src/scenario_db/gate/` (researcher/planner가 결정)
- `GateResultStatus` StrEnum에 `WAIVER_REQUIRED` 추가 위치 (common.py vs gate/models.py)
- `$`-DSL 평가기 세부 지원 오퍼레이터 범위 (fixture 기반으로 최소 구현)

## Deferred Ideas

- condition.match 평가 (evidence.resolution_result.* 참조) → Phase 3
- WaiverScope.execution_scope 평가 → Phase 3
- GateRule 결과 영속화 (gate_executions 테이블) → v2 requirements
