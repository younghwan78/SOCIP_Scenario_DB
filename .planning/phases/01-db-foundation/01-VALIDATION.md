---
phase: 1
slug: db-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-06
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (설치됨, testcontainers 포함) |
| **Config file** | `pyproject.toml` (기존 markers: `integration`) |
| **Quick run command** | `uv run pytest tests/unit/ -q` |
| **Integration run command** | `uv run pytest tests/integration/ -q -m integration` |
| **Full suite command** | `uv run pytest tests/ -q` |
| **Estimated runtime** | unit: ~5s / integration: ~30s (testcontainers PG spin-up 포함) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/ -q`
- **After every plan wave:** Run `uv run pytest tests/integration/ -q -m integration`
- **Before `/gsd-verify-work`:** `uv run pytest tests/ -q` — 기존 209개 + 신규 모두 green
- **Max feedback latency:** unit ~5s / integration ~30s

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| validate_loaded unit | 01 | 1 | DB-01 | — | SQLAlchemy parameterized query only | unit | `uv run pytest tests/unit/test_validate_loaded.py -x -q` | ❌ W0 | ⬜ pending |
| validate_loaded integration | 01 | 1 | DB-01 | — | demo fixtures 로드 후 errors==[] | integration | `uv run pytest tests/integration/test_validate_loaded.py -x -q -m integration` | ❌ W0 | ⬜ pending |
| loader.py 통합 | 01 | 1 | DB-01 | — | load_yaml_dir() 후 validation 자동 실행 | integration | `uv run pytest tests/integration/test_validate_loaded.py::test_load_triggers_validation -x -q -m integration` | ❌ W0 | ⬜ pending |
| CanonicalScenarioGraph DTO round-trip | 02 | 1 | DB-02 | — | Pydantic extra='forbid' 위반 없음 | unit | `uv run pytest tests/unit/test_scenario_graph_models.py -x -q` | ❌ W0 | ⬜ pending |
| get_canonical_graph happy path | 02 | 2 | DB-02 | — | SELECT only, parameterized | integration | `uv run pytest tests/integration/test_scenario_graph.py::test_canonical_graph_demo_scenario -x -q -m integration` | ❌ W0 | ⬜ pending |
| get_canonical_graph not found | 02 | 2 | DB-02 | — | None 반환, 예외 없음 | integration | `uv run pytest tests/integration/test_scenario_graph.py::test_canonical_graph_not_found -x -q -m integration` | ❌ W0 | ⬜ pending |
| view_projection 쿼리 | 03 | 2 | DB-03 | — | SELECT only, parameterized | integration | `uv run pytest tests/integration/test_view_projection.py -x -q -m integration` | ❌ W0 | ⬜ pending |
| 기존 regression | — | all | — | — | 기존 209개 테스트 영향 없음 | unit+integration | `uv run pytest tests/ -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_validate_loaded.py` — ValidationReport 로직 단위 테스트 (DB-01): missing project_ref, missing scenario_id, wildcard `*` issue, gate_rule 형식 오류
- [ ] `tests/integration/test_validate_loaded.py` — demo fixtures 로드 후 validate_loaded 통합 테스트 (DB-01)
- [ ] `tests/unit/test_scenario_graph_models.py` — CanonicalScenarioGraph Pydantic round-trip (DB-02)
- [ ] `tests/integration/test_scenario_graph.py` — get_canonical_graph 통합 테스트 (DB-02, DB-03)
- [ ] `tests/integration/test_view_projection.py` — view_projection 쿼리 통합 테스트 (DB-03)

*Note: 기존 test 인프라(conftest.py, testcontainers, pytest markers) 재사용. 신규 패키지 설치 불필요.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| logger.warning() 출력 확인 | DB-01 | log output은 pytest capture 외부 | `uv run python -m scenario_db.etl.demo` 실행 후 WARNING 로그 확인 |
| FHD30-SDR-H265 fixture 추가 여부 | DB-02 | acceptance criteria vs. fixture gap — 결정 필요 | Wave 0에서 fixture 추가 또는 criteria 조정 후 integration test로 자동화 가능 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s (integration), < 5s (unit)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
