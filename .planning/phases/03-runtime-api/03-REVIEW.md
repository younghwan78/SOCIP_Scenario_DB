---
phase: 03-runtime-api
reviewed: 2026-05-10T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - src/scenario_db/api/routers/runtime.py
  - src/scenario_db/api/app.py
  - src/scenario_db/api/routers/view.py
  - src/scenario_db/view/service.py
  - tests/integration/test_api_runtime.py
findings:
  critical: 3
  warning: 4
  info: 3
  total: 10
status: issues_found
---

# Phase 03: Code Review Report — Runtime API

**Reviewed:** 2026-05-10
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Runtime API (graph / resolve / gate) 및 view 라우터 전반을 표준 깊이로 검토했다.
라우터 자체의 구조는 비교적 단순하지만, 의존 계층(service, utility, cache)에서
런타임 크래시로 이어질 수 있는 결함 3건을 확인했다. 특히 `/health/ready` 엔드포인트의
context manager 오용, `_projection_to_view_response`의 KeyError 무방비 접근,
`test_api_runtime.py`의 VARIANT_ID 불일치가 BLOCKER로 분류된다.

---

## Critical Issues

### CR-01: `/health/ready` — `session_factory()` 반환값에 `with` 사용 시 런타임 크래시

**File:** `src/scenario_db/api/routers/utility.py:27`

**Issue:**
`make_session_factory(engine)` 는 `sessionmaker` 인스턴스를 반환하고,
`session_factory()` 호출은 일반 `Session` 객체를 반환한다.
SQLAlchemy `Session`은 컨텍스트 매니저(`__enter__`/`__exit__`)를 지원하지 *않는다*
(SQLAlchemy 1.x 기준; 2.x에서는 지원하지만 프로젝트는 `sessionmaker(bind=engine, ...)`
방식의 1.x 스타일 API를 혼용). `make_session_factory`의 반환 타입이
`sessionmaker[Session]`임을 보면 `Session()` 호출로 새 객체를 얻는데,
이 객체에 `with` 블록을 걸면 `AttributeError: __exit__` 또는 세션 누수가 발생한다.
`get_db` 의존성은 `try/finally`로 수동 close를 수행하는 반면, readiness 핸들러만
`with` 패턴을 사용해 불일치가 있다.

```python
# 현재 (utility.py:27) — AttributeError 위험
with request.app.state.session_factory() as s:
    s.execute(text("SELECT 1"))
```

**Fix:**
```python
# get_db와 동일한 수동 close 패턴 사용
s = request.app.state.session_factory()
try:
    s.execute(text("SELECT 1"))
    db_ok = True
finally:
    s.close()
```

---

### CR-02: `_projection_to_view_response` — `node["id"]` 직접 접근으로 KeyError 발생 가능

**File:** `src/scenario_db/view/service.py:241`

**Issue:**
`projection.get("pipeline", {}).get("nodes", [])` 로 얻은 `node` dict에서
`node["id"]`를 직접 접근한다. `get_view_projection`이 반환하는 `nodes` 리스트는
DB에 저장된 `scenario.pipeline` JSONB를 그대로 전달하며,
YAML 명세상 `id` 필드가 필수이지만 ETL 레이어에서 이를 강제하지 않는다.
pipeline 노드에 `id` 키가 없으면 `KeyError`로 500 에러가 발생한다.
바로 다음 줄 `label=node.get("id", "")` 는 `.get()`을 사용해 방어하는데,
이는 `node["id"]`가 KeyError를 낼 수 있음을 암묵적으로 인정하는 모순이다.

```python
# 현재 (service.py:241) — node에 "id" 없으면 KeyError → 500
id=node["id"],
label=node.get("id", ""),  # 동일 키인데 방어 패턴 불일치
```

**Fix:**
```python
node_id = node.get("id")
if not node_id:
    continue  # id 없는 노드는 건너뛰거나 WARNING 로그
NodeElement(
    data=NodeData(
        id=node_id,
        label=node_id,
        type="ip",
        layer="hw",
    ),
    position={"x": 0.0, "y": 0.0},
)
```

---

### CR-03: 테스트 `VARIANT_ID`가 demo fixture와 불일치 — 404로 테스트 항상 실패

**File:** `tests/integration/test_api_runtime.py:8`

**Issue:**
테스트 파일 상단에 `VARIANT_ID = "UHD60-HDR10-H265"` 로 정의되어 있다.
`/view` 엔드포인트 테스트(`test_view_architecture_mode`, `test_view_topology_mode_returns_501`)는
이 VARIANT_ID를 그대로 사용하여 `project_level0()`을 호출하고,
`project_level0`은 `get_view_projection(db, scenario_id, variant_id)`를 통해
DB에서 조회한다.

그런데 `get_view_projection`이 반환하는 `projection` 에는 `variant_id`가 포함되어 있고
`_projection_to_view_response`는 `projection["variant_id"]` 로 `ViewResponse.variant_id`를
채운다.

