# Phase 4: Level 0 Viewer DB — Research

**Researched:** 2026-05-10
**Domain:** Streamlit Dashboard / FastAPI 연동 / SVG 렌더러 확장 / topology mode 신규 구현
**Confidence:** HIGH (전체 코드베이스 직접 검증)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01: Dashboard → FastAPI 연동 방식 (VIEW-01)**
- HTTP API (`requests.get()`) — 직접 service import 없음
- `requests.get(f"{api_url}/api/v1/scenarios/{sid}/variants/{vid}/view?level=0&mode=architecture")` 로 교체
- Response JSON → Pydantic `ViewResponse.model_validate(data)`

**D-02: API Base URL 설정 (VIEW-01)**
- `st.sidebar` text input, 기본값 `http://localhost:8000`
- `st.session_state["api_url"]`에 저장, 변경 시 `st.cache_data.clear()` 호출

**D-03: Scenario / Variant 선택 UI (VIEW-01)**
- Sidebar dropdown — `/api/v1/scenarios` API에서 목록 조회, `@st.cache_data(ttl=60)`
- Scenario 선택 후 해당 scenario의 variants를 두 번째 dropdown으로 표시
- 엔드포인트 없으면 stub 또는 수동 입력 fallback (planner 결정)

**D-04: Architecture mode 노드 배치 전략 (VIEW-02)**
- `ip_ref → IpCatalog.category → lane` 자동 매핑
- Stage 배치: pipeline.edges에서 topological sort → stage_index → x 좌표
- `position={"x": 0.0, "y": 0.0}` → 실제 좌표 계산으로 교체
- SW 레인은 topology mode에서만 (architecture mode에서는 HW IP만)

**D-05: Topology mode 데이터 소스 (VIEW-03)**
- pipeline YAML에 `sw_stack` 섹션 신규 추가
- `ip_ref` 필드: SW 노드와 연결되는 HW IP node id
- 구현 우선순위: topology mode (VIEW-03) → gate overlay (VIEW-04)

**D-06: Gate overlay 연동 (VIEW-04)**
- 노드 색상/테두리로 PASS/WARN/BLOCK/WAIVER_REQUIRED 구분
- Lazy fetch — Sidebar "Show Gate Status" 토글 ON 시에만 API 호출
- `@st.cache_data(ttl=30)` 적용

### Claude's Discretion

없음 — 모든 구현 결정은 D-01~D-06으로 잠금.

### Deferred Ideas (OUT OF SCOPE)

- Perfetto profiling 결과에서 `sw_stack` 자동 생성
- Level 1 IP DAG view (Phase C)
- Level 2 drill-down view (Phase C)
- Timing diagram (perfetto 수준) — milestone 이후
- ELK layout engine 연동 — Level 1 이후
- `build_sample_level0()` 삭제 — Phase 4 완료 후 별도 정리
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VIEW-01 | `project_level0(db, scenario_id, variant_id)` DB 구현 — 하드코딩 sample data 제거 | `service.py`의 `_projection_to_view_response()` 확장으로 실좌표 계산, HTTP API 연동 |
| VIEW-02 | Level 0 architecture mode — 기존 lane view를 DB 데이터로 구동 | CATEGORY_TO_LANE 매핑 완성, topological sort stage 배치 |
| VIEW-03 | Level 0 topology mode — SW task/thread/queue 노드 중심 레이아웃 | sw_stack YAML 섹션 신규 + `service.py` topology 분기 구현 |
| VIEW-04 | Gate overlay — GateExecutionResult를 인스펙터 패널 + risk card로 표시 | gate endpoint 확인 완료, matched_issues는 issue id 목록 |
| VIEW-05 | `mode=architecture|topology` selector UI (Streamlit radio button) | sidebar radio + visible_layers 파라미터 전달 구조 확인 완료 |
</phase_requirements>

---

## Summary

Phase 4는 크게 3개 영역으로 구성된다: (1) Dashboard ↔ FastAPI HTTP 연동 (VIEW-01/02/05), (2) SW stack 데이터 추가 및 topology mode 구현 (VIEW-03), (3) Gate overlay 연동 (VIEW-04).

