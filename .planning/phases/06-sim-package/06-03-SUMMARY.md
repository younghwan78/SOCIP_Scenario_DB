---
phase: 06-sim-package
plan: "03"
subsystem: sim-package
tags: [sim, dvfs-resolver, scenario-adapter, runner, tdd, end-to-end]
dependency_graph:
  requires: [phase-06-plan-01-infra, phase-06-plan-02-calc-functions]
  provides: [dvfs-resolver, scenario-adapter, run-simulation-api]
  affects: [phase-07-simulation-api]
tech_stack:
  added: []
  patterns: [tdd-red-green, pure-pydantic-no-orm, otf-group-constraint, vdd-voltage-alignment]
key_files:
  created:
    - src/scenario_db/sim/dvfs_resolver.py
    - src/scenario_db/sim/scenario_adapter.py
    - src/scenario_db/sim/runner.py
    - tests/sim/test_dvfs_resolver.py
    - tests/sim/test_scenario_adapter.py
    - tests/sim/test_runner.py
  modified: []
decisions:
  - "run_simulation() 시그니처: fps 인수 추가 (sensor_spec.fps 우선, 기본값 30.0) — SimGlobalConfig에 fps 필드 없으므로"
  - "DvfsResolver._get_pixels_from_port_config(): port_cfg outputs > inputs > FHD 기본값 우선순위"
  - "[Rule 1 - Bug] OTF 제약 테스트 기대값 수정: 계획의 '533MHz 이상' 오산 — 실제 105.88MHz는 400MHz(level2)로 충족 가능"
metrics:
  duration: "~5분"
  completed: "2026-05-16T14:37:13Z"
  tasks_completed: 2
  files_created: 6
  files_modified: 0
  tests_added: 11
  tests_passed: 11
---

# Phase 6 Plan 03: Wave 2 — DvfsResolver + scenario_adapter + runner Summary

Wave 2 오케스트레이션 계층 완성 — DvfsResolver(OTF 그룹 제약 + VDD 정렬 + fallback), scenario_adapter(ip_ref resolve), run_simulation()(순수 Pydantic 파이프라인) 구현. FHD30 ISP end-to-end SimRunResult(feasible=True, 295.992 MB/s) 검증 완료.

## What Was Built

### Task 1: DvfsResolver (RED `053733f` → GREEN `6e2ff4e`)

| 컴포넌트 | 내용 |
|----------|------|
| `DvfsResolver.resolve()` | 5-Step DVFS 결정 알고리즘 |
| OTF 그룹 탐색 | `Pipeline.edges[type=OTF]` 추출 → sensor v_valid_time 기반 required_clock 적용 (sw_margin 미적용 Pitfall 2) |
| dvfs_group 정렬 | `max(required_clock)` per group → 그룹 내 모든 IP 동일 레벨 결정 |
| DVFS 룩업 | `DVFSTable.find_min_level()` + domain 없으면 logging.warning + fallback (D-03) |
| VDD 정렬 | 같은 vdd 도메인 `max(set_voltage_mv)` 적용 (Pitfall 3) |
| dvfs_overrides | node_id → level 번호 강제 (SimGlobalConfig.dvfs_overrides) |

### Task 2: scenario_adapter + runner (RED `9d08d93` → GREEN `9b0fec3`)

**scenario_adapter.py**

| 함수 | 내용 |
|------|------|
| `build_ip_params()` | node_id -> IPSimParams 맵; sim_params 없는 IP 제외 + logging.warning (D-04) |
| `_resolve_ip_name()` | hw_name_in_sim 우선 → ip_ref 파싱 fallback ("ip-isp-v12" → "ISP") |

**runner.py**

| 단계 | 내용 |
|------|------|
| Step 1 | `build_ip_params()` 호출 |
| Step 2 | `DvfsResolver.resolve()` → node_id -> ResolvedIPConfig |
| Step 3 | `calc_port_bw()` — inputs + outputs 포트 순환, PortType 매핑 |
| Step 4 | `calc_processing_time()` — port_cfg 해상도 우선, FHD 기본값 |
| Step 5 | `calc_active_power()` — VDD 도메인별 집계 + BW 전력 합산 |
| Return | `SimRunResult` 조립 (feasible 판정 포함) |

## end-to-end SimRunResult 실제 값 (FHD30 ISP M2M)

