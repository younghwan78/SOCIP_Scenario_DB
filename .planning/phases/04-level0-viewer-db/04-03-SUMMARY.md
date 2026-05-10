---
phase: "04"
plan: "03"
subsystem: "view-service + dashboard"
tags: [topology-mode, gate-overlay, sw-stack, elk-viewer, integration-tests]
dependency_graph:
  requires: [04-01, 04-02]
  provides: [VIEW-03, VIEW-04]
  affects:
    - src/scenario_db/view/service.py
    - dashboard/components/elk_graph_builder.py
    - dashboard/components/elk_viewer.py
    - dashboard/components/node_detail_panel.py
    - dashboard/pages/1_Pipeline_Viewer.py
tech_stack:
  added: []
  patterns:
    - "_sw_stack_to_view_response(): sw_stack YAML → ViewResponse (topology mode)"
    - "gate_styles={'__global__': status}: 전역 gate 상태를 HW 노드 border 오버라이드"
    - "render_gate_inspector(): GateExecutionResult → status badge + risk card"
key_files:
  modified:
    - src/scenario_db/view/service.py
    - dashboard/components/elk_graph_builder.py
    - dashboard/components/elk_viewer.py
    - dashboard/components/node_detail_panel.py
    - dashboard/pages/1_Pipeline_Viewer.py
    - tests/integration/test_api_runtime.py
  created:
    - tests/integration/test_view_topology.py
decisions:
  - "_sw_stack_to_view_response(): HW 노드는 _projection_to_view_response() 재사용 (좌표 동일)"
  - "gate_styles 전달 방식: {'__global__': status} — 노드별 per-node 매핑 없음 (Pattern 3)"
  - "topology 501 테스트 업데이트: Wave 1B 임시 테스트 → 200 검증으로 전환 (Rule 1 fix)"
metrics:
  duration: "35m"
  completed: "2026-05-10"
  tasks_completed: 5
  files_changed: 7
---

# Phase 4 Plan 3: Topology Mode + Gate Overlay + 통합 테스트 Summary

**One-liner:** `_sw_stack_to_view_response()`로 YAML sw_stack → topology ViewResponse를 구현하고, `gate_styles` 파라미터로 gate 상태에 따른 HW 노드 border 오버라이드 + `render_gate_inspector()`로 인스펙터 패널에 GateExecutionResult 표시.

---

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | service.py topology mode 구현 | 4f5fcf6 | src/scenario_db/view/service.py |
| 2 | elk_graph_builder + elk_viewer gate_styles 지원 | 27f593d | dashboard/components/elk_graph_builder.py, elk_viewer.py |
| 3 | node_detail_panel Gate 인스펙터 + 1_Pipeline_Viewer 연동 | 3a3405a | dashboard/components/node_detail_panel.py, dashboard/pages/1_Pipeline_Viewer.py |
| 4 | 통합 테스트 test_view_topology.py | 76c23c7 | tests/integration/test_view_topology.py |
| 5 | 전체 테스트 스위트 통과 + outdated test fix | a1f39bf | tests/integration/test_api_runtime.py |

---

## What Was Built

### Task 1: `_sw_stack_to_view_response()` 구현 (4f5fcf6)

`src/scenario_db/view/service.py`에 신규 추가:

- `_sw_stack_to_view_response(projection: dict) -> ViewResponse`
  - `projection["pipeline"]["sw_stack"]` → SW 노드 생성
  - layer별 x 누적 배치: `X_START=235px`, `X_STEP=180px`
  - y좌표: `LANE_Y[layer]` (layout.py 기존 상수 재사용)
  - `ip_ref` 있는 SW 노드 → HW 노드 방향 `flow_type="control"` 엣지 생성
  - HW 노드: `_projection_to_view_response()` 재사용 (동일 좌표)
  - `ViewResponse(mode="topology", ...)` 반환

- `project_level0()` 수정:
  - topology NotImplementedError 제거
  - `mode == "topology"` → `_sw_stack_to_view_response(projection)` 호출

### Task 2: `gate_styles` 파라미터 추가 (27f593d)

`dashboard/components/elk_graph_builder.py`:
- `build_elk_graph()` 시그니처: `gate_styles: dict[str, str] | None = None` 추가
- `GATE_BORDER` 상수: PASS/WARN/BLOCK/WAIVER_REQUIRED → border 색상 매핑
- `_build_meta()`: `gate_styles={"__global__": status}` 있으면 ip 타입 노드 border/warning 오버라이드
- `build_view_layout()` backward-compat alias 추가 (gate_styles 지원)

`dashboard/components/elk_viewer.py`:
- `render_level0()` 시그니처: `gate_styles: dict[str, str] | None = None` 추가
- `build_elk_graph()` 호출 시 gate_styles 전달

