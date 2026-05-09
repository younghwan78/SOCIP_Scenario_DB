# Phase 3: Runtime API — Context

**Gathered:** 2026-05-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1/2 산출물을 HTTP 엔드포인트로 노출하고, view router의 sample fallback을 제거한다.

- 신규: GET /api/v1/scenarios/{id}/variants/{vid}/graph → CanonicalScenarioGraph JSON
- 신규: GET /api/v1/scenarios/{id}/variants/{vid}/resolve → ResolverResult JSON
- 신규: GET /api/v1/scenarios/{id}/variants/{vid}/gate → GateExecutionResult JSON
- 수정: view router mode 파라미터 실제 분기 + sample fallback 코드 경로 제거

모든 신규 엔드포인트는 기존 `get_db` + `get_rule_cache` 의존성 패턴을 그대로 사용.

</domain>

<decisions>
## Implementation Decisions

### Router 파일 구조 (API-01~03)

- **D-01:** `src/scenario_db/api/routers/runtime.py` 신규 생성 — /graph, /resolve, /gate 3개 엔드포인트를 하나의 파일로 관리
  - 기존 `definition.py` 오염 없음
  - `app.py`에 `runtime.router` include 추가 (`prefix="/api/v1"`)

### 응답 스키마 (API-01, API-02, API-03)

- **D-02:** CanonicalScenarioGraph를 `/graph` 엔드포인트의 `response_model`로 직접 사용
  - CanonicalScenarioGraph는 이미 `ConfigDict(extra='forbid')`가 설정된 Pydantic BaseModel
  - 별도 GraphResponse API 스키마 불필요 — 중복 구조 방지
  - ORM 객체가 아닌 순수 Pydantic 모델이므로 직렬화 즉시 가능

- **D-03:** ResolverResult를 `/resolve` 엔드포인트의 `response_model`로 직접 사용
  - `resolver/models.py`의 `ResolverResult(ConfigDict(extra='forbid'))` 그대로

- **D-04:** GateExecutionResult를 `/gate` 엔드포인트의 `response_model`로 직접 사용
  - `gate/models.py`의 `GateExecutionResult(ConfigDict(extra='forbid'))` 그대로

### Gate 엔드포인트 RuleCache 주입 (API-03)

- **D-05:** `get_rule_cache` FastAPI 의존성으로 RuleCache 주입
  - `RuleCache.loaded=False` 이거나 `gate_rules=[]`이면 `evaluate_gate(graph, [])` 호출 → status=PASS 반환
  - 503 에러 없음 — empty cache는 허용 (서버 시작 실패 방지를 위한 기존 설계 준수)

### View Router Sample Fallback 제거 (API-04)

- **D-06:** `service.py`의 `project_level0()` 에서 `db=None` 분기 완전 제거
  - 기존: `if db is None: return build_sample_level0()` → 삭제
  - `db` 파라미터를 필수(non-optional)로 변경
  - `build_sample_level0()` 함수는 삭제하지 않음 (테스트에서 직접 참조 가능성, 또는 다른 용도 가능)
    - 단, `project_level0()`에서는 호출 안 함

- **D-07:** `mode` 파라미터 실제 분기 추가
  - `mode='topology'` → `raise NotImplementedError("topology mode is Phase 4 work")`
  - `mode='architecture'` (기본값) → DB projection 기반 최소 ViewResponse 반환

- **D-08:** architecture mode 임시 구현 (Phase 4 전까지)
  - `get_view_projection(db, scenario_id, variant_id)` 결과에서 `pipeline.nodes` 를 NodeElement 리스트로 변환
  - 위치(x/y)는 None/미설정 (ELK 레이아웃은 Phase 4 VIEW-01 작업)
  - nodes 변환 공식: `NodeData(id=node['id'], label=node.get('id',''), type='ip', layer='hw')`
  - edges=[], risks=[], summary는 DB 기반 최소값으로 채움

### 에러 처리

- **D-09:** 존재하지 않는 scenario_id / variant_id → `NotFoundError` 발생 (기존 `api/exceptions.py` 패턴 재사용)
  - `get_canonical_graph()` 반환값이 None → NotFoundError
  - `get_view_projection()` 반환값이 None → NotFoundError

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 요구사항
- `.planning/REQUIREMENTS.md` §API-01~API-04 — Phase 3 요구사항 전체
- `.planning/ROADMAP.md` §Phase 3 — Success Criteria 5개 항목

### 기존 코드 (수정 대상)
- `src/scenario_db/api/app.py` — `runtime.router` include 추가 위치
- `src/scenario_db/api/routers/view.py` — `mode` 파라미터를 service.py에 전달하도록 수정
- `src/scenario_db/view/service.py` — sample fallback 제거 + DB projection 기반 구현

### Phase 1/2 산출물 (재사용)
- `src/scenario_db/db/repositories/scenario_graph.py` — `get_canonical_graph()` + `CanonicalScenarioGraph` DTO
- `src/scenario_db/resolver/engine.py` — `resolve(graph) -> ResolverResult`
- `src/scenario_db/resolver/models.py` — `ResolverResult`
- `src/scenario_db/gate/engine.py` — `evaluate_gate(graph, gate_rules) -> GateExecutionResult`
- `src/scenario_db/gate/models.py` — `GateExecutionResult`
- `src/scenario_db/db/repositories/view_projection.py` — `get_view_projection()`

