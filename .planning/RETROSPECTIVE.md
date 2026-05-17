# Retrospective — ScenarioDB

---

## Milestone: v1.0 MVP — ScenarioDB Viewer MVP & Simulation Engine

**Shipped:** 2026-05-17
**Phases:** 7 | **Plans:** 21 | **Timeline:** 28일 (2026-04-19 → 2026-05-17)

### What Was Built

1. ETL semantic validation + CanonicalScenarioGraph DTO (Phase 1)
2. 비영속 Resolver + Gate Engine PASS/WARN/BLOCK/WAIVER_REQUIRED (Phase 2)
3. Runtime API 3개 엔드포인트 + View Router DB 연동 (Phase 3)
4. Level 0 Viewer topology mode + gate overlay UI, sample data 완전 제거 (Phase 4)
5. IpCatalog/Variant/SimulationEvidence 스키마 확장 + Alembic 0002 (Phase 5)
6. sim/ 패키지 9개 모듈 — BW/Power/DVFS/Timing 계산 (Phase 6)
7. /simulation/ 5개 엔드포인트 + SHA256 params_hash 캐싱 (Phase 7)

### What Worked

- **TDD RED→GREEN 사이클**: Phase 7 전체, Phase 6 PLAN-03에서 엄격하게 적용 — 테스트 먼저 작성 후 구현, 회귀 없음
- **Wave-based parallel planning**: Phase 내 Wave 1 (병렬) → Wave 2 (의존성) 분리로 의존성 명확화
- **D-01 단일 정의 원칙**: PortBWResult/IPTimingResult 재정의 없이 re-import — 순환 import 미발생
- **monkeypatch 전략 (Phase 7)**: DVFS YAML 파일 없이 통합 테스트 — 테스트 환경 의존성 격리 성공
- **Pydantic v2 extra='forbid' 강제**: 미정의 필드 조기 오류 포착 — 잠재 버그 다수 사전 차단
- **수동 6-쿼리 전략 (Phase 1)**: ORM relationship 없이 명시적 배치 쿼리 — 쿼리 동작 예측 가능

### What Was Inefficient

- **pre-existing test failures 6개**: Phase 7 완료 시점에도 존재 — 초기에 픽스하지 않아 매 phase마다 "기존 실패 6개" 메모 필요
- **topology mode ViewSummary placeholder**: Phase 4에서 placeholder 채택 후 v1.0 종료까지 미해소 — 다음 milestone 초기에 처리 필요
- **OTF required_clock 기대값 오산**: Phase 6-03에서 533MHz → 400MHz 수정 — 공식 검증이 계획 단계에서 이뤄졌으면 GREEN 단계 수정 불필요
- **Phase 5 + 6 + 7 동시 실행**: Alembic migration 의존성(0002 → 0003)으로 phase 순서 강제 — schema 설계를 Phase 5에서 더 완전하게 했으면 분리 효율 향상 가능

### Patterns Established

- **Soft validation 패턴**: validate_loaded() — 오류 수집 후 리포트, DB 상태 유지 (ETL 표준)
- **repository 캡슐화**: ORM 쿼리를 service 레이어에서 분리 — find_by_params_hash() 패턴
- **JSONB 필드 serialize**: `model_dump(exclude_none=True)` 패턴 — `vars()` / `__dict__` 금지
- **Alembic 수동 작성**: autogenerate 금지, `op.add_column()` 명시 — 마이그레이션 의도 명확
- **testcontainers 통합 테스트**: session-scoped engine fixture — testcontainer 1회 기동

### Key Lessons

- **pre-existing failures는 초기에 처리**: 매 phase 종료 시 "기존 실패 N개" 노트는 기술 부채 누적 신호 — v1.1 시작 시 즉시 처리
- **placeholder는 명시적으로 기록**: Known Stubs 섹션에 기록했지만 milestone 종료 전 해소 목표 설정 필요
- **공식/계산값 검증은 계획 단계에서**: OTF required_clock 오산처럼 Golden 값 사전 계산이 GREEN 단계 수정을 줄임
- **D-01 단일 정의 원칙은 초기 설계에서 확립**: Phase 6에서 결정되어 좋았으나, Phase 5 설계 시점에 정의했으면 sim/ 모듈 구조 더 명확

### Cost Observations

- Sessions: v1.0 전체 28일 — 집중 개발 (2주 단위 sprint 2회)
- Model mix: Claude Sonnet 4.6 (claude-sonnet-4-6)
- Notable: Phase 4 ELK viewer 구현에서 git reset --hard가 필요한 worktree 초기화 이슈 발생 — worktree 관리 주의 필요

---

## Cross-Milestone Trends

| Milestone | Phases | Tests | Days | Key Achievement |
|-----------|--------|-------|------|-----------------|
| v1.0 MVP | 7 | 346→612 | 28 | DB Viewer + Simulation API 완성 |