### Task 3: `render_gate_inspector()` + Pipeline_Viewer 연동 (3a3405a)

`dashboard/components/node_detail_panel.py`:
- `_GATE_STATUS_STYLE` 상수: PASS/WARN/BLOCK/WAIVER_REQUIRED 색상 딕셔너리
- `render_gate_inspector(gate)` 신규 함수:
  - status badge (border/bg/text 색상 구분)
  - matched_issues 목록 (빨간 badge)
  - missing_waivers 목록 (보라 badge)
  - matched_rules risk card 형태 (rule_id + message)

`dashboard/pages/1_Pipeline_Viewer.py`:
- `gate_styles_param = {"__global__": str(gate_result.status)}` → `render_level0()` 전달
- `inspector_col`에서 `render_gate_inspector(gate_result)` 호출 (toggle ON 시)

### Task 4: 통합 테스트 (76c23c7)

`tests/integration/test_view_topology.py` 신규 생성 (6개 테스트):
- `test_topology_view_returns_200`: 200 응답 확인
- `test_topology_view_has_sw_nodes`: SW 노드(app/framework/hal/kernel) 포함 확인
- `test_topology_view_has_control_edges`: SW→HW control 엣지 포함 확인
- `test_topology_mode_field`: `ViewResponse.mode="topology"` 확인
- `test_architecture_mode_still_works`: architecture mode 회귀 테스트
- `test_sw_stack_node_ids_in_topology`: sw_stack id(app-camera, fw-cam-svc 등) 포함 확인

### Task 5: 전체 테스트 통과 (a1f39bf)

- 492 tests 전체 통과 (326 unit + 166 integration)
- Wave 1B 임시 테스트 `test_view_topology_mode_returns_501` → `test_view_topology_mode_returns_200`으로 업데이트 (Rule 1 fix)

---

## Test Results

```
326 unit tests passed
166 integration tests passed (including 6 new topology tests)
492 total — 0 failed
```

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_api_runtime.py outdated 501 테스트 수정**
- **Found during:** Task 5 전체 테스트 실행
- **Issue:** `test_view_topology_mode_returns_501` — Wave 1B에서 topology mode 미구현 상태를 가정한 임시 테스트가 Wave 2(04-03) 구현 후 실패
- **Fix:** `test_view_topology_mode_returns_200`으로 rename + 200 응답 + `mode="topology"` 필드 검증 강화
- **Files modified:** `tests/integration/test_api_runtime.py`
- **Commit:** `a1f39bf`

### Context Discovery

- **worktree 초기화 필요:** `git reset --hard c3c1e4b` 수행으로 Wave 1(04-01, 04-02) 커밋들이 반영됨. `elk_viewer.py`, `elk_graph_builder.py` 등이 reset 후에야 존재했음.

---

## Known Stubs

- `ViewSummary.period_ms`, `budget_ms`, `resolution`, `fps`, `variant_label`: topology mode에서 0.0/"" placeholder — DB projection에서 variant 메타데이터 조회 미구현. 현재는 `subtitle="topology mode"` 표시. VIEW-01 fully-completed 이후 보완 가능.
- `render_gate_inspector()`: GateExecutionResult 전체를 표시하나, 특정 노드와 issue의 매핑은 없음 (RESEARCH.md Pattern 3 — 실용적 접근 채택, gate 전체 status만 overlay).

---

## Threat Flags

없음 — 기존 Threat Model(T-04-03, T-04-04) 범위 내. 신규 네트워크 엔드포인트 없음.

---

## Self-Check: PASSED

- [x] `src/scenario_db/view/service.py` — `_sw_stack_to_view_response()` 존재
- [x] `project_level0(mode="topology")` → 200 반환 (NotImplementedError 없음)
- [x] `dashboard/components/elk_graph_builder.py` — `gate_styles` 파라미터 + GATE_BORDER 상수
- [x] `dashboard/components/elk_viewer.py` — `render_level0(gate_styles=...)` 지원
- [x] `dashboard/components/node_detail_panel.py` — `render_gate_inspector()` 존재
- [x] `dashboard/pages/1_Pipeline_Viewer.py` — gate overlay + render_gate_inspector() 연동
- [x] `tests/integration/test_view_topology.py` — 6 tests, all passed
- [x] `uv run pytest tests/ -x -q` — 492 passed, 0 failed
- [x] Commit 4f5fcf6 존재 (Task 1)
- [x] Commit 27f593d 존재 (Task 2)
- [x] Commit 3a3405a 존재 (Task 3)
- [x] Commit 76c23c7 존재 (Task 4)
- [x] Commit a1f39bf 존재 (Task 5 fix)
- [x] STATE.md, ROADMAP.md 수정 없음 (orchestrator 담당)
