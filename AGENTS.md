# AGENTS.md — ScenarioDB Project

## Project Context
- SoC Multimedia Scenario DB 구축 프로젝트
- 설계 문서: docs/scenario-db-yaml-design-v2.2.md (반드시 먼저 읽을 것)
- 목표: v2.2 YAML 스키마를 Pydantic v2 모델로 구현

## Architecture (v2.2 핵심)
- 4-Layer 분리: Capability / Definition / Evidence / Decision
- 3-경계선 원칙:
  1. Variant ≠ Instance (design_axes vs execution_axes)
  2. Capability ≠ Requirement (HW/SW 추상 mode vs scenario 요구사항)
  3. Canonical ≠ Derived (YAML authored vs DB materialized)

## Tech Stack
- Python 3.11+
- Pydantic v2
- PyYAML (YAML 파싱)
- pytest (테스트)

## Coding Conventions
- 모든 Pydantic 모델은 `model_config = ConfigDict(extra='forbid')`
- Field alias는 YAML 키와 정확히 일치
- Enum은 str subclass 사용 (YAML serialize 용이)
- Discriminated Union은 Literal kind 필드 사용

## Working Mode (IMPORTANT)
- 구현 전 반드시 plan 제시 후 승인 받기
- 한 번에 한 레이어씩 구현 (Capability → Definition → Evidence → Decision)
- 모든 Pydantic 모델에 pytest fixture + round-trip test 작성
- YAML 예시는 설계 문서 §8-§17 참고

# 코드 수정 규칙

## 필수 원칙
코드를 수정하기 전에 반드시 파일을 먼저 읽어라
- 맥락을 파악한 후 edit 실행
- 추측으로 코드를 수정하지 말 것
- Read 도구로 파일 전체를 확인