`test_view_architecture_mode`는 `data["variant_id"] == VARIANT_ID` 를 단언하므로
픽스처에 `UHD60-HDR10-H265` variant가 없으면 404 를 받아 테스트가 실패한다.
데모 픽스처 `uc-camera-recording.yaml`에는 `UHD60-HDR10-H265` variant가
존재하므로 graph/resolve/gate 3개 엔드포인트는 통과할 수 있지만,
`view` 엔드포인트는 `project_level0`이 이 variant에 대한 view projection을
정확히 반환해야 `data["variant_id"] == VARIANT_ID` 단언이 통과된다.
`_projection_to_view_response`가 `projection["variant_id"]`(=`"UHD60-HDR10-H265"`)를
그대로 쓰므로 DB에 해당 variant가 있으면 일치하지만,
만약 픽스처 로딩 순서나 ETL 실패로 variant가 없으면 404 → assertion fail 으로
테스트 신뢰성 문제가 된다. 더 큰 문제는 동일 `VARIANT_ID`로 `graph`, `resolve`, `gate`,
`view` 엔드포인트를 모두 묶어 테스트하면서 view 엔드포인트만 다른 코드 경로
(`project_level0` → `get_view_projection`)를 타는데, 이에 대한 404 케이스 테스트가
없다. 즉 view 404 시나리오는 테스트 커버리지 밖에 있다.

**Fix:**
```python
# test_api_runtime.py 에 추가
def test_view_404(api_client: TestClient):
    resp = api_client.get("/api/v1/scenarios/no-such-id/variants/no-such-vid/view",
                          params={"level": 0, "mode": "architecture"})
    assert resp.status_code == 404
```

그리고 `VARIANT_ID`의 실제 픽스처 존재 여부를 `conftest.py` session fixture에서
검증하거나, 테스트별로 다른 fixture ID를 명시할 것.

---

## Warnings

### WR-01: `project_level0` — invalid `mode` 값을 `NotImplementedError`로 처리하지만 실제로는 도달 불가 경로

**File:** `src/scenario_db/view/service.py:280-283`

**Issue:**
```python
if mode not in ("architecture", "topology"):
    raise NotImplementedError(f"mode '{mode}' is not supported")
if mode == "topology":
    raise NotImplementedError("topology mode is Phase 4 work")
```
첫 번째 조건이 `architecture` 또는 `topology` 이외의 값은 모두 차단한다.
따라서 두 번째 `if mode == "topology"` 까지 도달하는 경우는
`mode == "topology"` 뿐이다. 이는 정확하지만,
라우터 레이어(`view.py`)에서 `Query(description="architecture | topology")`로
hint만 제공하고 실제 validation은 없으므로, `mode="foobar"` 로 요청하면
service에서 `NotImplementedError` → 라우터에서 501로 변환된다.
이는 클라이언트 입력 오류(422 expected)를 서버 미구현(501)으로 오해하게 만든다.
또한 `mode` 파라미터에 `Literal["architecture", "topology"]` 타입 힌트와 Pydantic 검증을
라우터 레이어에서 수행하지 않아 422 vs 501 혼동이 발생한다.

**Fix:**
```python
# view.py 라우터에서 mode 를 검증
from typing import Literal
mode: Literal["architecture", "topology"] = Query("architecture", ...)
```
또는 service에서 invalid mode 를 `ValueError` 로 올리고 라우터에서 422로 변환.

---

### WR-02: `runtime.py` — `NoResultFound` 직접 raise가 예외 핸들러에 의존

**File:** `src/scenario_db/api/routers/runtime.py:33,49,69`

**Issue:**
`get_graph`, `get_resolve`, `get_gate` 세 핸들러 모두 `NoResultFound`를 직접
raise하여 `exceptions.py`의 `_not_found_handler`가 404로 변환하도록 위임한다.
이 패턴은 동작하지만 `NoResultFound`는 SQLAlchemy 내부 예외로, 도메인 로직에서
DB 예외를 직접 raise하면 계층 경계(API ↔ 도메인)가 흐려진다.
`graph is None` 체크 후 HTTP 레이어 예외(`HTTPException(404)`)를 raise하는 것이
FastAPI 관례상 더 명확하다. 특히 `get_canonical_graph`는 이미 `None`을 반환하므로
라우터가 `HTTPException`을 올리는 것이 자연스럽다.
현재 방식은 `NoResultFound` 핸들러가 등록되지 않은 환경(예: 단위 테스트)에서
500으로 노출될 수 있다.

**Fix:**
```python
from fastapi import HTTPException

if graph is None:
    raise HTTPException(
        status_code=404,
        detail=f"scenario '{scenario_id}' / variant '{variant_id}' not found",
    )
```

---

### WR-03: `view/service.py` — `_projection_to_view_response` 에서 `type="ip"`, `layer="hw"` 하드코딩

**File:** `src/scenario_db/view/service.py:243-244`

