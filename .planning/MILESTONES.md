# Milestones — ScenarioDB

---

## v1.0 MVP — ScenarioDB Viewer MVP & Simulation Engine

**Shipped**: 2026-05-17
**Phases**: 1-7 (7 phases, 21 plans)
**Tests**: 346 → 612 (+266)
**Timeline**: 28일 (2026-04-19 → 2026-05-17)

### Delivered

DB-backed Level 0 Pipeline Viewer + 실제 HW 파라미터 기반 BW/Power/DVFS Simulation API를 완전 구현한 초기 MVP.
하드코딩 샘플 뷰어 → DB projection으로 전환하고, FastAPI 41 endpoints + 612 tests 달성.

### Key Accomplishments

1. ETL semantic validation + CanonicalScenarioGraph DTO — DB 기반 scenario 전체 그래프 안전 조회 (8가지 FK-like 규칙)
2. Resolver + Gate Engine — IP capability matching + PASS/WARN/BLOCK/WAIVER_REQUIRED 비영속 순수 Python 판정 (29개 통합 테스트)
3. Runtime API 3개 엔드포인트 (`/graph`, `/resolve`, `/gate`) + View Router DB 연동
4. Level 0 Viewer topology mode + gate overlay UI — sample data 완전 제거, ELK 기반 SW stack 렌더링
5. Schema 확장 (IpCatalog.sim_params, Variant.sim_port_config, SimulationEvidence, Alembic 0002/0003)
6. `sim/` 패키지 9개 모듈 — BW/Power/DVFS/Timing 계산, FHD30 ISP end-to-end: 295.992 MB/s, 42.494 mW
7. `/simulation/` 5개 엔드포인트 + SHA256 params_hash 캐싱 — SAPI-01~06 전체 충족

### Requirements Coverage

- 39/39 v1 requirements COMPLETE
- Archive: `.planning/milestones/v1.0-REQUIREMENTS.md`

### Known Gaps at Close

- 6개 pre-existing test failures (Phase 7 이전부터 존재): demo fixture FHD30 variant sim_config, sw_stack topology test 3개, caplog 관련 2개
- topology mode ViewSummary metadata (period_ms, budget_ms) placeholder 값 — v1.1 개선 대상

### Archive

- ROADMAP: `.planning/milestones/v1.0-ROADMAP.md`
- Requirements: `.planning/milestones/v1.0-REQUIREMENTS.md`
- Tag: `v1.0`

---