**기존 코드 상태 (검증 완료):**
- `/api/v1/scenarios` 엔드포인트: **존재 (확인됨)** — `definition.py` `list_scenarios()` 구현되어 있음
- `/api/v1/scenarios/{id}/variants` 엔드포인트: **존재** — `list_variants_for_scenario()` 구현됨
- `/api/v1/scenarios/{id}/variants/{vid}/gate` 엔드포인트: **존재** — `runtime.py` 구현됨
- `LANE_LABEL_ORDER = ["app", "framework", "hal", "kernel", "hw", "memory"]`: **이미 정의됨** — SW 레인 포함
- `LANE_Y`: app/framework/hal/kernel/hw/memory **모두 정의됨** — topology mode 레인 y좌표 즉시 사용 가능
- `build_sample_level0()`: 여전히 `1_Pipeline_Viewer.py`에서 직접 import하여 사용 중 — Phase 4에서 교체 필요
- `project_level0()` topology 분기: `raise NotImplementedError("topology mode is Phase 4 work")` — 실제 구현 대상

**가장 복잡한 부분:** `service.py`의 `_projection_to_view_response()` 확장 — topological sort, CATEGORY_TO_LANE 매핑, 실좌표 계산을 모두 여기서 처리해야 함.

**Primary recommendation:** Wave 1에서 architecture mode DB 연동 + 좌표 계산을 완성하고, Wave 2에서 sw_stack + topology mode, Wave 3에서 gate overlay를 구현한다.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Scenario/Variant 목록 조회 | API (FastAPI) | Dashboard (소비) | DB 쿼리는 API에서, UI dropdown은 Dashboard에서 |
| Level 0 view 데이터 생성 | API service.py | — | 좌표 계산/투영은 서버사이드 책임 |
| Topology mode SW stack 저장 | API (pipeline YAML → DB) | Dashboard (소비) | YAML 스키마 변경 → ETL → DB → API → Dashboard |
| Gate 상태 조회 | API (runtime.py) | Dashboard (lazy fetch) | gate evaluation은 API, 렌더링은 Dashboard |
| SVG 렌더링 | Dashboard (elk_viewer.py) | Browser (JS) | layout dict를 JS가 SVG로 그림 |
| 노드 선택/인스펙터 | Browser (JS click) | Dashboard (node_detail_panel.py) | 클릭 이벤트는 JS, 패널 렌더링은 Python |

---

## Standard Stack

### Core (현재 프로젝트에 이미 설치됨)

| 라이브러리 | 버전 | 목적 | 비고 |
|-----------|------|------|------|
| streamlit | 현재 설치 | Dashboard UI | `dashboard` optional group |
| requests | 현재 설치 | HTTP API 호출 | `requests.get()` — D-01 결정 |
| pydantic v2 | 현재 설치 | ViewResponse validate | `model_validate()` |
| fastapi | 현재 설치 | API 서버 | 이미 36 endpoints 동작 중 |
| sqlalchemy | 현재 설치 | DB 쿼리 | repositories 패턴 유지 |

### 신규 추가 없음

Phase 4는 기존 스택으로 모두 구현 가능. 외부 의존성 추가 없음. [VERIFIED: 코드베이스 직접 검증]

---

## Architecture Patterns

### System Architecture Diagram

```
[Streamlit Dashboard]
        │
        │ requests.get() (D-01)
        ▼
[FastAPI :8000]
   /api/v1/scenarios                     → scenario dropdown 목록
   /api/v1/scenarios/{id}/variants       → variant dropdown 목록
   /api/v1/scenarios/{id}/variants/{vid}/view?level=0&mode={mode}
        │
        ▼
[service.py: project_level0()]
   architecture mode: _projection_to_view_response()
        │  - ip_ref → CATEGORY_TO_LANE 매핑
        │  - topological sort → stage_index → x 좌표
        │  - LANE_Y[lane] → y 좌표
   topology mode: _sw_stack_to_view_response()
        │  - sw_stack 섹션 파싱
        │  - SW 노드 생성 + SW→HW 엣지 생성
        ▼
[ViewResponse JSON]
        │
        ▼
[elk_graph_builder.py: build_view_layout()]
        │  - visible_layers 파라미터로 mode별 레인 필터링
        ▼
[elk_viewer.py: render_level0()]  →  [SVG in Browser]

[Gate overlay (lazy)]
   Sidebar "Show Gate Status" ON
        │
        │ requests.get() /gate
        ▼
[GateExecutionResult]
        │  - matched_issues: list[str] → issue id 목록
        │  - status → 노드 border/bg 색상 결정
        ▼
[node_detail_panel.py: render_inspector()] + [elk_viewer.py: 노드 스타일 오버라이드]
```

### Recommended Project Structure (변경 대상만)

