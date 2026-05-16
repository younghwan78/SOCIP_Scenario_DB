---
phase: 06-sim-package
plan: "02"
subsystem: sim-package
tags: [sim, bw-calc, perf-calc, power-calc, tdd, golden-values]
dependency_graph:
  requires: [phase-06-plan-01-infra]
  provides: [bw-calc-engine, perf-calc-engine, power-calc-engine]
  affects: [phase-06-plan-03-dvfs-resolver-runner]
tech_stack:
  added: []
  patterns: [tdd-red-green, pure-functions, golden-value-tests]
key_files:
  created:
    - src/scenario_db/sim/bw_calc.py
    - src/scenario_db/sim/perf_calc.py
    - src/scenario_db/sim/power_calc.py
    - tests/sim/test_bw_calc.py
    - tests/sim/test_perf_calc.py
    - tests/sim/test_power_calc.py
  modified: []
decisions:
  - "OTF 포트 direction 필드: Literal[read,write] 제약 충족을 위해 read 고정 — bw_mbs=0으로 의미 없음"
  - "BPP_MAP.get(format, 1.0) fallback: T-06-05 위협 mitigate — 알 수 없는 format은 보수적 1.0 사용"
  - "compression=disable 시 comp_ratio 무시: Pitfall 4 방지 — 명시적 분기로 구현"
metrics:
  duration: "~10분"
  completed: "2026-05-16T15:00:00Z"
  tasks_completed: 2
  files_created: 6
  files_modified: 0
  tests_added: 16
  tests_passed: 16
---

# Phase 6 Plan 02: Wave 1 계산 함수 — bw_calc / perf_calc / power_calc Summary

순수 계산 함수 3개 TDD 구현 완료 — FHD30 ISP Golden 값 (93.312 MB/s BW, 1.021 ms 처리시간, 26.28 mW) 오차 0% 달성.

## What Was Built

### Task 1: bw_calc.py (commit `a57e02e` RED → `b4d90b9` GREEN)

| 항목 | 내용 |
|------|------|
| 함수 | `calc_port_bw(port, ip_name, port_type, fps, bw_power_coeff) -> PortBWResult` |
| OTF 처리 | `PortType.OTF_IN / OTF_OUT` → `bw_mbs=0.0, bw_power_mw=0.0` |
| compression 처리 | `compression="disable"` → `comp_ratio` 무시, 1.0 사용 (Pitfall 4) |
| LLC 처리 | `llc_enabled=False` → `llc_weight` 무시, 1.0 사용 |
| worst-case | `comp_ratio_max` 설정 시 `bw_mbs_worst` 계산 |
| 테스트 | 9개 (Golden 2개 + OTF 2개 + direction 2개 + 특수 케이스 3개) |

### Task 2: perf_calc.py + power_calc.py (commit `56e0018` RED → `458474d` GREEN)

**perf_calc.py**

| 항목 | 내용 |
|------|------|
| 함수 | `calc_processing_time(pixels, set_clock_mhz, ppc, h_blank_margin) -> float` |
| 공식 | `pixels / (mhz * 1e6 * ppc) * (1 + h_blank) * 1000` |
| 테스트 | 3개 (Golden + h_blank=0 기저 + feasibility) |

**power_calc.py**

| 항목 | 내용 |
|------|------|
| 함수 | `calc_active_power(unit_power_mw_mp, width, height, set_voltage_mv, fps) -> float` |
| 공식 | `unit * MP * (V/710)^2 * (fps/30)` |
| 상수 참조 | `REFERENCE_VOLTAGE_MV`, `REFERENCE_FPS` — 하드코딩 없음 |
| 테스트 | 4개 (Golden + V_ref 스케일 + fps 절반 + V² 배율) |

## Golden 값 실제 계산 결과

| 항목 | Golden | 실제 | 오차 |
|------|--------|------|------|
| WDMA_BE BW (FHD30, NV12) | 93.312 MB/s | 93.312 MB/s | 0.000% |
| RDMA_FE BW (FHD30, BAYER SBWC 0.5) | 202.68 MB/s | 202.680 MB/s | 0.000% |
| ISP 처리시간 (533MHz, ppc=4, h_blank=5%) | 1.021 ms | 1.0212 ms | 0.02 ms |
| ISP Active Power (780mV, 30fps) | 26.28 mW | 26.278 mW | 0.002 mW |

## Test Results

```
tests/sim/test_bw_calc.py    — 9 passed
tests/sim/test_perf_calc.py  — 3 passed
tests/sim/test_power_calc.py — 4 passed
Subtotal (Plan 02): 16 passed

tests/sim/ total: 30 passed (Plan 01: 14 + Plan 02: 16)
tests/unit/ total: 357 passed (회귀 없음)
```

## TDD Gate Compliance

| Gate | Task | Commit | Status |
|------|------|--------|--------|
| RED (test bw_calc) | Task 1 | `a57e02e` | `ModuleNotFoundError: No module named 'scenario_db.sim.bw_calc'` — 실패 확인 |
| GREEN (feat bw_calc) | Task 1 | `b4d90b9` | 9/9 PASSED |
| RED (test perf+power) | Task 2 | `56e0018` | `ModuleNotFoundError` x2 — 실패 확인 |
| GREEN (feat perf+power) | Task 2 | `458474d` | 7/7 PASSED |

## Deviations from Plan

None — 계획 그대로 실행됨. OTF 포트의 `direction` 필드 처리에서 `Literal["read","write"]` 제약 충족을 위해 `"read"` 고정 사용 — 이는 계획의 action 코드와 동일한 방식이므로 이탈 아님.

## Threat Surface Scan

`T-06-05 (mitigate)` — `BPP_MAP.get(format, 1.0)` fallback: 알 수 없는 format은 bpp=1.0으로 보수적 처리. 계획의 threat model에 이미 등록됨. 로그 없이 silent이므로 주요 format(NV12/BAYER/RAW10/ARGB)은 BPP_MAP에 사전 등록 권장. 추가 신규 위협 표면 없음.

## Self-Check: PASSED

- `a57e02e`: test(06-02): RED bw_calc — FOUND
- `b4d90b9`: feat(06-02): GREEN bw_calc — FOUND
- `56e0018`: test(06-02): RED perf+power — FOUND
- `458474d`: feat(06-02): GREEN perf+power — FOUND
- `src/scenario_db/sim/bw_calc.py` — FOUND
- `src/scenario_db/sim/perf_calc.py` — FOUND
- `src/scenario_db/sim/power_calc.py` — FOUND
- `tests/sim/test_bw_calc.py` — FOUND
- `tests/sim/test_perf_calc.py` — FOUND
- `tests/sim/test_power_calc.py` — FOUND