| 항목 | 값 |
|------|-----|
| feasible | True |
| bw_total_mbs | 295.992 MB/s (RDMA_FE BAYER 202.68 + WDMA_BE NV12 93.312) |
| hw_time_max_ms | 1.361 ms (< 33.33ms 프레임 간격) |
| total_power_mw | 42.494 mW |
| total_power_ma | 12.498 mA |
| resolved.isp0.set_clock_mhz | 400.0 MHz (level 2) |
| resolved.isp0.set_voltage_mv | 660.0 mV (asv_group=4) |

## Test Results

```
tests/sim/test_dvfs_resolver.py   — 4 passed (Task 1)
tests/sim/test_scenario_adapter.py — 5 passed (Task 2)
tests/sim/test_runner.py          — 2 passed (Task 2)
Subtotal (Plan 03): 11 passed

tests/sim/ total: 41 passed (Plan 01: 14 + Plan 02: 16 + Plan 03: 11)
tests/unit/ total: 357 passed (회귀 없음)
```

## TDD Gate Compliance

| Gate | Task | Commit | Status |
|------|------|--------|--------|
| RED (test dvfs_resolver) | Task 1 | `053733f` | `ModuleNotFoundError: No module named 'scenario_db.sim.dvfs_resolver'` — 실패 확인 |
| GREEN (feat dvfs_resolver) | Task 1 | `6e2ff4e` | 4/4 PASSED |
| RED (test adapter+runner) | Task 2 | `9d08d93` | `ModuleNotFoundError` x2 — 실패 확인 |
| GREEN (feat adapter+runner) | Task 2 | `9b0fec3` | 7/7 PASSED |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] OTF 제약 테스트 기대값 수정**
- **Found during:** Task 1 GREEN 단계
- **Issue:** 계획의 `test_dvfs_otf_group_constraint`에서 `assert r.set_clock_mhz >= 533.0` 기대값 오산. sensor(4000x3000, fps=30, v_valid_ratio=0.85, ppc=4) → OTF required_clock = 105.88 MHz. 이를 충족하는 최소 DVFS 레벨은 400MHz(level 2) 이지 533MHz(level 1)가 아님.
- **Fix:** 기대값을 `>= 400.0`으로 수정하고 OTF 제약이 M2M보다 엄격함을 required_clock_mhz > 100.0으로 확인하도록 변경.
- **Files modified:** `tests/sim/test_dvfs_resolver.py`
- **Commit:** `6e2ff4e` (GREEN 커밋에 통합)

## Phase 7 연결 준비 완료

`run_simulation()` 최종 시그니처:
```python
def run_simulation(
    scenario_id: str,
    variant_id: str,
    pipeline: Pipeline,
    ip_catalog: dict[str, IpCatalog],
    dvfs_tables: dict[str, DVFSTable],
    variant_port_config: dict[str, IPPortConfig],
    sim_config: SimGlobalConfig,
    sensor_spec: SensorSpec | None = None,
    fps: float = 30.0,
) -> SimRunResult: ...
```

Phase 7 라우터 호출 패턴:
```python
from scenario_db.sim.runner import run_simulation
# ORM row -> Pydantic 변환 후 호출 (D-05: runner에 DB import 없음)
result = run_simulation(scenario_id=..., variant_id=..., ...)
```

## Known Stubs

없음 — 모든 계산 경로가 실제 데이터로 동작함.

## Threat Surface Scan

T-06-08 (mitigate): `runner.py`에 sqlalchemy/ORM import 없음 — AST 분석으로 검증 완료. 추가 신규 위협 표면 없음.

## Self-Check: PASSED

- `053733f`: test(06-03) RED dvfs_resolver — FOUND
- `6e2ff4e`: feat(06-03) GREEN dvfs_resolver — FOUND
- `9d08d93`: test(06-03) RED adapter+runner — FOUND
- `9b0fec3`: feat(06-03) GREEN adapter+runner — FOUND
- `src/scenario_db/sim/dvfs_resolver.py` — FOUND
- `src/scenario_db/sim/scenario_adapter.py` — FOUND
- `src/scenario_db/sim/runner.py` — FOUND
- `tests/sim/test_dvfs_resolver.py` — FOUND
- `tests/sim/test_scenario_adapter.py` — FOUND
- `tests/sim/test_runner.py` — FOUND
- tests/sim/ 41 passed — VERIFIED
- tests/unit/ 357 passed — VERIFIED
