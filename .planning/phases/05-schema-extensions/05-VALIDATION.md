---
phase: 5
slug: 05-schema-extensions
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-10
---

# Phase 5 — Validation Strategy: Schema Extensions

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/unit/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds (unit) / ~120 seconds (integration) |

---

## Sampling Rate

- **After every task commit:** `uv run pytest tests/unit/ -x -q`
- **After every plan wave:** `uv run pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** < 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-T1 | 01 | 1 | SCH-01 | — | N/A | unit | `uv run pytest tests/unit/test_schema_extensions.py -k sim_params -v` | ❌ created by this task | ⬜ pending |
| 05-01-T2 | 01 | 1 | SCH-02, SCH-03 | — | N/A | unit | `uv run pytest tests/unit/test_schema_extensions.py -k "sensor or sim_config" -v` | ❌ created by this task | ⬜ pending |
| 05-01-T3 | 01 | 1 | SCH-04 | — | N/A | unit | `uv run pytest tests/unit/test_schema_extensions.py -k "port_bw or timing" -v` | ❌ created by this task | ⬜ pending |
| 05-01-T4 | 01 | 1 | SCH-01~04 | — | N/A | unit | `uv run pytest tests/unit/test_schema_extensions.py -v` | ❌ created by this task | ⬜ pending |
| 05-02-T1 | 02 | 1 | SCH-01~04 | — | N/A | integration | `uv run pytest tests/ -q` (existing 507 still pass) | ✅ db/models.py exists | ⬜ pending |
| 05-02-T2 | 02 | 1 | SCH-05 | — | N/A | integration | `uv run alembic upgrade head && uv run alembic current` | ❌ new migration file | ⬜ pending |
| 05-03-T1 | 03 | 2 | SCH-01~04 | — | N/A | integration | `uv run pytest tests/integration/test_schema_extensions.py -v` | ❌ created by this task | ⬜ pending |
| 05-03-T2 | 03 | 2 | SCH-05 | — | N/A | integration | `uv run pytest tests/integration/test_alembic_migration.py -v` | ❌ created by this task | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Plan 05-01 Task 4가 `tests/unit/test_schema_extensions.py`를 생성한다 (Wave 0 stub 역할).
Plan 05-03 Task 2가 `tests/integration/test_alembic_migration.py`를 생성한다.

기존 pytest 인프라(pyproject.toml + conftest.py) 재사용 — 추가 Wave 0 설치 불필요.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `alembic upgrade head` on production DB | SCH-05 | 프로덕션 DB는 testcontainer 외부 — 통합 테스트로 기능은 검증 | `alembic upgrade head` 후 `alembic current` + `psql -c "\d ip_catalog"` 로 sim_params 컬럼 확인 |

---

## Validation Sign-Off

- [x] All tasks have automated verify command
- [x] Sampling continuity: 05-01(T1→T4) + 05-02(T1→T2) + 05-03(T1→T2) — 연속성 유지
- [x] Wave 0: Plan 05-01 Task 4가 test stub 생성 (Wave 1 내에서 즉시 생성)
- [x] No watch-mode flags
- [x] Feedback latency < 10s (unit suite)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending (플랜 실행 후 갱신)
