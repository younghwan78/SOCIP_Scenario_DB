---
phase: 2
plan: 2
subsystem: gate-engine
tags: [gate, dsl, pydantic, pure-function, tdd]
dependency_graph:
  requires:
    - 02-01 (ResolverResult 모델, CanonicalScenarioGraph, MatcherContext)
    - src/scenario_db/models/decision/common.py (GateResultStatus)
    - src/scenario_db/api/schemas/decision.py (GateRuleResponse)
    - src/scenario_db/matcher/runner.py (evaluate)
    - src/scenario_db/matcher/context.py (MatcherContext)
  provides:
    - evaluate_gate(graph, gate_rules) -> GateExecutionResult
    - evaluate_applies_to(match, variant) -> bool
    - GateResultStatus.WAIVER_REQUIRED
  affects:
    - Phase 3 API 라우터 (GET /gate 엔드포인트에서 evaluate_gate 호출)
tech_stack:
  added: []
  patterns:
    - TDD (RED → GREEN 순서)
    - 순수 함수 설계 (DB/SQLAlchemy 의존성 없음)
    - Sentinel 객체 패턴 (_UNKNOWN_PATH)
    - StrEnum 확장 (WAIVER_REQUIRED 추가)
key_files:
  created:
    - src/scenario_db/gate/dsl.py
    - src/scenario_db/gate/engine.py
    - tests/unit/gate/test_dsl.py
    - tests/unit/gate/test_gate_engine.py
  modified:
    - src/scenario_db/models/decision/common.py (WAIVER_REQUIRED 추가)
    - tests/unit/test_decision_models.py (test_gate_result_status_enum 업데이트)
  created_prior_session:
    - src/scenario_db/gate/__init__.py (44ade76)
    - src/scenario_db/gate/models.py (44ade76)
    - tests/unit/gate/__init__.py (44ade76)
decisions:
  - "D-04: condition.match 생략 — GateRuleMatch.condition_not_evaluated=True로 명시"
  - "D-05: $-DSL 평가기를 MatcherContext와 별개 모듈(gate/dsl.py)로 분리"
  - "D-06: applies_to=None → True (unconditional), 빈 match dict → True"
  - "D-07: evaluate_gate() 순수 함수 — Session 파라미터 없음"
  - "D-09: _WAIVER_REQUIRED_STATUSES = frozenset({'open', 'deferred'})"
  - "알 수 없는 path prefix → _UNKNOWN_PATH sentinel → _eval_op에서 True 반환 (pass-through)"
  - "T-02-05: 알 수 없는 gate_result 값 → WARN 강등 (BLOCK 조작 불가)"
metrics:
  duration: "~30분"
  completed_date: "2026-05-09"
  tasks_completed: 3
  files_created: 4
  files_modified: 2
---

# Phase 2 Plan 2: Gate 엔진 구현 Summary

**한 줄 요약:** applies_to $-DSL 평가기 + BLOCK/WAIVER_REQUIRED/WARN/PASS 우선순위 집계 순수 함수 evaluate_gate() 구현 (SQLAlchemy 의존성 없음)

## 구현한 파일 목록

### 신규 생성 (이번 세션)

| 파일 | 역할 |
|------|------|
| `src/scenario_db/gate/dsl.py` | applies_to.match $-DSL 평가기 — evaluate_applies_to(match, variant) |
| `src/scenario_db/gate/engine.py` | evaluate_gate(graph, gate_rules) 순수 함수 |
| `tests/unit/gate/test_dsl.py` | DSL 평가기 단위 테스트 19개 |
| `tests/unit/gate/test_gate_engine.py` | 엔진 단위 테스트 27개 |

### 신규 생성 (이전 세션 44ade76에서 커밋)

| 파일 | 역할 |
|------|------|
| `src/scenario_db/gate/__init__.py` | 패키지 마커 |
| `src/scenario_db/gate/models.py` | GateRuleMatch, GateExecutionResult Pydantic 모델 |
| `tests/unit/gate/__init__.py` | 테스트 패키지 마커 |

### 수정

| 파일 | 변경 내용 |
|------|----------|
| `src/scenario_db/models/decision/common.py` | GateResultStatus에 WAIVER_REQUIRED = "WAIVER_REQUIRED" 추가 |
| `tests/unit/test_decision_models.py` | test_gate_result_status_enum — WAIVER_REQUIRED 포함으로 업데이트 |

## 테스트 결과

```
tests/unit/gate/test_dsl.py          19 passed
tests/unit/gate/test_gate_engine.py  27 passed
──────────────────────────────────────────────
tests/unit/gate/ TOTAL               46 passed
tests/unit/test_decision_models.py   29 passed (regression 없음)
```

**SQLAlchemy 의존성 없음:**
```
grep -r "from sqlalchemy" src/scenario_db/gate/  → (결과 없음)
```

## 커밋 이력