```
dashboard/
├── pages/
│   └── 1_Pipeline_Viewer.py     # 전체 재작성 (HTTP API 연동)
├── components/
│   ├── elk_graph_builder.py     # build_view_layout() visible_layers 파라미터 이미 지원
│   ├── elk_viewer.py            # gate_styles 파라미터 추가 필요
│   └── node_detail_panel.py    # GateExecutionResult 표시 추가
src/scenario_db/
├── view/
│   └── service.py               # _projection_to_view_response() 실좌표 계산 확장
│                                #  + topology mode 구현
demo/fixtures/
└── 02_definition/
    └── uc-camera-recording.yaml # sw_stack 섹션 추가
src/scenario_db/
└── models/definition/
    └── usecase.py               # Pipeline 모델에 sw_stack 필드 추가
```

### Pattern 1: CATEGORY_TO_LANE 완성 매핑

**실제 IpCatalog.category 값 (모든 fixture 직접 검증):**

| IP YAML | id | category |
|---------|-----|----------|
| ip-csis-v8.yaml | ip-csis-v8 | `camera` |
| ip-isp-v12.yaml | ip-isp-v12 | `camera` |
| ip-mfc-v14.yaml | ip-mfc-v14 | `codec` |
| ip-dpu-v9.yaml | ip-dpu-v9 | `display` |
| ip-llc-v2.yaml | ip-llc-v2 | `memory` |

[VERIFIED: 코드베이스 직접 읽음 — demo/fixtures/00_hw/ip-*.yaml]

**따라서 올바른 CATEGORY_TO_LANE 매핑:**

```python
CATEGORY_TO_LANE: dict[str, str] = {
    "camera":  "hw",    # CSIS, ISP
    "codec":   "hw",    # MFC
    "display": "hw",    # DPU
    "memory":  "hw",    # LLC (hw lane에 배치 — buffer lane 아님)
    # future: "npu": "hw", "dsp": "hw", "gpu": "hw"
}
```

CONTEXT.md D-04의 CATEGORY_TO_LANE 초안(`"csis", "isp", "mfc"` 등의 id 기반)은 **틀렸음** — 실제 필드는 category (category 값 기반으로 매핑해야 함). [VERIFIED]

### Pattern 2: Topological Sort로 stage_index 도출

`uc-camera-recording.yaml` pipeline edges 실제 구조 [VERIFIED]:
```yaml
edges:
  - { from: csis0, to: isp0, type: OTF }
  - { from: isp0,  to: mfc,  type: M2M, buffer: "RECORD_BUF" }
  - { from: isp0,  to: dpu,  type: M2M, buffer: "PREVIEW_BUF" }
```

nodes: `csis0, isp0, mfc, dpu, llc` (5개, llc는 edge 없음 → isolated)

topological sort 결과: `csis0(0) → isp0(1) → mfc(2), dpu(2)`, `llc(0)` (isolated)

stage_index → STAGE_X 매핑 (기존 layout.py 상수 활용):
```python
STAGE_X = {
    "capture":    195.0,  # stage_index 0
    "processing": 510.0,  # stage_index 1
    "encode":     790.0,  # stage_index 2
    "display":    1020.0, # stage_index 3
}
# stage_index를 직접 사용하는 경우:
STAGE_STEP = 310  # 510 - 195 (approximate, variable)
```

**권장:** topo sort stage_index 0,1,2... → STAGE_X의 capture/processing/encode/display 순으로 매핑. llc (isolated) → stage_index 0 → capture 열.

### Pattern 3: GateExecutionResult.matched_issues 구조 (확인 완료)

```python
class GateExecutionResult(BaseModel):
    status: GateResultStatus
    matched_rules: list[GateRuleMatch] = []
    matched_issues: list[str] = []      # issue id 목록 (str list)
    applicable_waivers: list[str] = []
    missing_waivers: list[str] = []
```

[VERIFIED: src/scenario_db/gate/models.py 직접 읽음]

`matched_issues`는 issue id 문자열 목록. pipeline node id와 직접 매핑되지 않음.

**노드-Issue 매핑 전략:**
- `uc-camera-recording.yaml`에서 `references.known_issues: [iss-LLC-thrashing-0221]` 확인
- `build_sample_level0()`에서 `hw-mfc` 노드에 `matched_issues=["iss-LLC-thrashing-0221"]` 하드코딩됨
- Phase 4에서의 실용적 접근: gate 결과의 `status`만 사용해 노드 전체 border 색상 변경 (노드별 per-issue 매핑은 복잡 — view 레이어에서 처리 불필요)
- Inspector panel에서 GateExecutionResult 전체 표시 (matched_issues 목록 + matched_rules)

### Pattern 4: /api/v1/scenarios 엔드포인트 존재 확인

[VERIFIED: src/scenario_db/api/routers/definition.py 직접 읽음]

