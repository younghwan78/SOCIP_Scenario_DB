# Phase 4: Level 0 Viewer DB — Pattern Map

**Mapped:** 2026-05-10
**Files analyzed:** 8 (3 new + 5 modified)
**Analogs found:** 8 / 8

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tests/unit/test_view_service.py` | test | request-response | `tests/unit/test_definition_models.py` | role-match |
| `tests/integration/test_view_topology.py` | test | request-response | `tests/integration/test_api_runtime.py` | exact |
| `tests/unit/test_pipeline_sw_stack.py` | test | CRUD | `tests/unit/test_definition_models.py` | exact |
| `dashboard/pages/1_Pipeline_Viewer.py` | component | request-response | `dashboard/Home.py` + `dashboard/pages/1_Pipeline_Viewer.py` (현재) | exact |
| `dashboard/components/elk_viewer.py` | component | transform | `dashboard/components/elk_viewer.py` (현재) | self |
| `dashboard/components/node_detail_panel.py` | component | CRUD | `dashboard/components/node_detail_panel.py` (현재) | self |
| `src/scenario_db/view/service.py` | service | CRUD | `src/scenario_db/view/service.py` (현재) | self |
| `src/scenario_db/models/definition/usecase.py` | model | CRUD | `src/scenario_db/models/definition/usecase.py` (현재) | self |

---

## Pattern Assignments

### `tests/unit/test_view_service.py` (test, request-response)

**Analog:** `tests/unit/test_definition_models.py`

**Imports pattern** (lines 1-17 of analog):
```python
from __future__ import annotations
from pathlib import Path
import pytest
import yaml
from pydantic import ValidationError

from scenario_db.view.service import _projection_to_view_response, build_sample_level0
from scenario_db.view.layout import LANE_Y, STAGE_X
from scenario_db.api.schemas.view import ViewResponse
```

**No DB / No fixture 패턴** — unit test이므로 conftest 없이 raw dict를 직접 구성:
```python
# 테스트 전용 최소 projection dict
_SAMPLE_PROJECTION = {
    "scenario_id": "uc-camera-recording",
    "variant_id":  "UHD60-HDR10-H265",
    "project_name": "Camera Recording",
    "pipeline": {
        "nodes": [
            {"id": "csis0", "ip_ref": "ip-csis-v8"},
            {"id": "isp0",  "ip_ref": "ip-isp-v12"},
            {"id": "mfc",   "ip_ref": "ip-mfc-v14"},
        ],
        "edges": [
            {"from": "csis0", "to": "isp0", "type": "OTF"},
            {"from": "isp0",  "to": "mfc",  "type": "M2M"},
        ],
    },
    "ip_catalog": [
        {"id": "ip-csis-v8",  "category": "camera"},
        {"id": "ip-isp-v12",  "category": "camera"},
        {"id": "ip-mfc-v14",  "category": "codec"},
    ],
    "lanes": [],
}
```

**Core pattern** — VIEW-02 좌표 계산 검증:
```python
def test_architecture_mode_nodes_have_real_coords():
    view = _projection_to_view_response(_SAMPLE_PROJECTION)
    pos = {n.data.id: n.position for n in view.nodes}
    # 모든 노드가 x=0.0, y=0.0 stub이 아닌 실좌표여야 함
    for node_id, p in pos.items():
        assert p["x"] != 0.0 or p["y"] != 0.0, f"{node_id} still at stub 0,0"

def test_csis_before_isp_in_x():
    """topological sort 결과: csis0(stage 0) < isp0(stage 1) → x_csis < x_isp."""
    view = _projection_to_view_response(_SAMPLE_PROJECTION)
    pos = {n.data.id: n.position for n in view.nodes}
    assert pos["csis0"]["x"] < pos["isp0"]["x"]