| 커밋 | 내용 |
|------|------|
| 44ade76 (이전 세션) | gate 패키지 + GateResultStatus WAIVER_REQUIRED + GateExecutionResult 모델 |
| c3e5cdb | $-DSL 평가기 (gate/dsl.py) + 단위 테스트 19개 |
| (스테이징 완료) | evaluate_gate() 엔진 + 단위 테스트 27개 |

## 중요한 구현 결정사항

### 1. _UNKNOWN_PATH Sentinel 패턴 (dsl.py)

```python
class _UnknownPath:
    pass

_UNKNOWN_PATH = _UnknownPath()
```

`"evidence.*"` 같은 Phase 2 미지원 path prefix를 받았을 때, `None`을 반환하면 `$in` 오퍼레이터에서 `None not in [...]` → `False`가 되어 rule이 잘못 차단될 수 있다. Sentinel을 사용해 `_eval_op`에서 `isinstance(value, _UnknownPath) → True (pass-through)` 처리.

### 2. GateResultStatus.WAIVER_REQUIRED 경로

WAIVER_REQUIRED는 **rule 경로가 아닌 issue 경로**로만 발생한다:
- gate rule의 `action.gate_result`에 "WAIVER_REQUIRED" → `GateResultStatus("WAIVER_REQUIRED")` 성공하지만 GateRuleMatch.result에 WAIVER_REQUIRED가 들어갈 수 있음
- 실제로는 open/deferred issue + no waiver → `missing_waivers` 경로로만 발생 (D-09)
- `_aggregate_status()`에서 `missing_waivers` 유무로만 WAIVER_REQUIRED 판단

### 3. D-11 우선순위 집계 구현

```python
def _aggregate_status(matched_rules, missing_waivers) -> GateResultStatus:
    if any(r.result == BLOCK for r in matched_rules):   # 1순위
        return BLOCK
    if missing_waivers:                                   # 2순위
        return WAIVER_REQUIRED
    if any(r.result == WARN for r in matched_rules):    # 3순위
        return WARN
    return PASS                                           # 기본
```

### 4. Issue matching — affects 목록 순회

`IssueRecord.affects`는 `list[dict]` 형태. 각 항목의 `scenario_ref`가 현재 `scenario_id`와 일치하거나 `"*"` (와일드카드)이면 `match_rule`을 `MatcherContext`로 평가. 첫 번째 매칭에서 break (중복 방지).

## GateResultStatus 수정 후 기존 테스트 Regression 여부

- `test_gate_result_status_enum`이 `{"PASS", "WARN", "BLOCK"}` 하드코딩으로 실패 → Rule 1 (Bug fix)로 자동 수정
- `{"PASS", "WARN", "BLOCK", "WAIVER_REQUIRED"}`로 업데이트
- 나머지 28개 테스트 영향 없음 — StrEnum 확장이므로 기존 값 동작 유지
- 최종: 29 passed (0 failed)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_gate_result_status_enum 하드코딩 수정**
- **Found during:** Task 1 검증
- **Issue:** `assert set(GateResultStatus) == {"PASS", "WARN", "BLOCK"}` — WAIVER_REQUIRED 추가 후 실패
- **Fix:** `{"PASS", "WARN", "BLOCK", "WAIVER_REQUIRED"}`로 업데이트
- **Files modified:** `tests/unit/test_decision_models.py`
- **Commit:** 44ade76 (이전 세션)

**2. [Rule 2 - Enhancement] _UNKNOWN_PATH Sentinel 패턴 추가**
- **Found during:** Task 2 설계 시
- **Issue:** `None` 반환 시 `$in` 오퍼레이터에서 미지원 path가 False로 처리될 수 있음
- **Fix:** `_UnknownPath` sentinel 클래스 + `_eval_op`에서 `isinstance` 체크 추가
- **Files modified:** `src/scenario_db/gate/dsl.py`
- **Commit:** c3e5cdb

## Known Stubs

없음 — 모든 구현이 실제 로직으로 완성됨. Phase 3 미지원 기능(condition.match, execution_scope)은 의도적으로 생략(D-04, D-10)이며 `condition_not_evaluated=True` 플래그로 추적 가능.

## Threat Flags

없음 — 모든 신규 코드는 순수 함수 내부에서만 동작. Phase 3 API 노출 시 T-02-06(message_template 원본 노출) 재검토 권장.

## Self-Check: PASSED

- `src/scenario_db/gate/dsl.py` — 존재
- `src/scenario_db/gate/engine.py` — 존재
- `tests/unit/gate/test_dsl.py` — 존재
- `tests/unit/gate/test_gate_engine.py` — 존재
- `uv run pytest tests/unit/gate/ -x -q` — 46 passed
- `grep -r "from sqlalchemy" src/scenario_db/gate/` — 결과 없음
- `GateResultStatus.WAIVER_REQUIRED == "WAIVER_REQUIRED"` — True