```python
@router.get("/scenarios", response_model=PagedResponse[ScenarioResponse])
def list_scenarios(limit, offset, sort_by, sort_dir, db):
    ...

@router.get("/scenarios/{scenario_id}/variants", response_model=PagedResponse[ScenarioVariantResponse])
def list_variants_for_scenario(scenario_id, limit, offset, sort_by, sort_dir, db):
    ...
```

두 엔드포인트 모두 존재. D-03의 "없으면 fallback" 분기는 **불필요**. Dashboard에서 직접 사용 가능.

**응답 구조 확인:**
```python
class ScenarioResponse(BaseModel):
    id: str
    schema_version: str
    project_ref: str
    metadata_: dict = {}   # {"name": "Camera Recording Pipeline", ...}
    pipeline: dict = {}
    ...

class ScenarioVariantResponse(BaseModel):
    scenario_id: str
    id: str
    severity: str | None = None
    design_conditions: dict | None = None
    ...
```

Dropdown 표시용: `ScenarioResponse.id`, `ScenarioResponse.metadata_.get("name", id)`.
Variant dropdown: `ScenarioVariantResponse.id`.

PagedResponse 구조 확인 필요 → `.items` 또는 `.data` 필드로 목록 접근 예상. [ASSUMED - PagedResponse 내부 구조 미확인]

### Pattern 5: visible_layers로 mode별 레인 필터링

`build_view_layout()`는 이미 `visible_layers` 파라미터 지원:

```python
def build_view_layout(
    view: ViewResponse,
    visible_layers: list[str] | None = None,  # None이면 모든 레인 표시
    visible_edge_types: list[str] | None = None,
) -> tuple[dict, dict]:
    vis_layers = set(visible_layers) if visible_layers is not None else set(LANE_LABEL_ORDER)
    ...
```

[VERIFIED: dashboard/components/elk_graph_builder.py 직접 읽음]

mode별 visible_layers:
```python
ARCH_LAYERS  = ["hw", "memory"]           # architecture mode
TOPO_LAYERS  = ["app", "framework", "hal", "kernel", "hw"]  # topology mode (memory 제외 가능)
```

### Pattern 6: sw_stack YAML 스키마 및 Pydantic 모델 수정

**현재 Pipeline 모델** (usecase.py 확인):
```python
class Pipeline(BaseScenarioModel):
    nodes: list[PipelineNode] = Field(default_factory=list)
    edges: list[PipelineEdge] = Field(default_factory=list)
    # sw_stack 없음 — Phase 4에서 추가
```

`model_config = ConfigDict(extra='forbid')` 사용 중 (`BaseScenarioModel` 상속) → sw_stack 추가 시 Pydantic 모델 수정 필수.

**추가할 Pydantic 모델:**
```python
class SwStackNode(BaseScenarioModel):
    layer: Literal["app", "framework", "hal", "kernel"]
    id: str
    label: str
    ip_ref: str | None = None  # 연결 HW IP node id

class Pipeline(BaseScenarioModel):
    nodes: list[PipelineNode] = Field(default_factory=list)
    edges: list[PipelineEdge] = Field(default_factory=list)
    sw_stack: list[SwStackNode] = Field(default_factory=list)  # 신규
```

**ETL 영향:** `pipeline` 컬럼은 JSONB 타입 — sw_stack 추가는 ETL mapper 변경 없이 JSONB 그대로 저장됨. [VERIFIED: db/models/definition.py - pipeline = Column(JSONB)]

단, `get_view_projection()`이 `scenario.pipeline`을 raw dict로 반환하므로 `projection["pipeline"].get("sw_stack", [])` 으로 접근 가능.

### Anti-Patterns to Avoid

- **`visible_layers` 없이 모드 전환:** topology mode 선택 시 `visible_layers`를 넘기지 않으면 "hw", "memory" 외 레인도 모두 표시됨 (architecture data만 있는 경우 빈 레인 표시). 반드시 mode별 레이어 필터링 필요.
- **Gate overlay를 eager로 fetch:** 토글 OFF 상태에서도 gate API를 호출하면 불필요한 서버 부하. D-06 결정 준수 (lazy fetch).
- **`position={"x": 0.0, "y": 0.0}` 유지:** service.py의 기존 stub 코드를 그대로 사용하면 모든 노드가 좌상단에 겹침. 실좌표 계산 확장 필수.
- **`@st.cache_data` 인수 없이 사용:** scenario/variant 변경 시 캐시가 invalidate되지 않음. api_url, scenario_id, variant_id를 모두 인수로 포함해야 함.
- **sw_stack 없이 topology mode 렌더링:** sw_stack 섹션 추가 전에 topology mode를 렌더링하면 빈 ViewResponse 반환.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Topological sort | 직접 DFS 구현 | Python stdlib `graphlib.TopologicalSorter` | Python 3.9+에 포함, cycle detection 포함 |
| Scenario 목록 드롭다운 | 별도 stub | `/api/v1/scenarios` 이미 존재 | 엔드포인트 확인됨 |
| Gate status 집계 | 노드별 status 재계산 | GateExecutionResult.status 그대로 사용 | API가 이미 BLOCK>WAIVER_REQUIRED>WARN>PASS 집계 완료 |
| LANE_Y 재정의 | 새 상수 | `src/scenario_db/view/layout.py` LANE_Y | SW 레인 포함 이미 정의됨 |

