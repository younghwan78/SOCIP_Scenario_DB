---
phase: 06-sim-package
verified: 2026-05-16T16:00:00Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
---

# Phase 6: sim/ Package Verification Report

**Phase Goal:** BW/Power/DVFS/Timing 계산 파이프라인을 구현하는 sim/ 패키지 — constants/models/bw_calc/perf_calc/power_calc/dvfs_resolver/adapter/runner 모듈 포함. Phase 7(Simulation API)에서 호출할 run_simulation() 인터페이스 확정.
**Verified:** 2026-05-16T16:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | sim/ 패키지가 import 가능하다 | ✓ VERIFIED | `from scenario_db.sim.runner import run_simulation` 성공. `__init__.py` 존재 확인. |
| 2 | constants.py의 BPP_MAP에 NV12/RAW10/ARGB/BAYER/YUV420 5개 키가 정의된다 | ✓ VERIFIED | 실제 constants.py 코드 + `test_bpp_map_values[NV12-1.5]` 등 5개 파라미터 테스트 통과 |
| 3 | sim/models.py의 4개 신규 모델이 round-trip 직렬화를 통과한다 | ✓ VERIFIED | test_dvfs_level_roundtrip, test_dvfs_table_roundtrip, test_resolved_ip_config_roundtrip, test_sim_run_result_roundtrip 모두 PASSED |
| 4 | config.py에 DVFS_CONFIG_PATH 상수가 추가된다 | ✓ VERIFIED | `DVFS_CONFIG_PATH: Path = Path("hw_config/dvfs-projectA.yaml")` 마지막 줄 확인. import 실행 값: `hw_config\dvfs-projectA.yaml` |
| 5 | hw_config/dvfs-projectA.yaml이 CAM/INT/MIF 3개 도메인을 정의한다 | ✓ VERIFIED | yaml 파일 직접 확인: CAM(3레벨), INT(2레벨), MIF(2레벨) 정의됨 |
| 6 | bw_calc/perf_calc/power_calc 3개 순수 함수가 Golden 값을 통과한다 | ✓ VERIFIED | FHD30 WDMA_BE 93.312 MB/s (오차 0%), RDMA_FE 202.68 MB/s (오차 0%), 처리시간 1.021 ms (오차 0.02 ms), Active Power 26.28 mW (오차 0.002 mW). 16개 테스트 모두 PASSED |
| 7 | DvfsResolver가 OTF 그룹 제약/VDD 정렬/fallback을 처리한다 | ✓ VERIFIED | ISP FHD30 → level 2(400MHz, 660mV) 확인. OTF 그룹 제약 105.88MHz 적용 확인. domain 없을 때 logging.warning + fallback 확인. 4개 테스트 PASSED |
| 8 | run_simulation()이 DB/ORM import 없이 SimRunResult를 반환한다 | ✓ VERIFIED | grep으로 실제 import 줄에 sqlalchemy/db 없음 확인. 행동 검증: feasible=True, bw_total_mbs=295.992, hw_time_max_ms=1.361 |
| 9 | 기존 테스트에 회귀가 없다 (SIM-09) | ✓ VERIFIED | `tests/unit/ — 357 passed` (회귀 없음) |