### 기존 패턴 (그대로 재사용)
- `src/scenario_db/api/deps.py` — `get_db`, `get_rule_cache` FastAPI 의존성
- `src/scenario_db/api/exceptions.py` — `NotFoundError` (404)
- `src/scenario_db/api/routers/definition.py` — 라우터 구조 패턴 참조
- `src/scenario_db/api/cache.py` — `RuleCache` 구조

### 신규 파일 위치
- `src/scenario_db/api/routers/runtime.py` — /graph, /resolve, /gate 엔드포인트

### 통합 테스트 패턴
- `tests/integration/conftest.py` — engine fixture (PostgreSQL testcontainers)
- `tests/integration/test_api_definition.py` — FastAPI TestClient 통합 테스트 패턴

</canonical_refs>

<code_context>
## Existing Code Insights

### 라우터 등록 패턴 (app.py)
```python
from scenario_db.api.routers import runtime as runtime_router
# lifespan 이후 include_router 리스트에 추가:
for r in [capability.router, definition.router, ..., runtime_router.router]:
    app.include_router(r, prefix="/api/v1")
```

### 의존성 패턴 (definition.py 참조)
```python
@router.get("/scenarios/{scenario_id}/variants/{variant_id}/graph",
            response_model=CanonicalScenarioGraph)
def get_graph(
    scenario_id: str,
    variant_id: str,
    db: Session = Depends(get_db),
):
    graph = get_canonical_graph(db, scenario_id, variant_id)
    if graph is None:
        raise NotFoundError(f"scenario '{scenario_id}' / variant '{variant_id}' not found")
    return graph
```

### 현재 view.py 문제점
- `mode` 파라미터를 받지만 `project_level0(scenario_id, variant_id, db=db)` 에 전달 안 함
- `project_level0()`이 내부적으로 `if db is None: return build_sample_level0()` 분기 존재
- Phase 3: `mode=mode`를 전달하고 service.py에서 분기 처리

### architecture mode 최소 ViewResponse 구성
```python
from scenario_db.api.schemas.view import NodeData, NodeElement, ViewResponse, ViewSummary

def _projection_to_view_response(projection: dict) -> ViewResponse:
    nodes = [
        NodeElement(data=NodeData(
            id=node["id"],
            label=node.get("id", ""),
            type="ip",
            layer="hw",
        ))
        for node in projection.get("pipeline", {}).get("nodes", [])
    ]
    summary = ViewSummary(
        scenario_id=projection["scenario_id"],
        variant_id=projection["variant_id"],
        name=projection.get("project_name") or projection["scenario_id"],
    )
    return ViewResponse(
        level=0,
        mode="architecture",
        scenario_id=projection["scenario_id"],
        variant_id=projection["variant_id"],
        nodes=nodes,
        edges=[],
        risks=[],
        summary=summary,
    )
```

### ViewSummary 필수 필드 확인 필요
- `api/schemas/view.py`의 `ViewSummary` 필수 필드 목록을 확인하여 최소 생성 가능한지 검증

### 기존 통합 테스트 패턴 (TestClient)
```python
from fastapi.testclient import TestClient
from scenario_db.api.app import create_app

@pytest.fixture(scope="session")
def client(engine):
    app = create_app()
    app.state.engine = engine
    # ... session_factory, rule_cache 설정
    with TestClient(app) as c:
        yield c
```

</code_context>

<specifics>
## Specific Implementation Notes

- `runtime.py` 라우터 태그: `["runtime"]`
- URL 경로: `/scenarios/{scenario_id}/variants/{variant_id}/graph|resolve|gate`
- gate 엔드포인트에서 RuleCache: `cache: RuleCache = Depends(get_rule_cache)` → `evaluate_gate(graph, cache.gate_rules)`
- `/resolve` 엔드포인트는 RuleCache 불필요 (Resolver는 gate_rules 무관)
- view.py 수정: `mode: str = Query("architecture", ...)` → `project_level0(scenario_id, variant_id, mode=mode, db=db)`
- `project_level0()` 시그니처 변경: `db=None` → `db` (필수 파라미터)
  - **주의:** `view.py`에서 호출 시 항상 db가 전달되므로 None 케이스 삭제 가능
  - dashboard/Home.py, dashboard/pages/*.py에서 `project_level0()`을 직접 호출하는 부분이 있으면 수정 필요
    - 확인: `grep -r "project_level0" dashboard/` → db 없이 호출하는 경우 sample fallback 유지 여부 결정 필요

</specifics>

<deferred>
## Deferred Ideas

- ELK 기반 실제 레이아웃 (positions x/y) → Phase 4 VIEW-01
- topology mode 구현 → Phase 4 VIEW-03
- gate overlay in viewer → Phase 4 VIEW-04
- Level 1/2 view endpoints — v2 requirements
- `build_sample_level0()` 삭제 — Phase 4 완료 후 불필요 시 제거

</deferred>

---

*Phase: 03-Runtime-API*
*Context gathered: 2026-05-10*
