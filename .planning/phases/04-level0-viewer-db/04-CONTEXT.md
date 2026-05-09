# Phase 4: Level 0 Viewer DB — Context

**Gathered:** 2026-05-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 3에서 완성된 FastAPI `/view?level=0` 엔드포인트를 Streamlit 뷰어에 연동하고,
topology mode + gate overlay를 구현한다.

- 수정: `dashboard/pages/1_Pipeline_Viewer.py` — `build_sample_level0()` 직접 호출 → HTTP API 호출로 교체
- 수정: `src/scenario_db/view/service.py` — `project_level0()` DB projection → 실제 레인 배치 로직 추가
- 수정: `dashboard/components/elk_graph_builder.py` — category 기반 auto grid 배치
- 신규: pipeline YAML에 `sw_stack` 섹션 추가 (topology mode용)
- 신규: Gate overlay toggle (Sidebar "Show Gate Status" → node color/border 변경)

우선순위: VIEW-03(topology mode) → VIEW-04(gate overlay) 순서

</domain>

<decisions>
## Implementation Decisions

### D-01: Dashboard → FastAPI 연동 방식 (VIEW-01)

- **결정:** HTTP API (`requests.get()`) 방식 — 직접 service import 없음
  - `dashboard/pages/1_Pipeline_Viewer.py`에서 `build_sample_level0()` import 제거
  - `requests.get(f"{api_url}/api/v1/scenarios/{sid}/variants/{vid}/view?level=0&mode=architecture")`로 교체
  - Response JSON → Pydantic `ViewResponse.model_validate(data)`

### D-02: API Base URL 설정 (VIEW-01)

- **결정:** `st.sidebar` text input — 유저가 직접 입력
  - 기본값: `http://localhost:8000`
  - `st.session_state["api_url"]`에 저장 (re-run 간 유지)
  - 입력 변경 시 `st.cache_data.clear()` 호출

### D-03: Scenario / Variant 선택 UI (VIEW-01)

- **결정:** Sidebar dropdown — `/api/v1/scenarios` API에서 목록 조회
  - `@st.cache_data(ttl=60)` 적용
  - Scenario 선택 후 해당 scenario의 variants를 두 번째 dropdown으로 표시
  - `/api/v1/scenarios` 엔드포인트가 존재하지 않으면 stub 또는 수동 입력 fallback (CONTEXT 확인 후 planner가 결정)

### D-04: Architecture mode 노드 배치 전략 (VIEW-02)

- **핵심 문제:** pipeline YAML에 `lane_id`, `stage`, `layer` 필드가 없음
  - YAML pipeline.nodes: `{id, ip_ref, instance_index, role}` 만 존재
  - `IpCatalog.category` 필드로 lane 자동 추론

- **결정:** `ip_ref → IpCatalog.category → lane` 자동 매핑
  - 레인 매핑 테이블 (확장 가능):
    ```python
    CATEGORY_TO_LANE = {
        "csis": "hw", "isp": "hw", "mfc": "hw",
        "dpu": "hw", "gpu": "hw", "llc": "hw",
        "npu": "hw", "dsp": "hw",
    }
    ```
  - lane을 알 수 없으면 "hw" fallback

- **SW 스택 포함 여부 (architecture mode):** HW IP만 — App/Framework 노드 없음
  - architecture mode = HW IP 파이프라인 topology (CSIS→ISP→MFC/DPU)
  - SW 레인(app, framework, hal, kernel)은 topology mode에서 추가

- **Stage 배치 (x 좌표):** pipeline.edges 방향에서 자동 도출
  - Topological sort → stage_index 부여 → x = LANE_LABEL_W + stage_index * STAGE_STEP
  - edge가 없는 isolated 노드는 stage 0

- **위치 계산:** `service.py`의 `_projection_to_view_response()` 확장
  - 현재 `position={"x": 0.0, "y": 0.0}` → 실제 좌표 계산으로 교체

### D-05: Topology mode 데이터 소스 (VIEW-03, 우선순위 높음)

- **결정:** pipeline YAML에 `sw_stack` 섹션 신규 추가
  ```yaml
  pipeline:
    nodes: [...]
    edges: [...]
    sw_stack:          # 신규 — topology mode용
      - { layer: app,       id: app-camera,    label: "Camera App" }
      - { layer: framework, id: fw-cam-svc,    label: "CameraService" }
      - { layer: hal,       id: hal-camera,    label: "Camera HAL" }
      - { layer: kernel,    id: ker-v4l2,      label: "V4L2 Driver",  ip_ref: csis0 }
      - { layer: hal,       id: hal-codec2,    label: "Codec2 HAL" }
      - { layer: kernel,    id: ker-mfc-drv,   label: "MFC Driver",   ip_ref: mfc }
  ```
  - `ip_ref` 필드: SW 노드와 연결되는 HW IP node id (topology mode에서 SW→HW 엣지 생성)
  - future: perfetto profiling 결과에서 자동 생성