**Score:** 9/9 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/scenario_db/sim/__init__.py` | 패키지 마커 | ✓ VERIFIED | 파일 존재 확인 |
| `src/scenario_db/sim/constants.py` | BPP_MAP + 3개 참조 상수 | ✓ VERIFIED | BPP_MAP 5개 키, REFERENCE_VOLTAGE_MV=710.0, REFERENCE_FPS=30.0, BW_POWER_COEFF_DEFAULT=80.0 |
| `src/scenario_db/sim/models.py` | 4개 신규 모델 + 2개 re-import | ✓ VERIFIED | DVFSLevel, DVFSTable, ResolvedIPConfig, SimRunResult 정의; PortBWResult/IPTimingResult는 evidence.simulation에서 re-import (D-01 원칙) |
| `src/scenario_db/sim/bw_calc.py` | calc_port_bw() | ✓ VERIFIED | 실제 구현 확인. OTF 판별(enum 사용), comp_ratio/llc_weight 처리 |
| `src/scenario_db/sim/perf_calc.py` | calc_processing_time() | ✓ VERIFIED | 단일 순수 함수; h_blank_margin 포함 |
| `src/scenario_db/sim/power_calc.py` | calc_active_power() | ✓ VERIFIED | V²/fps 스케일링; REFERENCE 상수 참조 (하드코딩 없음) |
| `src/scenario_db/sim/dvfs_resolver.py` | DvfsResolver 클래스 | ✓ VERIFIED | 5-Step 알고리즘: OTF 그룹 탐색, group max 정렬, DVFS 룩업, VDD 정렬, fallback |
| `src/scenario_db/sim/scenario_adapter.py` | build_ip_params(), _resolve_ip_name() | ✓ VERIFIED | DB import 없음 확인. sim_params 없는 IP logging.warning 처리 |
| `src/scenario_db/sim/runner.py` | run_simulation() | ✓ VERIFIED | 5-Step 파이프라인 오케스트레이션. fps 인수 추가(SUMMARY deviation 반영). DB import 없음 |
| `hw_config/dvfs-projectA.yaml` | CAM/INT/MIF DVFS 테이블 | ✓ VERIFIED | 3개 도메인 정의; CAM 3레벨, INT 2레벨, MIF 2레벨 |
| `src/scenario_db/config.py` | DVFS_CONFIG_PATH 상수 | ✓ VERIFIED | 파일 끝에 모듈 수준 상수로 배치 (Settings 클래스 외부) |
| `pyproject.toml` | tests/sim testpaths 등록 | ✓ VERIFIED | `testpaths = ["tests/unit", "tests/sim"]` 확인 |
| `tests/sim/conftest.py` | 인라인 픽스처 (YAML 의존 없음) | ✓ VERIFIED | isp_sim_params, cam_dvfs_table, fhd30_wdma_port, fhd30_rdma_port, default_sim_config, sensor_fhd30 픽스처 하드코딩 |
| `tests/sim/test_*.py` (8개) | 모든 테스트 | ✓ VERIFIED | 41개 테스트 전체 PASSED (0.04s) |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `sim/models.py` | `evidence/simulation.py` | `from scenario_db.models.evidence.simulation import IPTimingResult, PortBWResult` | ✓ WIRED | line 8 확인. `PortBWResult is EvidencePortBWResult` 테스트 통과 |
| `sim/models.py` | `models/common.py` | `from scenario_db.models.common import BaseScenarioModel` | ✓ WIRED | line 5 확인. ResolvedIPConfig/DVFSLevel/DVFSTable/SimRunResult 상속 |
| `sim/bw_calc.py` | `sim/constants.py` | `from scenario_db.sim.constants import BPP_MAP, BW_POWER_COEFF_DEFAULT` | ✓ WIRED | line 6 확인 |
| `sim/bw_calc.py` | `models/capability/hw.py` | `from scenario_db.models.capability.hw import PortType` | ✓ WIRED | line 3 확인. OTF 판별에 enum 사용 |
| `sim/power_calc.py` | `sim/constants.py` | `from scenario_db.sim.constants import REFERENCE_FPS, REFERENCE_VOLTAGE_MV` | ✓ WIRED | line 3 확인 |
| `sim/runner.py` | `sim/dvfs_resolver.py` | `from scenario_db.sim.dvfs_resolver import DvfsResolver` | ✓ WIRED | line 17 확인. `resolver.resolve()` 호출 |
| `sim/runner.py` | `sim/bw_calc.py` | `from scenario_db.sim.bw_calc import calc_port_bw` | ✓ WIRED | line 16 확인. Step 3에서 호출 |
| `sim/runner.py` | `sim/models.py` | `from scenario_db.sim.models import DVFSTable, ResolvedIPConfig, SimRunResult` | ✓ WIRED | line 18 확인. SimRunResult 반환 |
| `sim/dvfs_resolver.py` | `models/definition/usecase.py` | `EdgeType.OTF` 사용 | ✓ WIRED | line 89: `if edge.type == EdgeType.OTF` 확인 |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `runner.py` | `dma_breakdown` | `calc_port_bw()` — PortInputConfig + fps 입력 | Yes — 수식 기반 실계산. FHD30 WDMA_BE=93.312 MB/s | ✓ FLOWING |
| `runner.py` | `timing_breakdown` | `calc_processing_time()` — pixels/clock/ppc 입력 | Yes — 수식 기반 실계산. ISP=1.361 ms | ✓ FLOWING |
| `runner.py` | `total_power_mw` | `calc_active_power()` + BW power sum | Yes — V²/fps 스케일링 계산. 42.494 mW | ✓ FLOWING |
| `runner.py` | `resolved` | `DvfsResolver.resolve()` → `DVFSTable.find_min_level()` | Yes — DVFS 테이블 룩업. isp0: level2/400MHz/660mV | ✓ FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| run_simulation() import | `from scenario_db.sim.runner import run_simulation` | OK | ✓ PASS |
| BPP_MAP 5개 키 + REFERENCE 상수 | Python import + print | BPP_MAP=['NV12','YUV420','RAW10','ARGB','BAYER'], REFERENCE_VOLTAGE_MV=710.0 | ✓ PASS |
| D-01 원칙 (re-import 동일 클래스) | `PortBWResult is EvidencePortBWResult` | True | ✓ PASS |
| FHD30 end-to-end run_simulation() | 실행 검증 | feasible=True, bw_total_mbs=295.992, hw_time_max_ms=1.361, isp0.set_clock=400.0 | ✓ PASS |
| ORM import 없음 (D-05) | grep 실제 import 줄 | NO sqlalchemy/db import found | ✓ PASS |
| tests/sim/ 전체 | `uv run pytest tests/sim/ -v` | 41 passed in 0.04s | ✓ PASS |
| tests/unit/ 회귀 없음 | `uv run pytest tests/unit/ -q` | 357 passed in 0.98s | ✓ PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SIM-01 | PLAN-01 | `sim/constants.py` — BPP_MAP, BW_POWER_COEFF_DEFAULT, REFERENCE_VOLTAGE_MV | ✓ SATISFIED | constants.py 구현 + 6개 상수 테스트 PASSED |
| SIM-02 | PLAN-01, PLAN-02 | `sim/models.py` — DVFSLevel, DVFSTable, ResolvedIPConfig, PortBWResult, IPTimingResult, SimRunResult | ✓ SATISFIED | models.py 구현. D-01 원칙 (re-import). 8개 모델 테스트 PASSED |
| SIM-03 | PLAN-02 | `sim/bw_calc.py` — calc_port_bw() OTF 포트 제외, comp_ratio/llc_weight 적용 | ✓ SATISFIED | bw_calc.py 구현. 9개 테스트 PASSED. Golden 93.312/202.68 MB/s 오차 0% |
| SIM-04 | PLAN-02, PLAN-03 | `sim/perf_calc.py` — calc_processing_time() h_blank_margin 포함 | ✓ SATISFIED | perf_calc.py 구현. 3개 테스트 PASSED. Golden 1.021 ms |
| SIM-05 | PLAN-02, PLAN-03 | `sim/power_calc.py` — calc_active_power() V² 스케일링 + fps 스케일링 | ✓ SATISFIED | power_calc.py 구현. 4개 테스트 PASSED. Golden 26.28 mW |
| SIM-06 | PLAN-01, PLAN-03 | `sim/dvfs_resolver.py` — DvfsResolver: OTF 그룹 v_valid_time 제약 + VDD 도메인 전압 정렬 | ✓ SATISFIED | dvfs_resolver.py 구현. 4개 테스트 PASSED. fallback logging.warning 확인 |
| SIM-07 | PLAN-01 | `hw_config/dvfs-projectA.yaml` — DVFS 테이블 (CAM/INT/MIF 도메인) | ✓ SATISFIED | yaml 파일 존재. 3개 도메인 7개 레벨 정의 |
| SIM-08 | PLAN-03 | `sim/scenario_adapter.py` — Usecase.pipeline + Variant.sim_port_config → runner 입력 변환 | ✓ SATISFIED | scenario_adapter.py 구현. build_ip_params()/\_resolve_ip_name(). 5개 테스트 PASSED |
| SIM-09 | PLAN-02, PLAN-03 | `sim/runner.py` — 전체 파이프라인 오케스트레이터 | ✓ SATISFIED | runner.py 구현. run_simulation() 시그니처 확정. 2개 테스트 PASSED. end-to-end 검증 완료 |

**전체 9개 요구사항 모두 SATISFIED.**

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (없음) | - | - | - | - |

TODO/FIXME/stub 패턴 없음. `return null/[]/{}` 없음. 모든 함수가 실계산 데이터를 반환함.

---

### Notes on Plan Deviation (Auto-fixed)

**run_simulation() fps 인수 추가 (PLAN-03 deviation):**
PLAN-03의 계획에는 fps 인수가 없었으나, SimGlobalConfig에 fps 필드가 없어 sensor_spec.fps 우선 + 기본값 30.0 처리를 위해 `fps: float = 30.0` 인수를 추가함. 이는 Phase 7 호출 계약에서 명시적 fps 전달을 가능하게 하는 개선이다. SUMMARY.md에 명시됨.

**OTF 제약 테스트 기대값 수정 (PLAN-03 deviation):**
계획 `test_dvfs_otf_group_constraint`의 `>= 533.0` 기대값이 오산이었음 (실제 105.88MHz 요구사항은 400MHz로 충족 가능). `>= 400.0`으로 수정 후 구현. 이는 올바른 수정이다.

---

### Human Verification Required

없음. 모든 must-have가 자동화 검증으로 확인됨.

---

## Gaps Summary

없음 — 모든 9개 must-have 검증 통과. Phase 6 목표 달성.

---

_Verified: 2026-05-16T16:00:00Z_
_Verifier: Claude (gsd-verifier)_