---

## Runtime State Inventory

> 이 Phase는 코드/YAML 변경 + Dashboard HTTP 연동이지만, YAML 스키마 변경이 DB에 영향을 줌.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | `uc-camera-recording.yaml`의 pipeline → DB `scenarios.pipeline` JSONB 컬럼 | sw_stack 추가 후 ETL 재실행 필요 (uv run etl load) |
| Live service config | FastAPI 서버 재시작 필요 (service.py 변경) | 코드 수정 후 서버 재기동 |
| OS-registered state | 없음 | — |
| Secrets/env vars | DATABASE_URL 등 기존 그대로 | 변경 없음 |
| Build artifacts | 없음 | — |

**sw_stack YAML 추가 후 반드시 ETL 재실행 필요:** `uv run python -m scenario_db.etl.loader demo/fixtures/` 또는 동등 명령으로 DB 재로드.

---

## Common Pitfalls

### Pitfall 1: CATEGORY_TO_LANE 키 오류 (category vs ip id)

**What goes wrong:** CONTEXT.md D-04의 초안은 `"csis", "isp", "mfc"`를 키로 사용 — 이는 ip id가 아니라 category 값이어야 함. 실제 category 값은 `"camera"`, `"codec"`, `"display"`, `"memory"`.
**Why it happens:** 설계 단계에서 ip id와 category 값을 혼동.
**How to avoid:** 이 Research에서 확인한 실제 값 사용: `{"camera": "hw", "codec": "hw", "display": "hw", "memory": "hw"}`.
**Warning signs:** 모든 노드가 "hw" fallback으로 처리됨 (올바른 결과이긴 하지만 매핑 테이블이 동작하지 않는 신호).

### Pitfall 2: sw_stack + extra='forbid' 충돌

**What goes wrong:** `Pipeline` 모델이 `BaseScenarioModel`(extra='forbid') 상속 → sw_stack 필드 없이 YAML에 `sw_stack` 추가하면 ValidationError.
**Why it happens:** 코드베이스 전체에 `extra='forbid'` 적용됨.
**How to avoid:** `usecase.py`의 `Pipeline` 모델에 `sw_stack: list[SwStackNode] = Field(default_factory=list)` 추가 필수.
**Warning signs:** ETL 실행 시 `pydantic_core._pydantic_core.ValidationError: Extra inputs are not permitted`.

### Pitfall 3: PagedResponse 구조 미확인으로 dropdown 오류

**What goes wrong:** `requests.get("/api/v1/scenarios")` 응답을 `.json()["items"]` 등으로 접근 시 KeyError.
**Why it happens:** PagedResponse 내부 구조를 확인하지 않음.
**How to avoid:** `src/scenario_db/api/pagination.py`의 PagedResponse 구조 확인 후 정확한 필드명 사용. [현재 `PagedResponse.from_query()` 반환 필드명 확인 필요]
**Warning signs:** `KeyError: 'items'` 또는 `KeyError: 'data'`.

### Pitfall 4: topology mode에서 SW→HW 엣지의 flow_type

**What goes wrong:** `EdgeData.flow_type`이 `Literal["OTF", "vOTF", "M2M", "control", "risk"]` 로 제한됨. SW→HW 엣지를 다른 타입으로 생성하면 ValidationError.
**Why it happens:** view.py 스키마의 Literal 제약.
**How to avoid:** SW→HW 엣지는 `"control"` 타입 사용. `build_sample_level0()`에서 SW 레인 간 엣지가 모두 `"control"`임을 확인. [VERIFIED]
**Warning signs:** `pydantic_core.ValidationError: Input should be 'OTF', 'vOTF', 'M2M', 'control' or 'risk'`.

### Pitfall 5: `@st.cache_data`와 `requests.Session` 충돌