def test_lane_assignment_camera_to_hw():
    """camera category → hw 레인 → LANE_Y["hw"]."""
    from scenario_db.view.layout import LANE_Y
    view = _projection_to_view_response(_SAMPLE_PROJECTION)
    hw_nodes = {n.data.id for n in view.nodes if n.data.layer == "hw"}
    assert "csis0" in hw_nodes
    assert "isp0"  in hw_nodes
```

**Divergence from analog:** analog은 YAML 파일에서 로드하지만, 이 파일은 in-memory dict를 직접 사용. `pytestmark = pytest.mark.integration` 없이 순수 unit test.

---

### `tests/integration/test_view_topology.py` (test, request-response)

**Analog:** `tests/integration/test_api_runtime.py`

**Imports + fixture 사용 패턴** (analog lines 1-10):
```python
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

SCENARIO_ID = "uc-camera-recording"
VARIANT_ID  = "UHD60-HDR10-H265"
BASE = f"/api/v1/scenarios/{SCENARIO_ID}/variants/{VARIANT_ID}"
```

**Core HTTP client pattern** (analog lines 54-65):
```python
def test_view_topology_mode(api_client: TestClient):
    resp = api_client.get(
        f"{BASE}/view",
        params={"level": 0, "mode": "topology"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "topology"
    assert data["scenario_id"] == SCENARIO_ID
    # topology mode는 sw_stack 노드를 포함해야 함
    layers = {n["data"]["layer"] for n in data["nodes"]}
    assert "app" in layers or "kernel" in layers, "topology mode에 SW 레인 노드 없음"

def test_view_topology_404(api_client: TestClient):
    resp = api_client.get(
        "/api/v1/scenarios/no-such-id/variants/no-vid/view",
        params={"level": 0, "mode": "topology"},
    )
    assert resp.status_code == 404
```

**Conftest dependency:** `api_client` fixture는 `tests/integration/conftest.py` (lines 81-111)에서 공급.
`scope="session"` — PostgresContainer + Alembic migration + ETL load + TestClient.
이 fixture는 그대로 재사용하면 됨 (별도 conftest 추가 불필요).

**Divergence from analog:** analog의 `test_view_topology_mode_returns_501` 테스트를 `200 + topology 검증`으로 교체. 기존 테스트가 501을 기대하므로 analog 파일의 해당 테스트도 함께 수정해야 함.

---

### `tests/unit/test_pipeline_sw_stack.py` (test, CRUD)

**Analog:** `tests/unit/test_definition_models.py` (lines 30-45, 72-100)

**Round-trip helper 패턴** (analog lines 36-45):
```python
def roundtrip(model_cls, raw: dict, **dump_kwargs):
    obj = model_cls.model_validate(raw)
    serialised = obj.model_dump(exclude_none=True, **dump_kwargs)
    obj2 = model_cls.model_validate(serialised)
    assert obj == obj2
    return obj
```

**Core pattern** — sw_stack Pydantic 모델 round-trip:
```python
from scenario_db.models.definition.usecase import Pipeline, SwStackNode

_SW_STACK_PIPELINE = {
    "nodes": [
        {"id": "csis0", "ip_ref": "ip-csis-v8", "instance_index": 0},
        {"id": "mfc",   "ip_ref": "ip-mfc-v14"},
    ],
    "edges": [
        {"from": "csis0", "to": "mfc", "type": "M2M"},
    ],
    "sw_stack": [
        {"layer": "app",    "id": "app-camera",  "label": "Camera App"},
        {"layer": "kernel", "id": "ker-v4l2",    "label": "V4L2 Driver", "ip_ref": "csis0"},
    ],
}

def test_pipeline_with_sw_stack_roundtrip():
    obj = roundtrip(Pipeline, _SW_STACK_PIPELINE, by_alias=True)
    assert len(obj.sw_stack) == 2
    assert obj.sw_stack[0].layer == "app"
    assert obj.sw_stack[1].ip_ref == "csis0"

def test_sw_stack_empty_by_default():
    """sw_stack 없는 기존 YAML도 여전히 valid."""
    raw = {"nodes": [{"id": "n1", "ip_ref": "ip-x"}], "edges": [], "sw_stack": []}
    obj = Pipeline.model_validate(raw)
    assert obj.sw_stack == []

def test_sw_stack_extra_field_forbidden():
    from pydantic import ValidationError
    bad = {"layer": "app", "id": "x", "label": "X", "unknown_field": True}
    with pytest.raises(ValidationError):
        SwStackNode.model_validate(bad)
```

**Divergence from analog:** analog은 YAML 파일에서 로드하지만, sw_stack은 아직 YAML 파일이 없으므로 in-memory dict 사용. YAML 추가 후 파일 경로 테스트 추가 권장.

---

### `dashboard/pages/1_Pipeline_Viewer.py` (component, request-response)

**Analog A (sys.path 설정):** 현재 `1_Pipeline_Viewer.py` lines 1-16

**Analog B (sidebar + session_state):** `dashboard/Home.py` 전체 구조

**sys.path 설정 패턴** (현재 lines 10-16, 유지):
```python
_root = Path(__file__).resolve().parents[2]
if str(_root / "src") not in sys.path:
    sys.path.insert(0, str(_root / "src"))
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
if str(_root / "dashboard") not in sys.path:
    sys.path.insert(0, str(_root / "dashboard"))
```

**@st.cache_data 패턴** (현재 lines 68-70을 확장):
```python
import requests
from scenario_db.api.schemas.view import ViewResponse

@st.cache_data(ttl=60)
def _fetch_scenarios(api_url: str) -> list[dict]:
    # api_url을 인수로 포함 → URL 변경 시 캐시 invalidate
    r = requests.get(f"{api_url}/api/v1/scenarios", params={"limit": 100}, timeout=10)
    r.raise_for_status()
    return r.json()["items"]   # PagedResponse.items (common.py 확인 완료)

@st.cache_data(ttl=60)
def _fetch_variants(api_url: str, scenario_id: str) -> list[dict]:
    r = requests.get(
        f"{api_url}/api/v1/scenarios/{scenario_id}/variants",
        params={"limit": 100}, timeout=10,
    )
    r.raise_for_status()
    return r.json()["items"]

@st.cache_data(ttl=60)
def _load_view(api_url: str, scenario_id: str, variant_id: str, mode: str) -> ViewResponse:
    r = requests.get(
        f"{api_url}/api/v1/scenarios/{scenario_id}/variants/{variant_id}/view",
        params={"level": 0, "mode": mode}, timeout=10,
    )
    r.raise_for_status()
    return ViewResponse.model_validate(r.json())

@st.cache_data(ttl=30)
def _fetch_gate(api_url: str, scenario_id: str, variant_id: str):
    from scenario_db.gate.models import GateExecutionResult
    r = requests.get(
        f"{api_url}/api/v1/scenarios/{scenario_id}/variants/{variant_id}/gate",
        timeout=10,
    )
    r.raise_for_status()
    return GateExecutionResult.model_validate(r.json())
```

**session_state + sidebar 패턴** (D-02 결정):
```python
with st.sidebar:
    # API URL 설정
    api_url = st.text_input(
        "API Base URL",
        value=st.session_state.get("api_url", "http://localhost:8000"),
        key="api_url_input",
    )
    if api_url != st.session_state.get("api_url"):
        st.session_state["api_url"] = api_url
        st.cache_data.clear()

    # Scenario dropdown
    scenarios = _fetch_scenarios(api_url)
    scenario_names = {s["id"]: s.get("metadata_", {}).get("name", s["id"]) for s in scenarios}
    selected_sid = st.selectbox("Scenario", list(scenario_names.keys()),
                                format_func=lambda x: scenario_names[x])

    # Variant dropdown
    variants = _fetch_variants(api_url, selected_sid)
    selected_vid = st.selectbox("Variant", [v["id"] for v in variants])

    # Mode radio (VIEW-05)
    mode = st.radio("View Mode", ["architecture", "topology"], index=0)

    # Gate overlay toggle (VIEW-04, D-06 lazy fetch)
    show_gate = st.toggle("Show Gate Status", value=False)
```

**mode→visible_layers 매핑 패턴** (VIEW-05):
```python
ARCH_LAYERS = ["hw", "memory"]
TOPO_LAYERS = ["app", "framework", "hal", "kernel", "hw"]

visible_layers = ARCH_LAYERS if mode == "architecture" else TOPO_LAYERS
render_level0(view_response=view, visible_layers=visible_layers, canvas_height=660)
```

**Divergence from analog:** `build_sample_level0()` import 제거 → `requests.get()` 교체. `@st.cache_data(ttl=60)` 인수 없는 현재 패턴을 api_url + scenario_id + variant_id 포함으로 확장.

---

### `dashboard/components/elk_viewer.py` (component, transform)

**Self-analog:** 현재 `elk_viewer.py` lines 523-537

**현재 render_level0 시그니처** (lines 523-529):
```python
def render_level0(
    view_response: ViewResponse,
    visible_layers: list[str] | None = None,
    visible_edge_types: list[str] | None = None,
    canvas_height: int = 660,
    selected_node: dict | None = None,
) -> None:
```

**Phase 4 추가: gate_styles 파라미터** (VIEW-04, D-06):
```python
def render_level0(
    view_response: ViewResponse,
    visible_layers: list[str] | None = None,
    visible_edge_types: list[str] | None = None,
    canvas_height: int = 660,
    selected_node: dict | None = None,
    gate_styles: dict[str, dict] | None = None,  # {node_id: {"border": "#EF4444"}}  NEW
) -> None:
    layout, meta = build_view_layout(
        view_response,
        visible_layers=visible_layers,
        visible_edge_types=visible_edge_types,
    )
    # gate_styles 오버라이드 적용 (노드 border/bg 색상)
    if gate_styles:
        for node_id, style in gate_styles.items():
            if node_id in meta:
                meta[node_id].update(style)
    html = _render_html(layout, meta, canvas_height)
    components.html(html, height=canvas_height + 40, scrolling=False)
```

**gate_styles 생성 패턴** (caller 측, Pipeline Viewer에서):
```python
GATE_BORDER = {
    "PASS":            "#D1D5DB",
    "WARN":            "#F59E0B",
    "BLOCK":           "#EF4444",
    "WAIVER_REQUIRED": "#8B5CF6",
}

def _build_gate_styles(gate, view: ViewResponse) -> dict[str, dict]:
    """gate status → 전체 뷰 노드에 동일 border 적용 (노드별 매핑은 Phase C)."""
    border = GATE_BORDER.get(str(gate.status), "#D1D5DB")
    return {n.data.id: {"border": border} for n in view.nodes}
```

**Divergence from analog:** `gate_styles` 파라미터 1개 추가. `_render_html()` 자체는 변경 없음 — meta dict 오버라이드만으로 충분.

---

### `dashboard/components/node_detail_panel.py` (component, CRUD)

**Self-analog:** 현재 `node_detail_panel.py` lines 45-110

**현재 render_inspector 시그니처** (line 45):
```python
def render_inspector(view: ViewResponse) -> None:
```

**Phase 4 추가: gate 파라미터 + GateExecutionResult 섹션** (VIEW-04):
```python
def render_inspector(
    view: ViewResponse,
    gate=None,   # GateExecutionResult | None — Optional import 피하기 위해 타입 미선언
) -> None:
```

**Gate 섹션 HTML 패턴** (현재 _risk_card, _metric_row 패턴 계승):
```python
GATE_STATUS_COLOR = {
    "PASS":            "#059669",
    "WARN":            "#D97706",
    "BLOCK":           "#DC2626",
    "WAIVER_REQUIRED": "#7C3AED",
}
GATE_STATUS_BG = {
    "PASS":            "#ECFDF5",
    "WARN":            "#FFFBEB",
    "BLOCK":           "#FEF2F2",
    "WAIVER_REQUIRED": "#F5F3FF",
}

def _gate_section(gate) -> None:
    status_str = str(gate.status)   # StrEnum → str (A3 가정 해소)
    color = GATE_STATUS_COLOR.get(status_str, "#6B7280")
    bg    = GATE_STATUS_BG.get(status_str, "#F9FAFB")
    issues_html = (
        ", ".join(f'<code>{i}</code>' for i in gate.matched_issues)
        if gate.matched_issues else "<em>none</em>"
    )
    waivers_html = (
        ", ".join(gate.missing_waivers) if gate.missing_waivers else "<em>none</em>"
    )
    st.markdown(
        f'<div style="background:{bg};border:2px solid {color};border-radius:8px;'
        f'padding:10px 12px;margin-bottom:12px;">'
        f'<span style="font-weight:700;color:{color};">Gate: {status_str}</span>'
        f'<div style="font-size:11px;color:#374151;margin-top:6px;">'
        f'Issues: {issues_html}</div>'
        f'<div style="font-size:11px;color:#374151;">Missing waivers: {waivers_html}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
```

**render_inspector 확장 위치** — 기존 SCENARIO 섹션 이전에 GATE 섹션 삽입:
```python
def render_inspector(view: ViewResponse, gate=None) -> None:
    if gate is not None:
        st.markdown('<p style="font-size:10px;font-weight:700;color:#9CA3AF;'
                    'letter-spacing:0.08em;text-transform:uppercase;margin-bottom:6px;">'
                    'GATE STATUS</p>', unsafe_allow_html=True)
        _gate_section(gate)
    # ... 기존 SCENARIO 섹션 그대로 이어짐
```

---

### `src/scenario_db/view/service.py` (service, CRUD)

**Self-analog:** 현재 `service.py` lines 233-305

**현재 _projection_to_view_response() 구조** (lines 233-284):
- `projection.get("pipeline", {}).get("nodes", [])` 로 노드 순회
- `NodeElement(data=NodeData(...), position={"x": 0.0, "y": 0.0})` — stub 위치

**Phase 4 확장 패턴** — topological sort + LANE_Y 실좌표:
```python
import graphlib

CATEGORY_TO_LANE: dict[str, str] = {
    "camera":  "hw",   # CSIS, ISP (ip-csis-v8, ip-isp-v12)
    "codec":   "hw",   # MFC      (ip-mfc-v14)
    "display": "hw",   # DPU      (ip-dpu-v9)
    "memory":  "hw",   # LLC      (ip-llc-v2)
}
STAGE_STEP = 310      # x 좌표 간격 px (STAGE_X capture→processing 차이)
STAGE_ORIGIN = 240    # LANE_LABEL_W(80) + 여백

def _topo_stage_map(nodes_raw: list[dict], edges_raw: list[dict]) -> dict[str, int]:
    """BFS level-by-level → stage_index 반환 (graphlib.TopologicalSorter 사용)."""
    ts = graphlib.TopologicalSorter()
    node_ids = {n["id"] for n in nodes_raw}
    for n in nodes_raw:
        ts.add(n["id"])
    for e in edges_raw:
        frm = e.get("from") or e.get("from_")
        if frm in node_ids and e.get("to") in node_ids:
            ts.add(e["to"], frm)
    ts.prepare()
    stage_map: dict[str, int] = {}
    stage_idx = 0
    while ts.is_active():
        ready = list(ts.get_ready())
        for nid in ready:
            stage_map[nid] = stage_idx
            ts.done(nid)
        stage_idx += 1
    return stage_map
```

**topology mode 구현 패턴** (project_level0 분기):
```python
def _sw_stack_to_view_response(projection: dict) -> ViewResponse:
    """sw_stack 기반 topology mode ViewResponse 생성."""
    from scenario_db.view.layout import LANE_Y
    pipeline = projection.get("pipeline", {})
    sw_stack = pipeline.get("sw_stack", [])
    hw_nodes_raw = pipeline.get("nodes", [])
    edges_raw    = pipeline.get("edges", [])

    # HW 노드 재사용 (architecture mode와 동일 좌표)
    ip_cat = {ip["id"]: ip for ip in projection.get("ip_catalog", [])}
    stage_map = _topo_stage_map(hw_nodes_raw, edges_raw)

    nodes: list[NodeElement] = []
    # SW 레인 노드
    sw_x_counter: dict[str, int] = {}
    for sw in sw_stack:
        layer = sw["layer"]
        sw_x_counter[layer] = sw_x_counter.get(layer, 0)
        x = STAGE_ORIGIN + sw_x_counter[layer] * STAGE_STEP
        sw_x_counter[layer] += 1
        y = LANE_Y[layer]
        nodes.append(NodeElement(
            data=NodeData(id=sw["id"], label=sw["label"], type="sw", layer=layer),
            position={"x": float(x), "y": float(y)},
        ))
    # HW 노드 (architecture mode 좌표 재사용)
    for node in hw_nodes_raw:
        nid = node["id"]
        ip_ref  = node.get("ip_ref", "")
        category = ip_cat.get(ip_ref, {}).get("category", "")
        lane     = CATEGORY_TO_LANE.get(category, "hw")
        stage    = stage_map.get(nid, 0)
        x = STAGE_ORIGIN + stage * STAGE_STEP
        y = LANE_Y[lane]
        nodes.append(NodeElement(
            data=NodeData(id=nid, label=node.get("label", nid), type="ip", layer=lane),
            position={"x": float(x), "y": float(y)},
        ))
    # SW→HW control 엣지
    sw_to_hw_edges: list[EdgeElement] = []
    for i, sw in enumerate(sw_stack):
        if sw.get("ip_ref"):
            sw_to_hw_edges.append(EdgeElement(data=EdgeData(
                id=f"sw-hw-{sw['id']}",
                source=sw["id"], target=sw["ip_ref"],
                flow_type="control",
            )))
    ...
```

**Divergence from analog:** `position={"x": 0.0, "y": 0.0}` 제거 → 실좌표 계산. topology mode `NotImplementedError` 제거 → `_sw_stack_to_view_response()` 신규 함수 구현.

---

### `src/scenario_db/models/definition/usecase.py` (model, CRUD)

**Self-analog:** 현재 `usecase.py` lines 23-61

**현재 Pipeline 모델** (lines 45-61):
```python
class Pipeline(BaseScenarioModel):
    nodes: list[PipelineNode] = Field(default_factory=list)
    edges: list[PipelineEdge] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_edge_references(self) -> Pipeline:
        ...
```

**Phase 4 추가: SwStackNode + sw_stack 필드** (D-05):
```python
class SwStackNode(BaseScenarioModel):
    """topology mode SW stack 노드 (YAML pipeline.sw_stack[] 항목)."""
    layer: Literal["app", "framework", "hal", "kernel"]
    id: str
    label: str
    ip_ref: str | None = None   # 연결 HW IP pipeline node id (ker-v4l2 → csis0)

class Pipeline(BaseScenarioModel):
    nodes: list[PipelineNode] = Field(default_factory=list)
    edges: list[PipelineEdge] = Field(default_factory=list)
    sw_stack: list[SwStackNode] = Field(default_factory=list)   # 신규 — Phase 4

    @model_validator(mode="after")
    def _validate_edge_references(self) -> Pipeline:
        ...  # 기존 validator 유지
```

**삽입 위치:** `PipelineEdge` 클래스 직후, `Pipeline` 클래스 이전 (기존 lines 35-43 사이).

**extra='forbid' 충돌 방지 원칙:** `SwStackNode`는 `BaseScenarioModel`을 상속하므로 자동으로 `extra='forbid'` 적용됨. `ip_ref` 없는 노드도 허용되도록 `Optional` (` | None = None`) 필수.

---

## Shared Patterns

### @st.cache_data 캐시 키 원칙
**Source:** `dashboard/pages/1_Pipeline_Viewer.py` (현재 line 68 패턴을 확장)
**Apply to:** 1_Pipeline_Viewer.py의 모든 fetch 함수

캐시 함수는 반드시 변동 요소(api_url, scenario_id, variant_id, mode)를 **모두 파라미터로 선언**해야 Streamlit이 올바르게 invalidate함:
```python
@st.cache_data(ttl=60)
def _load_view(api_url: str, scenario_id: str, variant_id: str, mode: str) -> ViewResponse:
    ...
```

`requests.Session` 객체를 캐시 함수 내부에서 생성하면 pickle 오류 → `requests.get()` 직접 호출 패턴 사용.

### PagedResponse.items 필드명 (확인 완료)
**Source:** `src/scenario_db/api/schemas/common.py` (line 11)
**Apply to:** 1_Pipeline_Viewer.py의 _fetch_scenarios(), _fetch_variants()

```python
class PagedResponse(BaseModel, Generic[T]):
    items: list[T]   # ← 정확한 필드명 확인됨
    total: int
    limit: int
    offset: int
    has_next: bool
```

Dashboard에서: `r.json()["items"]` 사용. `"data"`, `"results"` 아님.

### BaseScenarioModel 상속 + extra='forbid' 일관성
**Source:** `src/scenario_db/models/definition/usecase.py` (line 6-9, 23-26)
**Apply to:** SwStackNode 신규 모델

모든 도메인 모델은 `BaseScenarioModel`을 상속. 새 모델 추가 시:
- `ConfigDict(extra='forbid')` 직접 선언 불필요 (상속으로 적용됨)
- `Field(default_factory=list)` — 선택 필드의 기본값 패턴
- `str | None = None` — Optional 필드 패턴

### pytest.mark.integration 경계
**Source:** `tests/integration/conftest.py` (line 21), `tests/integration/test_api_runtime.py` (line 6)
**Apply to:** test_view_topology.py (integration), test_view_service.py는 미적용

```python
# integration test 상단에 반드시 추가
pytestmark = pytest.mark.integration
```

unit test (test_view_service.py, test_pipeline_sw_stack.py)에는 이 마커 없음 → Docker 없이 실행 가능.

### Literal + EdgeData.flow_type 제약
**Source:** `src/scenario_db/api/schemas/view.py` (EdgeData 정의)
**Apply to:** _sw_stack_to_view_response()에서 SW→HW 엣지 생성

SW→HW 연결 엣지는 반드시 `flow_type="control"` 사용.
허용값: `"OTF"`, `"vOTF"`, `"M2M"`, `"control"`, `"risk"`.
`"sw"` 같은 커스텀 타입은 ValidationError 발생.

---

## No Analog Found

없음 — 모든 Phase 4 파일에 대해 충분한 analog를 찾았음.

---

## Metadata

**Analog search scope:**
- `tests/unit/`, `tests/integration/`
- `dashboard/pages/`, `dashboard/components/`
- `src/scenario_db/view/`, `src/scenario_db/models/definition/`
- `src/scenario_db/api/schemas/`, `src/scenario_db/api/pagination.py`

**Files scanned:** 12
**Pattern extraction date:** 2026-05-10

**핵심 발견사항:**
1. `PagedResponse.items` 필드명 확인 완료 (RESEARCH.md A1 가정 해소)
2. `render_level0()` 시그니처에 `visible_layers` 파라미터 이미 존재 — 추가 불필요
3. `graphlib.TopologicalSorter` BFS API는 `prepare()` + `get_ready()` + `done()` 패턴 사용 (`static_order_groups()` 미존재 — RESEARCH.md A2 가정 수정)
4. `GateResultStatus`의 `.value` vs `str()` 안전성 — `str(gate.status)` 패턴 권장 (StrEnum 여부 미확인 시 안전)
