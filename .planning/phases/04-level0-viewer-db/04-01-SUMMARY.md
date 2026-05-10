---
phase: "04"
plan: "01"
subsystem: "view-service"
tags: [view, architecture-mode, topological-sort, sw-stack, pydantic]
dependency_graph:
  requires: []
  provides: [SwStackNode-model, Pipeline-sw_stack-field, _projection_to_view_response-real-coords]
  affects: [service.py, usecase.py, uc-camera-recording.yaml]
tech_stack:
  added: [graphlib.TopologicalSorter]
  patterns: [CATEGORY_TO_LANE-mapping, stage_index-x-coords, LANE_Y-y-coords]
key_files:
  created:
    - tests/unit/test_pipeline_sw_stack.py
    - tests/unit/test_view_service.py
  modified:
    - src/scenario_db/models/definition/usecase.py
    - src/scenario_db/view/service.py
    - demo/fixtures/02_definition/uc-camera-recording.yaml
decisions:
  - "CATEGORY_TO_LANE: category 값 기반 (camera/codec/display/memory → hw), id 기반 아님"
  - "graphlib.TopologicalSorter 배치 API: prepare()+is_active()+get_ready()+done() 패턴"
  - "x좌표: LANE_LABEL_W + stage_idx * STAGE_STEP(310) + STAGE_STEP//2"
  - "db=None일 때 build_sample_level0() fallback 유지 (dashboard demo mode)"
metrics:
  duration: "30m"
  completed: "2026-05-10"
  tasks_completed: 5
  files_changed: 5
---

# Phase 4 Plan 1: Service Layer 확장 — Architecture Mode 실좌표 계산 Summary

## One-liner

`service.py`의 stub `position={"x":0.0,"y":0.0}`을 graphlib topological sort + CATEGORY_TO_LANE 매핑 기반 실좌표 계산으로 교체하고, `SwStackNode` Pydantic 모델과 YAML `sw_stack` 섹션을 추가했다.

## What Was Built

### Task 1: SwStackNode 모델 + Pipeline.sw_stack 필드 (b105fba)

`src/scenario_db/models/definition/usecase.py`에 추가:

- `SwStackNode(BaseScenarioModel)`: `layer: Literal["app","framework","hal","kernel"]`, `id: str`, `label: str`, `ip_ref: str|None = None`
- `Pipeline.sw_stack: list[SwStackNode] = Field(default_factory=list)` (기존 `edges` 필드 뒤)
- `BaseScenarioModel` 상속으로 `extra='forbid'` 자동 적용 — 별도 config 불필요
- 하위 호환 보장: sw_stack 없는 기존 YAML도 그대로 유효

### Task 2: sw_stack 테스트 + YAML fixture 수정 (118b8af)

`tests/unit/test_pipeline_sw_stack.py` 신규 생성 (4개 테스트):
- `test_pipeline_accepts_sw_stack`: sw_stack 포함 Pipeline 검증
- `test_pipeline_without_sw_stack_is_valid`: 하위 호환 확인
- `test_sw_stack_round_trip`: SwStackNode serialization round-trip
- `test_sw_stack_invalid_layer_raises`: `hw` 레이어 거부 확인

`demo/fixtures/02_definition/uc-camera-recording.yaml` — `sw_stack` 섹션 추가:
- 8개 노드: app-camera, fw-cam-svc, hal-camera, ker-v4l2(ip_ref=csis0), hal-codec2, ker-mfc-drv(ip_ref=mfc), hal-disp, ker-drm(ip_ref=dpu)
- Pydantic 모델 검증 완료 (`uv run python -c "..."`)

ETL 재실행: DATABASE_URL 미설정 환경이므로 Pydantic 모델 직접 검증으로 대체 완료.

### Task 3: service.py 실좌표 계산 구현 (c50272e)

`src/scenario_db/view/service.py`에 추가:

```
CATEGORY_TO_LANE: {"camera": "hw", "codec": "hw", "display": "hw", "memory": "hw"}
STAGE_STEP: 310  # px per stage
```