- **우선순위:** topology mode가 gate overlay보다 먼저 구현 (VIEW-03 → VIEW-04)

- **도메인 rationale:** HAL + kernel driver 실행이 HW 동작 사이에 끼어들어 jitter 유발
  - HW OTF chain(CSIS→ISP): HAL/driver 개입 없음 → jitter 없음
  - M2M 경계(ISP→MFC): HAL ioctl + kernel interrupt 처리 → HW 시작 전 SW overhead 존재
  - topology view 목적: 이 SW overhead를 명시적으로 시각화

- **미래 goal:** Perfetto profiling 수준 timing diagram (현재 Phase 4 scope 밖)

### D-06: Gate overlay 연동 (VIEW-04)

- **표시 위치:** 노드 자체에 직접 — 색상/테두리로 PASS/WARN/BLOCK/WAIVER_REQUIRED 구분
  - PASS: 기본 스타일 (변화 없음)
  - WARN: 노드 테두리 orange (`#F59E0B`)
  - BLOCK: 노드 테두리 red (`#EF4444`), 배경 tint
  - WAIVER_REQUIRED: 노드 테두리 purple (`#8B5CF6`)
  - Inspector panel: 선택 노드의 GateExecutionResult 상세 (status badge + matched_rules)

- **Fetch 전략:** lazy — Sidebar "Show Gate Status" 토글 ON 시에만
  - 토글 OFF: gate API 호출 없음 (불필요한 request 차단)
  - 토글 ON: `/api/v1/scenarios/{id}/variants/{vid}/gate` 호출 → `st.cache_data(ttl=30)` 적용
  - gate 결과는 `matched_issues` 필드로 노드 id와 매핑

- **노드-Issue 매핑:** `GateExecutionResult.matched_issues[].component` vs node.id 매핑
  - 매핑 테이블 별도 정의 필요 (node id와 issue component 필드가 다를 수 있음)
  - planner가 `gate/models.py` 확인 후 매핑 전략 결정

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 요구사항
- `.planning/REQUIREMENTS.md` §VIEW-01~VIEW-05 — Phase 4 요구사항 전체
- `.planning/ROADMAP.md` §Phase 4 — Success Criteria 5개 항목

### 기존 Dashboard 코드 (수정 대상)
- `dashboard/pages/1_Pipeline_Viewer.py` — `build_sample_level0()` → HTTP API 교체 (line 27~72)
- `dashboard/components/elk_graph_builder.py` — node position 계산 (line 78-89)
- `dashboard/components/elk_viewer.py` — SVG 렌더러
- `dashboard/components/node_detail_panel.py` — Inspector panel (`render_inspector()`)

### Phase 3 API (소비 대상)
- `GET /api/v1/scenarios/{id}/variants/{vid}/view?level=0&mode=architecture` → ViewResponse
- `GET /api/v1/scenarios/{id}/variants/{vid}/view?level=0&mode=topology` → 현재 501 (Phase 4 구현)
- `GET /api/v1/scenarios/{id}/variants/{vid}/gate` → GateExecutionResult

### 서비스 레이어 (수정 대상)
- `src/scenario_db/view/service.py` — `_projection_to_view_response()` 확장 (position 계산 추가)
- `src/scenario_db/db/repositories/view_projection.py` — `ip_catalog.category` 이미 포함됨

### 데이터 구조 확인 필수
- `demo/fixtures/02_definition/uc-camera-recording.yaml` — pipeline.nodes 구조 확인
  - 현재: `{id, ip_ref, instance_index, role}` — lane_id/stage/layer 없음
  - Phase 4: `sw_stack` 섹션 추가 필요
- `src/scenario_db/api/schemas/view.py` — ViewResponse, NodeElement, NodeData, EdgeElement 스키마
- `src/scenario_db/gate/models.py` — GateExecutionResult.matched_issues 구조 확인

### IpCatalog category 값 확인
- `demo/fixtures/01_capability/ip-*.yaml` — 각 IP의 `category` 필드 실제 값 확인
  - `ip-csis-v8.yaml`, `ip-isp-v12.yaml`, `ip-mfc-v14.yaml`, `ip-dpu-v9.yaml`

</canonical_refs>

<code_context>
## Existing Code Insights

