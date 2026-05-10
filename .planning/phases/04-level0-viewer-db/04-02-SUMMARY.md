---
phase: "04"
plan: "02"
subsystem: dashboard
tags: [streamlit, http-api, pipeline-viewer, level0]
dependency_graph:
  requires: [03-api]
  provides: [VIEW-01, VIEW-05]
  affects: [dashboard/pages/1_Pipeline_Viewer.py]
tech_stack:
  added: [requests==2.33.1]
  patterns: [st.cache_data, HTTP API polling, lazy gate fetch]
key_files:
  modified:
    - dashboard/pages/1_Pipeline_Viewer.py
decisions:
  - "HTTP API 연동 방식 채택: requests.get() 직접 호출, requests.Session() 금지(pickle 실패)"
  - "topology 501 핸들러 추가: Wave 2(04-03) 미구현 안내 메시지 표시"
  - "Gate fetch lazy 전략: st.toggle OFF시 /gate API 미호출"
metrics:
  duration: "25m"
  completed: "2026-05-10"
  tasks_completed: 2
  files_modified: 1
---

# Phase 4 Plan 2: Dashboard HTTP 연동 — Pipeline_Viewer.py 전면 재작성 Summary

**One-liner:** Streamlit Pipeline Viewer를 `build_sample_level0()` 직접 호출에서 FastAPI HTTP API 연동으로 전면 교체하여 실제 DB 데이터를 표시하도록 재작성.

---

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | 1_Pipeline_Viewer.py 전면 재작성 | 5d90ac9 | dashboard/pages/1_Pipeline_Viewer.py |
| 2 | Dashboard import/동작 검증 | 5d90ac9 | (검증만, 파일 변경 없음) |

---

## What Was Built

### HTTP API 연동 4개 cache 함수

```python
@st.cache_data(ttl=60)
def _fetch_scenarios(api_url: str) -> list[dict]
    # GET /api/v1/scenarios → r.json()["items"]

@st.cache_data(ttl=60)
def _fetch_variants(api_url: str, scenario_id: str) -> list[dict]
    # GET /api/v1/scenarios/{id}/variants → r.json()["items"]

@st.cache_data(ttl=60)
def _load_view(api_url: str, scenario_id: str, variant_id: str, mode: str) -> ViewResponse
    # GET /api/v1/scenarios/{id}/variants/{vid}/view?level=0&mode=...

@st.cache_data(ttl=30)
def _fetch_gate(api_url: str, scenario_id: str, variant_id: str) -> GateExecutionResult
    # GET /api/v1/scenarios/{id}/variants/{vid}/gate
```

모든 `requests.get()` 호출에 `timeout=10` 적용 (T-04-01 mitigate).

### Sidebar 구성

| 요소 | 타입 | 설명 |
|------|------|------|
| API Server | text_input | 기본값 `http://localhost:8000`, URL 변경시 `cache_data.clear()` + `st.rerun()` |
| Scenario | selectbox | `metadata_.get("name", id)` 표시명, `_fetch_scenarios()` |
| Variant | selectbox | `_fetch_variants(api_url, scenario_id)` |
| View Mode | radio | `["architecture", "topology"]` |
| Show Gate Status | toggle | OFF시 `/gate` 미호출 (lazy fetch) |
| View Level | radio | Level 0 선택됨 (Phase C 항목은 disabled 표시) |

### Mode별 visible_layers 분기

```python
ARCH_LAYERS = ["hw", "memory"]        # architecture mode
TOPO_LAYERS = ["app", "framework", "hal", "kernel", "hw"]  # topology mode
```

`render_level0(view_response=view, visible_layers=LAYERS[mode], canvas_height=660)`으로 전달.

### 에러 핸들링

- API 연결 실패: `st.error()` + `st.stop()`
- 501 HTTPError: topology mode Wave 2 미구현 안내 메시지
- Gate 조회 실패: `st.sidebar.warning()` (non-blocking)

---

## Verification Results

```
requests OK: 2.33.1
ViewResponse OK
render_level0 OK
render_inspector OK
All imports OK

PASS: build_sample_level0 not found in file
PASS: _fetch_scenarios found
PASS: _fetch_variants found
PASS: _load_view found
PASS: _fetch_gate found
PASS: ARCH_LAYERS and TOPO_LAYERS defined
PASS: text_input present
PASS: selectbox present
PASS: radio present
PASS: toggle present
All acceptance criteria verified.
```

---

## Deviations from Plan

None — plan executed exactly as written.

---

## Known Stubs

None — 이 Plan은 UI 연동 레이어만 담당. `_fetch_gate()` 함수는 구현되어 있으나 Gate overlay 렌더링(노드 색상 변경)은 04-03-PLAN에서 구현 예정. 현재는 `gate_result.status`를 sidebar caption으로만 표시.

---

## Threat Flags

없음 — 기존 Threat Model(T-04-01, T-04-02)이 모두 적용됨. 새로운 네트워크 표면 없음.

---

## Self-Check: PASSED

- [x] `dashboard/pages/1_Pipeline_Viewer.py` 파일 존재 확인
- [x] Commit `5d90ac9` 존재 확인
- [x] `build_sample_level0` import 제거 확인
- [x] 4개 cache 함수 구현 확인
- [x] `timeout=10` 모든 API 호출에 적용 확인
- [x] STATE.md, ROADMAP.md 수정 없음 (orchestrator 담당)