`_projection_to_view_response()` 신규 구현:
1. `ip_catalog` dict 구성: `{ip_id: ip_dict}`
2. `graphlib.TopologicalSorter`: `prepare()` → `while is_active(): batch=get_ready(); done(*batch)` 패턴
3. x좌표: `LANE_LABEL_W(80) + stage_idx * 310 + 155` (stage 0=235, 1=545, 2=855)
4. y좌표: `LANE_Y[lane]` (layout.py 기존 상수)
5. edges: flow_type 검증 (`OTF/vOTF/M2M/control/risk`, fallback `M2M`)

`project_level0()` 시그니처 확장: `mode="architecture"` 파라미터 추가, topology mode `NotImplementedError`.

### Task 4: service.py 단위 테스트 (ed0e1fa)

`tests/unit/test_view_service.py` 신규 생성 (9개 테스트):
- hw lane 배치 검증
- x좌표 단조 증가 (`csis0 < isp0 < mfc`)
- y좌표 `LANE_Y["hw"]` 일치
- EdgeElement 변환 (OTF, M2M flow_type)
- stub position `(0,0)` 부재 확인
- `CATEGORY_TO_LANE` 상수 검증
- isolated node stage_0 배치
- unknown category hw fallback
- 빈 pipeline 처리

### Task 5: 전체 테스트 실행 확인

`uv run pytest tests/unit/ -x -q` → **243 passed**

## Commits

| Hash | Task | Description |
|------|------|-------------|
| b105fba | Task 1 | feat(04-01): add SwStackNode model and Pipeline.sw_stack field |
| 118b8af | Task 2 | feat(04-01): add sw_stack section to YAML fixture + round-trip tests |
| c50272e | Task 3 | feat(04-01): implement _projection_to_view_response() with real coordinates |
| ed0e1fa | Task 4 | test(04-01): add _projection_to_view_response() unit tests (VIEW-02) |

## Deviations from Plan

### Auto-fixed Issues

없음.

### Context Discovery

**worktree 버전 차이**: 이 worktree 브랜치는 Phase 3 이전 커밋(384bd3d 기준)에서 분기하여, `service.py`가 Phase 3 버전(stub `_projection_to_view_response()` + `project_level0()`)이 없는 상태였다. PLAN.md는 Phase 3 버전에서 확장하는 시나리오였으나, worktree에는 해당 함수가 없어 전체를 신규 구현했다. 결과적으로 동일한 기능 목표를 달성했다.

**ETL 재실행 불가**: 이 환경에 `DATABASE_URL`이 없어 ETL loader 실행 시 `KeyError: 'DATABASE_URL'`이 발생한다. 대신 `uv run python -c "..."` Pydantic 직접 검증으로 YAML 스키마 호환성을 확인했다.

**view_projection.py 부재**: worktree에는 `src/scenario_db/db/repositories/view_projection.py`가 없다. `project_level0()`의 `db is None` 분기에서 `build_sample_level0()` fallback을 유지하고, `db` 파라미터가 주어질 때만 `get_view_projection()` import를 시도하도록 구현했다.

## Test Results

```
tests/unit/test_pipeline_sw_stack.py  4 passed
tests/unit/test_view_service.py       9 passed
tests/unit/                          243 passed total
```

## Known Stubs

- `ViewSummary.period_ms`, `budget_ms`, `resolution`, `fps`, `variant_label`: 모두 placeholder (0.0/"") — Wave 2(04-PLAN-02)에서 DB 데이터로 보완 예정
- `project_level0()` topology mode: `NotImplementedError` — 04-PLAN-03에서 구현 예정

## Threat Flags

없음 — 서버사이드 순수 Python 로직. 신뢰 경계는 DB projection dict (ETL 검증 완료).

## Self-Check

### Created files exist
- [x] `tests/unit/test_pipeline_sw_stack.py`
- [x] `tests/unit/test_view_service.py`
- [x] `.planning/phases/04-level0-viewer-db/04-01-SUMMARY.md`

### Modified files verified
- [x] `src/scenario_db/models/definition/usecase.py` — SwStackNode + Pipeline.sw_stack
- [x] `src/scenario_db/view/service.py` — _projection_to_view_response() + CATEGORY_TO_LANE
- [x] `demo/fixtures/02_definition/uc-camera-recording.yaml` — sw_stack 8노드

### Commits exist
- [x] b105fba
- [x] 118b8af
- [x] c50272e
- [x] ed0e1fa

### Test gate
- [x] 243 unit tests passed

## Self-Check: PASSED