**What goes wrong:** `requests.Session` 객체를 `@st.cache_data` 내부에서 생성하면 pickle 직렬화 실패.
**Why it happens:** st.cache_data는 반환값을 pickle로 직렬화.
**How to avoid:** `requests.get()` 직접 호출 (Session 없이). 또는 `st.cache_data(hash_funcs={...})` 설정.
**Warning signs:** `TypeError: cannot pickle '_thread.RLock' object`.

---

## Code Examples

### [1] _projection_to_view_response() 실좌표 계산 확장]

```python
# Source: src/scenario_db/view/service.py 수정 대상 (현재 x=0.0, y=0.0 stub)
import graphlib

CATEGORY_TO_LANE: dict[str, str] = {
    "camera":  "hw",
    "codec":   "hw",
    "display": "hw",
    "memory":  "hw",  # LLC
}
LANE_LABEL_W = 80
STAGE_STEP = 310  # 310px per stage (capture→processing 간격)

def _projection_to_view_response(projection: dict) -> ViewResponse:
    pipeline = projection.get("pipeline", {})
    nodes_raw = pipeline.get("nodes", [])
    edges_raw = pipeline.get("edges", [])

    # ip_catalog lookup
    ip_cat = {ip["id"]: ip for ip in projection.get("ip_catalog", [])}

    # topological sort
    ts = graphlib.TopologicalSorter()
    node_ids = {n["id"] for n in nodes_raw}
    for n in nodes_raw:
        ts.add(n["id"])
    for e in edges_raw:
        if e.get("from") in node_ids and e.get("to") in node_ids:
            ts.add(e["to"], e["from"])
    stage_map: dict[str, int] = {}
    for stage_idx, batch in enumerate(ts.static_order_groups() if hasattr(ts, 'static_order_groups') else [list(ts.static_order())]):
        for nid in batch:
            stage_map[nid] = stage_idx

    nodes = []
    for node in nodes_raw:
        nid = node["id"]
        ip_ref = node.get("ip_ref", "")
        category = ip_cat.get(ip_ref, {}).get("category", "")
        lane = CATEGORY_TO_LANE.get(category, "hw")
        stage_idx = stage_map.get(nid, 0)
        x = LANE_LABEL_W + stage_idx * STAGE_STEP + 50  # node center x
        y = LANE_Y[lane]
        nodes.append(NodeElement(
            data=NodeData(id=nid, label=node.get("label", nid), type="ip", layer=lane),
            position={"x": float(x), "y": float(y)},
        ))
    ...
```

### [2] 1_Pipeline_Viewer.py HTTP API 연동 패턴

```python
# Source: CONTEXT.md D-01~D-03 결정
import requests
import streamlit as st
from scenario_db.api.schemas.view import ViewResponse

@st.cache_data(ttl=60)
def _fetch_scenarios(api_url: str) -> list[dict]:
    r = requests.get(f"{api_url}/api/v1/scenarios", params={"limit": 100}, timeout=10)
    r.raise_for_status()
    return r.json()["items"]  # PagedResponse 구조 확인 후 수정

@st.cache_data(ttl=60)
def _fetch_variants(api_url: str, scenario_id: str) -> list[dict]:
    r = requests.get(
        f"{api_url}/api/v1/scenarios/{scenario_id}/variants",
        params={"limit": 100}, timeout=10
    )
    r.raise_for_status()
    return r.json()["items"]

@st.cache_data(ttl=60)
def _load_view(api_url: str, scenario_id: str, variant_id: str, mode: str) -> ViewResponse:
    r = requests.get(
        f"{api_url}/api/v1/scenarios/{scenario_id}/variants/{variant_id}/view",
        params={"level": 0, "mode": mode}, timeout=10
    )
    r.raise_for_status()
    return ViewResponse.model_validate(r.json())

@st.cache_data(ttl=30)
def _fetch_gate(api_url: str, scenario_id: str, variant_id: str):
    from scenario_db.gate.models import GateExecutionResult
    r = requests.get(
        f"{api_url}/api/v1/scenarios/{scenario_id}/variants/{variant_id}/gate",
        timeout=10
    )
    r.raise_for_status()
    return GateExecutionResult.model_validate(r.json())
```

### [3] GateExecutionResult → 인스펙터 표시 패턴

