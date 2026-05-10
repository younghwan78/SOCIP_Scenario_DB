---
phase: 4
slug: 04-level0-viewer-db
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-10
---

# Phase 4 — Validation Strategy: Level 0 Viewer DB

> Per-phase validation contract: VIEW-01~VIEW-05 전체 커버리지 확인. Nyquist 갭 채우기 완료.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | `pyproject.toml` (testpaths = ["tests/unit"]) |
| **Quick run command** | `uv run pytest tests/unit/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -q` |
| **Estimated runtime** | ~4 seconds (507 tests) |

---

## Sampling Rate

- **After every task commit:** `uv run pytest tests/unit/ -x -q`
- **After every plan wave:** `uv run pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** < 10 seconds (unit) / < 120 seconds (integration with testcontainer)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| 04-01-T1 | 01 | Wave1A | VIEW-02 | unit | `uv run pytest tests/unit/test_pipeline_sw_stack.py -v` | ✅ green |
| 04-01-T2 | 01 | Wave1A | VIEW-02 | unit | `uv run pytest tests/unit/test_pipeline_sw_stack.py -v` | ✅ green |
| 04-01-T3 | 01 | Wave1A | VIEW-02 | unit | `uv run pytest tests/unit/test_view_service.py -v` | ✅ green |
| 04-01-T4 | 01 | Wave1A | VIEW-02 | unit | `uv run pytest tests/unit/test_view_service.py -v` | ✅ green |
| 04-02-T1 | 02 | Wave1B | VIEW-01, VIEW-05 | integration | `uv run pytest tests/integration/test_api_runtime.py -v` | ✅ green |
| 04-03-T1 | 03 | Wave2 | VIEW-03 | unit | `uv run pytest tests/unit/test_view_service.py::test_sw_stack_result_contains_sw_nodes -v` | ✅ green |
| 04-03-T2 | 03 | Wave2 | VIEW-04 | unit | `uv run pytest tests/unit/test_node_detail_panel.py tests/unit/test_elk_graph_builder.py -v` | ✅ green |
| 04-03-T3 | 03 | Wave2 | VIEW-03, VIEW-04 | integration | `uv run pytest tests/integration/test_view_topology.py -v` | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Requirement Coverage Map

| Requirement | Description | Test Files | Coverage |
|-------------|-------------|-----------|----------|
| VIEW-01 | `project_level0(db, ...)` DB 렌더링, sample data 없음 | `test_api_runtime.py` (view_architecture_mode, view_architecture_404), `test_view_service.py` (no_stub_positions) | **COVERED** |
| VIEW-02 | Architecture mode HW IP + AXI bus lane DB 구동 | `test_view_service.py` (9 tests: lane, x/y coords, edges, unknown_category), `test_view_topology.py` (architecture_mode_still_works) | **COVERED** |
| VIEW-03 | Topology mode SW stack 레인 렌더링 | `test_view_topology.py` (6 tests: sw_nodes, control_edges, mode_field, sw_stack_ids), `test_view_service.py` (4 G2 tests: sw nodes, control edges, collision skip, mode=topology) | **COVERED** |
| VIEW-04 | Inspector 패널 GateExecutionResult 표시 | `test_node_detail_panel.py` (5 tests: PASS/BLOCK badge, issues, rules, waivers), `test_elk_graph_builder.py` (5 tests: gate_styles PASS/BLOCK/None override) | **COVERED** |
| VIEW-05 | mode radio selector UI → 레이아웃 전환 | API 레벨: `test_api_runtime.py` (view_architecture_mode + view_topology_mode_returns_200), `test_view_topology.py` (architecture_mode_still_works) / Streamlit UI: manual-only | **PARTIAL** |

---

## Nyquist Gap Audit (2026-05-10)

| Gap | Status Before | Status After | Test File | Tests Added |
|-----|---------------|--------------|-----------|-------------|
| G1: `render_gate_inspector()` 미테스트 | MISSING | COVERED | `tests/unit/test_node_detail_panel.py` | 5 |
| G2: `_sw_stack_to_view_response()` 단위 미테스트 | PARTIAL | COVERED | `tests/unit/test_view_service.py` (추가) | 4 |
| G3: Streamlit radio selector UI 전환 | MANUAL | MANUAL | — | 0 |
| G4: `build_elk_graph(gate_styles=...)` 단위 미테스트 | PARTIAL | COVERED | `tests/unit/test_elk_graph_builder.py` | 5 |

**총 14개 테스트 추가. Final suite: 507 passed, 0 failed.**

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Streamlit radio selector `mode=architecture\|topology` UI 전환 | VIEW-05 | Streamlit UI 자동화 불가 (헤드리스 실행 시 widget 상태 불일치) | 1. `uv run streamlit run dashboard/Home.py` 실행<br>2. 사이드바에서 scenario/variant 선택<br>3. View Mode radio를 `topology`로 전환<br>4. SW stack 레인(app/framework/hal/kernel)이 표시됨 확인<br>5. `architecture`로 전환 시 HW/memory 레인만 표시됨 확인 |
| Gate Inspector 패널 브라우저 렌더링 | VIEW-04 | Streamlit UI 자동화 불가 | 1. `Show Gate Status` toggle ON<br>2. Gate Inspector 패널에서 status badge 색상 확인 (PASS=회색, WARN=노랑, BLOCK=빨강, WAIVER_REQUIRED=보라)<br>3. matched_issues, matched_rules risk card 표시 확인 |

---

## Wave 0 Requirements

기존 pytest 인프라(pyproject.toml + conftest.py)가 모든 Phase 4 요구사항을 커버. 추가 Wave 0 설치 불필요.

`tests/unit/conftest.py` — dashboard 모듈 경로(`sys.path`) 추가 (Nyquist 갭 채우기 시 신규 생성).

---

## Validation Audit 2026-05-10

| Metric | Count |
|--------|-------|
| Requirements analyzed | 5 (VIEW-01~VIEW-05) |
| Gaps found | 4 (G1 MISSING, G2 PARTIAL, G3 manual, G4 PARTIAL) |
| Resolved (automated) | 3 (G1, G2, G4) |
| Escalated to manual-only | 1 (G3 Streamlit UI) |
| Tests added | 14 |
| Final suite size | 507 |

---

## Validation Sign-Off

- [x] All VIEW-01~VIEW-05 requirements have automated verify or manual-only rationale
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0: existing infrastructure covers all phase requirements
- [x] No watch-mode flags
- [x] Feedback latency < 10s (unit suite)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-10
