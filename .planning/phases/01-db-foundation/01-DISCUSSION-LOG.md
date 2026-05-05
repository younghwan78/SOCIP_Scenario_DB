# Phase 1: DB Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-06
**Phase:** 1-DB Foundation
**Areas discussed:** ETL Validation 오류 처리, CanonicalScenarioGraph 타입

---

## ETL Validation 오류 처리

| 질문 | 선택지 | 선택 |
|------|--------|------|
| 오류 발견 시 처리 방식 | Soft validation (오류 수집 후 리포트) | ✓ |
| | Strict validation (즉시 raise + 롤백) | |
| 결과 표현 방식 | ValidationReport 반환값 (errors/warnings 리스트) | ✓ |
| | logging.warning 직접 출력 | |
| 실행 시점 | load_yaml_dir() 내부에서 자동 호출 | ✓ |
| | validate_loaded() 별도 호출 | |
| 검증 범위 | FK-like 참조 전체 (8가지 규칙) | ✓ |
| | 핵심 3가지만 (scenario, variant, evidence) | |

**Notes:** 현재 ETL의 skip-and-continue SAVEPOINT 패턴과 일관성을 유지하는 soft validation 선택. ValidationReport 반환으로 테스트에서 assert 가능.

---

## CanonicalScenarioGraph 타입

| 질문 | 선택지 | 선택 |
|------|--------|------|
| DTO 타입 | Pydantic v2 모델 | ✓ |
| | @dataclass (ORM 직접 보관) | |
| 위치 | db/repositories/scenario_graph.py | ✓ |
| | models/graph.py | |
| ORM 매핑 전략 | model_validate(row.__dict__) | ✓ |
| | 팩토리 메서드 (from_orm_row) | |
| 쿼리 전략 | joinedload / selectinload 적극 사용 | ✓ |
| | 개별 Repository 메서드 조합 | |

**Notes:** 프로젝트 전체 Pydantic v2 표준과 일관성 유지. docs §4.5 제안 구조 채택.

---

## Claude's Discretion

- CanonicalScenarioGraph 내부 Record 타입 네이밍
- Issues 스코핑 세부 로직 (`issue.affects[*].scenario_ref` wildcard 처리)
- Waivers 스코핑 세부 로직
- ValidationReport 에러 메시지 포맷

## Deferred Ideas

- Issues/Waivers 스코핑 — 별도 논의 없이 Claude 재량으로 구현
- Validation CLI 통합 — 현재 auto-call로 충분, 필요 시 추후 추가
- gate_executions 영속 테이블 — STATE.md 결정에 따라 비영속 유지
