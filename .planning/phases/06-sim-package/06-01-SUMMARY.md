---
phase: 06-sim-package
plan: "01"
subsystem: sim-package
tags: [sim, dvfs, constants, pydantic-models, tdd]
dependency_graph:
  requires: [phase-05-schema-extensions]
  provides: [sim-package-infra, dvfs-table-models, sim-run-result-model]
  affects: [phase-07-simulation-api]
tech_stack:
  added: []
  patterns: [D-01-single-definition, tdd-red-green, re-import-pattern]
key_files:
  created:
    - src/scenario_db/sim/__init__.py
    - src/scenario_db/sim/constants.py
    - src/scenario_db/sim/models.py
    - hw_config/dvfs-projectA.yaml
    - tests/sim/__init__.py
    - tests/sim/conftest.py
    - tests/sim/test_constants.py
    - tests/sim/test_models.py
  modified:
    - src/scenario_db/config.py
    - pyproject.toml
decisions:
  - "D-01 단일 정의 원칙: PortBWResult/IPTimingResult는 evidence.simulation에서 re-import — sim/models.py에서 재정의 없음"
  - "DVFS_CONFIG_PATH는 Settings 클래스 외부 모듈 수준 상수로 배치 (환경변수 불필요)"
  - "conftest.py는 YAML 파일 파싱 없이 인라인 하드코딩 픽스처만 사용 (테스트 격리)"
metrics:
  duration: "~15분"
  completed: "2026-05-16T14:23:48Z"
  tasks_completed: 2
  files_created: 8
  files_modified: 2
  tests_added: 14
  tests_passed: 14
---

# Phase 6 Plan 01: sim/ 패키지 인프라 + 상수 + Pydantic 모델 Summary

Wave 1 인프라 확립 — `scenario_db.sim` 패키지 import 가능, BPP_MAP/DVFS 상수 정의, 4개 신규 Pydantic 모델 round-trip 검증 완료 (TDD GREEN).

## What Was Built

### Task 1: 인프라 파일 생성 (commit `fc4c338`)

| 파일 | 역할 |
|------|------|
| `src/scenario_db/sim/__init__.py` | sim 패키지 마커 |
| `tests/sim/__init__.py` | tests/sim 패키지 마커 |
| `hw_config/dvfs-projectA.yaml` | CAM/INT/MIF 3개 도메인 DVFS 테이블 |
| `src/scenario_db/config.py` | `DVFS_CONFIG_PATH: Path = Path("hw_config/dvfs-projectA.yaml")` 추가 |
| `pyproject.toml` | `testpaths = ["tests/unit", "tests/sim"]` 업데이트 |

### Task 2: constants.py + models.py + 테스트 (TDD)

**RED commit `f350440`** — 테스트 파일 먼저 작성, 모듈 없어서 ImportError 실패 확인.

**GREEN commit `673ebde`** — 구현 완료, 14/14 통과.

## Constants Defined (`src/scenario_db/sim/constants.py`)

```python
BPP_MAP = {
    "NV12":   1.5,    # YUV420 semi-planar
    "YUV420": 1.5,    # NV12 동일
    "RAW10":  1.25,   # Bayer 10-bit packed
    "ARGB":   4.0,    # 32-bit RGBA
    "BAYER":  1.0,    # 1 sample/pixel (bitwidth 인수가 bit count)
}
BW_POWER_COEFF_DEFAULT: float = 80.0   # mW/(GB/s)
REFERENCE_VOLTAGE_MV: float = 710.0    # V² 스케일링 기준 전압
REFERENCE_FPS: float = 30.0            # fps 스케일링 기준
```

## Models Defined (`src/scenario_db/sim/models.py`)

| 모델 | 필드 | 비고 |
|------|------|------|
| `DVFSLevel` | `level: int`, `speed_mhz: float`, `voltages: dict[int, float]` | asv_group → voltage_mv |
| `DVFSTable` | `domain: str`, `levels: list[DVFSLevel]` | `find_min_level()` 메서드 포함 |
| `ResolvedIPConfig` | `ip_name`, `required_clock_mhz`, `set_clock_mhz`, `set_voltage_mv`, `dvfs_group`, `vdd` | DVFS resolve 결과 |
| `SimRunResult` | `scenario_id`, `variant_id`, `total_power_mw`, `total_power_ma`, `bw_total_mbs`, `hw_time_max_ms`, `feasible`, `resolved`, `dma_breakdown`, `timing_breakdown`, `vdd_power` | 파이프라인 전체 결과 |
| `PortBWResult` | re-import from evidence.simulation | D-01 원칙 |
| `IPTimingResult` | re-import from evidence.simulation | D-01 원칙 |

## Test Results

```
tests/sim/test_constants.py  — 6 passed
tests/sim/test_models.py     — 8 passed
Total: 14 passed, 0 failed
```

기존 회귀: `tests/unit/ — 357 passed` (회귀 없음)

## Deviations from Plan

None — 계획 그대로 실행됨. `conftest.py`의 `SensorSpec(ip_ref="ip-csis-v3", ...)` 필드명이 실제 `usecase.py` 구현과 일치 확인 후 그대로 사용.

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (test) | `f350440` | `test(06-01): RED — sim constants/models round-trip 테스트 작성` |
| GREEN (feat) | `673ebde` | `feat(06-01): GREEN — sim/constants.py + sim/models.py 구현 (14/14 tests pass)` |

RED gate: `ImportError: No module named 'scenario_db.sim.constants'` — 실패 확인 후 구현 진행.
GREEN gate: 14/14 PASSED.

## Threat Surface Scan

`hw_config/dvfs-projectA.yaml` 신규 파일 — 계획의 `<threat_model>`에 T-06-01 (accept)로 등록됨. 민감 정보 없음, 소스 제어로 버전 관리. T-06-02 (mitigate) 관련: 이 플랜에서는 YAML 파싱 코드를 포함하지 않음 — Wave 3 dvfs_resolver에서 `yaml.safe_load()` 사용 예정.

## Self-Check: PASSED

- `fc4c338`: feat(06-01): Task 1 인프라 파일 — sim/ 패키지 마커 + 상수 경로 + DVFS YAML — FOUND
- `f350440`: test(06-01): RED — sim constants/models round-trip 테스트 작성 — FOUND
- `673ebde`: feat(06-01): GREEN — sim/constants.py + sim/models.py 구현 (14/14 tests pass) — FOUND
- 모든 created 파일 존재 확인 완료