**Issue:**
DB에서 가져온 pipeline 노드들을 모두 `type="ip"`, `layer="hw"` 로 고정한다.
`uc-camera-recording.yaml`의 pipeline 노드는 ISP, MFC, DPU, LLC 등 HW IP 이지만,
다른 scenario에는 SW 컴포넌트나 DMA 그룹 노드가 포함될 수 있다.
`NodeData.type` 필드는 `Literal["sw", "ip", "submodule", "buffer", ...]` 이므로
pipeline 노드에 `type` 필드가 존재하면 이를 읽어야 하고,
없으면 폴백 로직이 있어야 한다. 현재는 모든 노드를 HW IP로 분류해 잘못된 메타데이터를
반환한다.

**Fix:**
```python
node_type = node.get("type", "ip")
node_layer = node.get("lane_id", "hw")  # 또는 pipeline 노드 스키마의 실제 필드
NodeData(
    id=node_id,
    label=node_id,
    type=node_type if node_type in NodeData.model_fields["type"].annotation.__args__ else "ip",
    layer=node_layer,
)
```

---

### WR-04: `get_settings()` 전역 싱글톤 — 테스트 격리 위험

**File:** `src/scenario_db/config.py:23-29`

**Issue:**
`_settings`를 모듈 레벨 전역 변수로 캐싱하는 패턴은 테스트 실행 순서에 따라
첫 번째 테스트가 설정한 값이 이후 모든 테스트에 고정된다.
`conftest.py`에서 `os.environ["DATABASE_URL"] = url`을 설정하지만
`get_settings()`가 이미 한번 호출된 이후라면 변경이 반영되지 않는다.
`integration/conftest.py`의 `engine` fixture가 `os.environ["DATABASE_URL"] = url`을
설정하는 시점보다 `create_app()`(또는 다른 코드)이 먼저 `get_settings()`를 호출하면
SQLite in-memory URL로 고정된다.

**Fix:**
```python
def get_settings() -> Settings:
    # 테스트에서는 매번 새로 파싱하거나, functools.lru_cache 사용 후 cache_clear() 제공
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

# 테스트 코드에서:
# from scenario_db.config import get_settings
# get_settings.cache_clear()  # lru_cache 전환 시
```
또는 `pydantic_settings`의 `model_post_init` / `@lru_cache` + `cache_clear` 패턴으로
교체.

---

## Info

### IN-01: `build_sample_level0()` — 데드코드 (아무 곳에서도 호출되지 않음)

**File:** `src/scenario_db/view/service.py:38`

**Issue:**
`build_sample_level0()` 함수가 정의되어 있지만 같은 파일 내부에서도,
`view.py` 라우터에서도, dashboard 코드에서도 import/호출되지 않는다.
Phase 3에서 DB 기반 `project_level0`으로 교체된 이후 잔존한 데드코드로 보인다.
약 190라인 분량의 하드코딩된 샘플 데이터가 유지 비용을 발생시킨다.

**Fix:**
삭제하거나, 명시적으로 `# 개발/데모 전용` 주석 + `__all__` 에서 제외.
또는 별도 `demo.py` 모듈로 분리.

---

### IN-02: `NodeData` — 가변 기본값 `list[str] = []` Pydantic v2에서는 안전하지만 명시성 부족

**File:** `src/scenario_db/api/schemas/view.py:63-64,70`

**Issue:**
```python
summary_badges: list[str] = []
capability_badges: list[str] = []
matched_issues: list[str] = []
```
Pydantic v2는 내부적으로 mutable default를 `default_factory`로 처리하므로
공유 객체 문제는 없다. 그러나 `model_config = ConfigDict(extra='forbid')` 가
없어 CLAUDE.md 코딩 컨벤션("모든 Pydantic 모델에 `extra='forbid'`")을 위반한다.
예상치 못한 필드가 조용히 통과된다.

**Fix:**
```python
from pydantic import ConfigDict

class NodeData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ...
```
`ViewHints`, `OperationSummary`, `MemoryDescriptor`, `MemoryPlacement`,
`EdgeData`, `RiskCard`, `ViewSummary`, `ViewResponse` 전체에도 동일 적용.

---

### IN-03: 테스트 — view level=1, level=2 에 대한 501 케이스 미검증

**File:** `tests/integration/test_api_runtime.py`

**Issue:**
`test_view_topology_mode_returns_501` 은 level=0 topology 를 검증하지만,
level=1 (`project_level1`), level=2 (`project_level2`) 는 모두 `NotImplementedError`
를 raise하므로 항상 501이 반환된다. 이 케이스들에 대한 테스트가 없으므로
향후 level=1/2 구현 시 기존 계약이 깨져도 테스트가 잡아내지 못한다.

**Fix:**
```python
def test_view_level1_returns_501(api_client: TestClient):
    resp = api_client.get(
        f"/api/v1/scenarios/{SCENARIO_ID}/variants/{VARIANT_ID}/view",
        params={"level": 1},
    )
    assert resp.status_code == 501

def test_view_level2_without_expand_returns_422(api_client: TestClient):
    resp = api_client.get(
        f"/api/v1/scenarios/{SCENARIO_ID}/variants/{VARIANT_ID}/view",
        params={"level": 2},
    )
    assert resp.status_code == 422
```

---

_Reviewed: 2026-05-10_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