### 현재 `1_Pipeline_Viewer.py` 문제점
```python
# 현재 (Phase 4에서 교체)
from scenario_db.view.service import build_sample_level0

@st.cache_data(ttl=60)
def _load_view():
    return build_sample_level0()
```
→ HTTP API 호출로 교체:
```python
import requests

@st.cache_data(ttl=60)
def _load_view(api_url: str, scenario_id: str, variant_id: str) -> ViewResponse:
    r = requests.get(f"{api_url}/api/v1/scenarios/{scenario_id}/variants/{variant_id}/view",
                     params={"level": 0, "mode": "architecture"}, timeout=10)
    r.raise_for_status()
    return ViewResponse.model_validate(r.json())
```

### Sidebar 구조 (Phase 4 확장)
```python
with st.sidebar:
    api_url = st.text_input("API URL", value="http://localhost:8000",
                             key="api_url")
    # scenario/variant dropdown (from /api/v1/scenarios)
    scenario_id = st.selectbox("Scenario", scenarios)
    variant_id  = st.selectbox("Variant",  variants[scenario_id])
    st.divider()
    mode = st.radio("Mode", ["architecture", "topology"])
    st.divider()
    show_gate = st.checkbox("Show Gate Status")  # VIEW-04
```

### `_projection_to_view_response()` 확장 방향
```python
# Phase 4: position 계산 추가
ip_catalog_map = {ip["id"]: ip for ip in projection["ip_catalog"]}

def _infer_lane(ip_ref: str) -> str:
    ip = ip_catalog_map.get(ip_ref, {})
    category = ip.get("category", "")
    return CATEGORY_TO_LANE.get(category, "hw")

def _topo_sort_stages(nodes, edges) -> dict[str, int]:
    # pipeline edges에서 topological sort → stage_index
    ...

for node in nodes:
    lane = _infer_lane(node.get("ip_ref", ""))
    stage_idx = stage_map.get(node["id"], 0)
    x = LANE_LABEL_W + stage_idx * STAGE_STEP + NODE_W / 2
    y = LANE_Y[lane]
    ...
```

### get_view_projection() 반환 구조 (이미 ip_catalog 포함)
```python
{
    "scenario_id": str,
    "variant_id": str,
    "project_name": str | None,
    "pipeline": {
        "nodes": [{"id", "ip_ref", "instance_index", "role"}, ...],
        "edges": [{"from", "to", "type", "buffer"?}, ...],
        # Phase 4 추가: "sw_stack": [{"layer", "id", "label", "ip_ref"?}, ...]
    },
    "ip_catalog": [{"id", "category", "hierarchy", "capabilities"}, ...],
    "lanes": [{"lane_id", "nodes"}, ...],  # lane_id=기존 "default" (Phase 4에서 개선)
}
```

### Gate overlay 색상 매핑
```python
GATE_STATUS_STYLE: dict[str, dict] = {
    "PASS":             {"border": "#D1D5DB", "bg_tint": None},
    "WARN":             {"border": "#F59E0B", "bg_tint": "#FFFBEB"},
    "BLOCK":            {"border": "#EF4444", "bg_tint": "#FEF2F2"},
    "WAIVER_REQUIRED":  {"border": "#8B5CF6", "bg_tint": "#F5F3FF"},
}
```

</code_context>

<specifics>
## Specific Implementation Notes

- `st.cache_data` 함수 signature에 `api_url`, `scenario_id`, `variant_id` 인수 포함 필수
  (인수가 없으면 scenario 변경 시 cache invalidation 안 됨)
- topology mode: service.py에서 `raise NotImplementedError` → 실제 구현으로 교체
  - `sw_stack` 섹션에서 SW 노드 생성 + SW→HW 엣지 생성
- `IpCatalog.category` 실제 값 확인 후 `CATEGORY_TO_LANE` 매핑 완성 (planner 작업)
- `/api/v1/scenarios` 엔드포인트 존재 여부 확인 필요
  - 없으면 Phase 4에서 신규 추가 또는 sidebar에 수동 입력 fallback
- `GateExecutionResult.matched_issues` → node id 매핑:
  - issue component 필드와 pipeline node id가 다를 수 있음 — planner가 확인

</specifics>

<deferred>
## Deferred Ideas

- Perfetto profiling 결과에서 `sw_stack` 자동 생성 (future milestone)
- Level 1 IP DAG view (Phase C)
- Level 2 drill-down view (Phase C)
- Timing diagram (perfetto 수준) — milestone 이후
- ELK layout engine 연동 — Level 1 이후
- `build_sample_level0()` 삭제 — Phase 4 완료 후 dashboard에서 더 이상 호출 안 하면 제거

</deferred>

---

*Phase: 04-Level0-Viewer-DB*
*Context gathered: 2026-05-10*