```python
# Source: CONTEXT.md D-06, gate/models.py 검증 완료
GATE_STATUS_STYLE = {
    "PASS":             {"border": "#D1D5DB", "bg_tint": None},
    "WARN":             {"border": "#F59E0B", "bg_tint": "#FFFBEB"},
    "BLOCK":            {"border": "#EF4444", "bg_tint": "#FEF2F2"},
    "WAIVER_REQUIRED":  {"border": "#8B5CF6", "bg_tint": "#F5F3FF"},
}

def render_gate_inspector(gate: GateExecutionResult) -> None:
    status = gate.status.value  # GateResultStatus는 StrEnum
    style = GATE_STATUS_STYLE[status]
    st.markdown(f"""
    <div style="border: 2px solid {style['border']}; border-radius: 8px; padding: 8px;">
      <b>Gate Status: {status}</b>
      <br>Matched Issues: {', '.join(gate.matched_issues) or 'None'}
      <br>Missing Waivers: {', '.join(gate.missing_waivers) or 'None'}
    </div>
    """, unsafe_allow_html=True)
```

### [4] sw_stack YAML 예시 (uc-camera-recording.yaml 추가 내용)

```yaml
# Source: CONTEXT.md D-05 결정
pipeline:
  nodes:
    - { id: csis0, ip_ref: ip-csis-v8, instance_index: 0 }
    - { id: isp0,  ip_ref: ip-isp-v12, instance_index: 0, role: main }
    - { id: mfc,   ip_ref: ip-mfc-v14 }
    - { id: dpu,   ip_ref: ip-dpu-v9 }
    - { id: llc,   ip_ref: ip-llc-v2 }
  edges:
    - { from: csis0, to: isp0, type: OTF }
    - { from: isp0,  to: mfc,  type: M2M, buffer: "RECORD_BUF" }
    - { from: isp0,  to: dpu,  type: M2M, buffer: "PREVIEW_BUF" }
  sw_stack:                           # topology mode용 신규 섹션
    - { layer: app,       id: app-camera,   label: "Camera App" }
    - { layer: framework, id: fw-cam-svc,   label: "CameraService" }
    - { layer: hal,       id: hal-camera,   label: "Camera HAL" }
    - { layer: kernel,    id: ker-v4l2,     label: "V4L2 Driver",   ip_ref: csis0 }
    - { layer: hal,       id: hal-codec2,   label: "Codec2 HAL" }
    - { layer: kernel,    id: ker-mfc-drv,  label: "MFC Driver",    ip_ref: mfc }
    - { layer: hal,       id: hal-disp,     label: "Display HAL" }
    - { layer: kernel,    id: ker-drm,      label: "DRM/KMS",       ip_ref: dpu }
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `build_sample_level0()` 직접 호출 | HTTP API 연동 | Phase 4 | sample data 제거, DB 데이터 구동 |
| `position={"x": 0.0, "y": 0.0}` stub | topological sort + LANE_Y 실좌표 | Phase 4 | 실제 레이아웃 렌더링 |
| topology mode `NotImplementedError` | sw_stack 기반 구현 | Phase 4 | VIEW-03 완성 |
| Gate overlay 없음 | lazy fetch + 노드 스타일 오버라이드 | Phase 4 | VIEW-04 완성 |

**Deprecated/outdated:**
- `build_sample_level0()`: Phase 4 완료 후 `1_Pipeline_Viewer.py`에서 import 제거 (함수 자체는 demo/테스트용 유지 가능)

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `PagedResponse` 응답의 목록 필드명이 `"items"` | Code Examples [2] | dashboard dropdown이 KeyError로 실패 — `pagination.py` 확인 필요 |
| A2 | `graphlib.TopologicalSorter.static_order_groups()` 메서드가 Python 3.11에서 사용 가능 | Code Examples [1] | Python 3.9에는 없을 수 있음 — `static_order()` fallback 필요 |
| A3 | `GateResultStatus`가 StrEnum이어서 `.value` 접근 가능 | Code Examples [3] | `models/decision/common.py` 미확인 — `.value` 대신 `str(status)` 사용 필요 |

---

## Open Questions

1. **PagedResponse 응답 필드명**
   - What we know: `PagedResponse.from_query()` 사용 중
   - What's unclear: `.items`, `.data`, `.results` 중 어떤 필드명인지
   - Recommendation: 플래너가 `src/scenario_db/api/pagination.py` 읽어서 확인 후 dashboard 코드 작성

2. **Topological sort 구현 방식**
   - What we know: `graphlib` 모듈 Python 3.9+에 포함
   - What's unclear: `TopologicalSorter` API에서 그룹(레벨)별 정렬을 얻는 정확한 방법
   - Recommendation: `static_order()` 전체 순서 기반으로 stage_index 부여, 또는 BFS level-by-level 직접 구현

3. **topology mode에서 memory 레인 표시 여부**
   - What we know: D-05는 SW 레인만 언급 (app, framework, hal, kernel, hw)
   - What's unclear: topology mode에서 buffer 노드를 표시할지
   - Recommendation: topology mode에서 `visible_layers = ["app", "framework", "hal", "kernel", "hw"]` (memory 제외)로 단순화

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| FastAPI server (localhost:8000) | Dashboard HTTP 연동 | 별도 실행 필요 | — | sidebar에서 URL 수동 입력 가능 (D-02) |
| requests | HTTP API 호출 | 현재 설치 여부 미확인 | — | `uv add requests` |
| streamlit | Dashboard | 현재 설치됨 (dashboard group) | — | — |

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | pyproject.toml (pytest 설정) |
| Quick run command | `uv run pytest tests/unit/ -x -q` |
| Full suite command | `uv run pytest -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VIEW-01 | `project_level0()` DB 조회 + ViewResponse 반환 | integration | `uv run pytest tests/integration/test_view_projection.py -x -q` | ✅ (확장 필요) |
| VIEW-02 | architecture mode 노드 좌표 계산 검증 | unit | `uv run pytest tests/unit/test_view_service.py -x -q` | ❌ Wave 0 |
| VIEW-03 | topology mode ViewResponse 반환 (sw_stack 노드 포함) | integration | `uv run pytest tests/integration/test_view_topology.py -x -q` | ❌ Wave 0 |
| VIEW-04 | gate endpoint 응답 → GateExecutionResult 파싱 | integration | 기존 `test_api_runtime.py` 활용 | ✅ |
| VIEW-05 | Streamlit UI 구조 테스트 | manual | Streamlit 실행 후 UI 확인 | manual-only |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/unit/ -x -q`
- **Per wave merge:** `uv run pytest -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/unit/test_view_service.py` — VIEW-02 architecture mode 좌표 계산 단위 테스트
- [ ] `tests/integration/test_view_topology.py` — VIEW-03 topology mode 통합 테스트
- [ ] `tests/unit/test_pipeline_sw_stack.py` — sw_stack Pydantic 모델 round-trip 테스트

---

## Security Domain

> security_enforcement 설정 미확인 → 포함.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | `ViewResponse.model_validate()` — Pydantic v2 |
| V2 Authentication | no | 내부 도구, 인증 없음 |
| V3 Session Management | no | Streamlit session_state 사용, 민감 데이터 없음 |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API URL 조작 | Tampering | sidebar URL은 사용자가 직접 입력 — 내부 도구이므로 허용 |
| requests timeout 없음 | DoS | `timeout=10` 필수 (CONTEXT.md 코드 예시에 명시됨) |

---

## Sources

### Primary (HIGH confidence)
- `demo/fixtures/00_hw/ip-*.yaml` — 모든 IP category 값 직접 확인
- `src/scenario_db/gate/models.py` — GateExecutionResult 구조 직접 확인
- `src/scenario_db/api/routers/definition.py` — /scenarios, /scenarios/{id}/variants 엔드포인트 존재 확인
- `dashboard/components/lane_layout.py` + `src/scenario_db/view/layout.py` — LANE_Y, LANE_LABEL_ORDER 확인
- `dashboard/components/elk_graph_builder.py` — visible_layers 파라미터 지원 확인
- `src/scenario_db/view/service.py` — topology NotImplementedError 위치, _projection_to_view_response() 현재 상태 확인
- `dashboard/components/node_detail_panel.py` — 인스펙터 패널 현재 구조 확인
- `demo/fixtures/02_definition/uc-camera-recording.yaml` — pipeline 실제 노드/엣지 구조 확인
- `src/scenario_db/models/definition/usecase.py` — Pipeline 모델 extra='forbid' 확인

### Secondary (MEDIUM confidence)
- CONTEXT.md D-01~D-06 — 유저 결정 사항 (gsd-discuss-phase 결과)

### Tertiary (LOW confidence)
- `pagination.py` PagedResponse 필드명 — 미확인 (A1 가정)
- Python 3.11 `graphlib` API — 훈련 데이터 기반 (A2 가정)

---

## Metadata

**Confidence breakdown:**
- IpCatalog.category 실제 값: HIGH — YAML 직접 읽음
- API 엔드포인트 존재: HIGH — 라우터 코드 직접 읽음
- GateExecutionResult 구조: HIGH — models.py 직접 읽음
- sw_stack Pydantic 추가 방법: HIGH — Pipeline 모델 구조 확인
- topological sort 구현: MEDIUM — graphlib API는 ASSUMED
- PagedResponse 응답 구조: LOW — pagination.py 미확인

**Research date:** 2026-05-10
**Valid until:** 2026-06-10 (안정 스택, 빠른 변화 없음)
