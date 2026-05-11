# Phase 6: sim/ Package — Research

**Researched:** 2026-05-11
**Domain:** Pure-Python BW/Power/DVFS/Timing 계산 패키지 이식 (SimEngine -> scenario_db/sim/)
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01: sim/models.py 범위 (모델 중복 방지)**
- `PortBWResult`, `IPTimingResult` — `models.evidence.simulation`에서 re-import (재정의 없음)
- 신규 정의: `ResolvedIPConfig`, `DVFSLevel`, `DVFSTable`, `SimRunResult`만 `sim/models.py`에 정의
- 근거: 단일 정의 원칙 — evidence layer 모델을 복제하면 Phase 7에서 타입 불일치 발생

**D-02: bw_calc 입력 모델**
- `bw_calc.calc_port_bw(port: PortInputConfig, fps: float, ...)` — `usecase.PortInputConfig` 직접 사용
- sim/ 내부 전용 입력 모델 신규 정의 없음

**D-03: DVFS YAML 로딩 방식**
- `config.py`에 `DVFS_CONFIG_PATH = Path("hw_config/dvfs-projectA.yaml")` 추가
- `DvfsResolver` 생성 시 이 경로에서 자동 로드 (또는 테스트에서 `dvfs_tables` dict로 직접 주입)
- DVFS 파일 없거나 domain 미매칭 -> `set_clock_mhz = required_clock_mhz`, `set_voltage_mv = REFERENCE_VOLTAGE_MV(710.0)` fallback + `logging.warning` 출력 (ValueError raise 없음)

**D-04: scenario_adapter.py 역할**
- `scenario_adapter.py` 단일 파일에 두 역할 모두 담당:
  1. `Usecase.pipeline + Variant.sim_port_config + Variant.sim_config` -> `runner.run_simulation()` 입력 조립
  2. `ip_ref -> IpCatalog.sim_params` resolve (ip_ref에서 hw_name_in_sim 추출 포함)
- fallback: `sim_params`가 없는 IP는 계산에서 제외하고 `logging.warning` 출력

**D-05: runner.py 입력 계약 — 순수 Pydantic**
- `run_simulation()` 시그니처:
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
  ) -> SimRunResult:
  ```
- DB/ORM 의존 없음 — 순수 Python 함수

**D-06: 테스트 픽스처 전략**
- `tests/sim/conftest.py` — ISP/CSIS 수치 인라인 하드코딩 픽스처
- YAML 파일 I/O 없음 (sim/ 테스트가 파일 시스템에 의존하지 않음)
- Golden 값 assert: FHD30 ISP WDMA_BE BW = 93.31 MB/s (±1%)

### Claude's Discretion

없음 (모든 주요 설계 결정 사항이 Locked)

### Deferred Ideas (OUT OF SCOPE)

- ParametricSweep <-> ExplorationEngine 어댑터 (`sim/exploration_adapter.py`) — Phase Sim-3
- SimPy 이벤트 시뮬레이션 (`sim/simulator.py`) — Phase Sim-5 (선택사항)
- `NodeData.sim_overlay` + `EdgeData.bw_mbs` Dashboard 오버레이 — Phase 7 이후
- Evidence Dashboard Streamlit 페이지 — Milestone 2 이후
- params_hash 캐싱 — Phase 7 (Simulation API) 범위
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SIM-01 | `sim/constants.py`에 BPP_MAP, BW_POWER_COEFF_DEFAULT, REFERENCE_VOLTAGE_MV 정의 + `sim/models.py` Pydantic v2 모델 round-trip 테스트 통과 | §2.2 공식에서 필요 상수 목록 확인, BaseScenarioModel 패턴 재사용 |
| SIM-02 | `calc_port_bw()` OTF 포트 제외, comp_ratio/llc_weight 적용 BW(MB/s) 반환 — 단위 테스트 계산값 검증 | PortType enum(DMA_READ/WRITE/OTF_IN/OUT) 확인, Golden 값 93.31 MB/s 계산 |
| SIM-03 | `calc_processing_time()` h_blank_margin 포함 처리시간(ms), `calc_active_power()` V² + fps 스케일링 | 공식 §2.2 직접 확인, 단위 불일치 없음 |
| SIM-04 | `DvfsResolver` OTF 그룹 v_valid_time 제약 + VDD 도메인 전압 정렬, `dvfs-projectA.yaml` CAM/INT/MIF 도메인 정의 | §7.3 DVFS 파일 구조 + OTF 알고리즘 §12.3 확인 |
| SIM-05 | `scenario_adapter.py` Usecase.pipeline + Variant.sim_port_config -> runner 입력 변환, `runner.py` SimRunResult 반환 | Pipeline/Variant 모델 실제 코드 확인 완료 |
| SIM-06 | `sim/models.py` ResolvedIPConfig, DVFSLevel, DVFSTable, SimRunResult Pydantic 정의 | 설계 문서 §6.2 스케치 기반 |
| SIM-07 | `config.py` DVFS_CONFIG_PATH 추가 | 기존 config.py 구조 확인 — Settings 클래스 없이 Path 상수로 추가 |
| SIM-08 | DVFS fallback 처리 (logging.warning, ValueError 없음) | D-03 locked |
| SIM-09 | tests/sim/ — Golden 값 assert, 기존 357 단위 테스트 회귀 없음 | 현재 test suite 구조 확인 완료 |
</phase_requirements>

---

## Summary

Phase 6는 SimEngine(별도 프로젝트)의 BW/Power/DVFS/Timing 계산 로직을 `src/scenario_db/sim/` 패키지로 이식하는 순수 Python 구현 작업이다. Phase 5에서 완성된 Pydantic 스키마(`IPSimParams`, `PortInputConfig`, `IPPortConfig`, `SimGlobalConfig`, `SensorSpec`, `PortBWResult`, `IPTimingResult`)를 그대로 소비한다. DB/ORM 의존성이 없으므로 독립적으로 테스트 가능하다.

핵심 계산 공식 4개(BW/Power/처리시간/DVFS)는 `docs/simulation-engine-integration.md §2.2`에 완전히 명세되어 있다. 이식 대상 모듈은 `constants.py -> models.py -> bw_calc/perf_calc/power_calc -> dvfs_resolver -> scenario_adapter -> runner` 순서의 단방향 의존 그래프를 형성한다. 테스트는 YAML 파일 의존 없이 인라인 픽스처 + Golden 값 assert 방식으로 구성한다.

가장 중요한 구현 위험은 OTF 그룹 타이밍 제약이다. OTF 연결로 묶인 IP들(CSIS->ISP)은 센서 v_valid_time 기반 처리량 제약을 받아야 하며, 이를 누락하면 DVFS 레벨이 과소 책정된다. `DvfsResolver`에서 `Pipeline.edges[type=OTF]`를 탐색해 OTF 그룹을 식별하고 센서 제약을 적용해야 한다.

**Primary recommendation:** `constants -> models -> 계산 함수 3개 -> dvfs_resolver -> scenario_adapter -> runner` 순서로 bottom-up 구현. 각 단계마다 Golden 값 단위 테스트를 먼저 작성(TDD).

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| BPP/전력 상수 정의 | sim/constants.py | — | 하드코딩 도메인 지식, DB 불필요 |
| 내부 계산 모델 (ResolvedIPConfig, DVFSTable 등) | sim/models.py | — | 계산 레이어 전용, evidence 모델과 분리 |
| DMA 포트 BW 계산 | sim/bw_calc.py | — | 순수 함수, Phase 5 PortInputConfig 소비 |
| IP 처리시간 계산 | sim/perf_calc.py | — | 순수 함수, set_clock + ppc 사용 |
| IP 전력 계산 | sim/power_calc.py | — | 순수 함수, V² 스케일링 |
| DVFS 레벨 결정 | sim/dvfs_resolver.py | — | OTF 그룹 제약 포함 핵심 알고리즘 |
| Pipeline -> 계산 입력 변환 | sim/scenario_adapter.py | — | ip_ref resolve + 입력 조립 담당 |
| 전체 파이프라인 오케스트레이션 | sim/runner.py | — | 순수 Pydantic, Phase 7 라우터가 호출 |
| DVFS 설정 파일 | hw_config/dvfs-projectA.yaml | config.py 경로 등록 | 프로젝트별 HW 파라미터 |

---

## Standard Stack

### Core (이미 설치됨 — 추가 설치 없음)
| Library | Version | Purpose | Source |
|---------|---------|---------|--------|
| pydantic | >=2.13.2 | sim/models.py Pydantic v2 모델 | [VERIFIED: pyproject.toml] |
| pyyaml | >=6.0.3 | dvfs-projectA.yaml 로딩 | [VERIFIED: pyproject.toml] |
| Python | >=3.11 | StrEnum, `float | None` 문법 | [VERIFIED: pyproject.toml] |

### Supporting (신규 의존성 없음)
Phase 6는 외부 라이브러리를 추가하지 않는다. 모든 계산은 표준 Python float 산술로 구현된다.

**Installation:**
```bash
# 추가 설치 불필요 — 기존 의존성으로 충분
uv run pytest tests/sim/ -q
```

---

## Architecture Patterns

### System Architecture Diagram

```
[Usecase.pipeline]  [Variant.sim_port_config]  [Variant.sim_config]
         |                      |                       |
         +----------+-----------+                       |
                    |                                   |
         [scenario_adapter.py]  <-- ip_ref resolve <-- [IpCatalog.sim_params]
                    |
                    v
         [runner.run_simulation()]
                    |
         +----------+----------+----------+
         |          |          |          |
    [dvfs_resolver] [bw_calc]  [perf_calc] [power_calc]
         |              |          |           |
         |         [constants.py BPP_MAP]       |
         |                                     |
    [hw_config/dvfs-projectA.yaml]             |
         |                                     |
         +----------+----------+---------------+
                    |
                    v
             [SimRunResult]
             (dma_breakdown, timing_breakdown, resolved, vdd_power)
                    |
                    v
          [Phase 7: SimulationEvidence 저장]
```

### Recommended Project Structure

```
src/scenario_db/sim/
├── __init__.py          # 빈 파일 또는 public API export
├── constants.py         # BPP_MAP, BW_POWER_COEFF_DEFAULT, REFERENCE_VOLTAGE_MV, REFERENCE_FPS
├── models.py            # ResolvedIPConfig, DVFSLevel, DVFSTable, SimRunResult (신규 4개)
│                        # PortBWResult, IPTimingResult: evidence.simulation에서 re-import
├── bw_calc.py           # calc_port_bw(port: PortInputConfig, fps, ...) -> PortBWResult
├── perf_calc.py         # calc_processing_time(pixels, set_clock_mhz, ppc, h_blank_margin) -> float
├── power_calc.py        # calc_active_power(unit_power, resolution_mp, set_voltage_mv, fps) -> float
├── dvfs_resolver.py     # DvfsResolver 클래스 — OTF 그룹 제약 포함
├── scenario_adapter.py  # build_runner_inputs(usecase, variant, ip_catalog) -> runner 인자
└── runner.py            # run_simulation(...) -> SimRunResult

hw_config/
└── dvfs-projectA.yaml   # CAM/INT/MIF 도메인 DVFS 테이블 (신규 작성)

tests/sim/
├── __init__.py
├── conftest.py          # 인라인 픽스처 (ISP/CSIS params, FHD30 port config, DVFS tables)
├── test_constants.py    # BPP_MAP 값 확인
├── test_bw_calc.py      # Golden 값 assert (FHD30 93.31 MB/s)
├── test_perf_calc.py    # 처리시간 계산 검증
├── test_power_calc.py   # V^2 스케일링 검증
├── test_dvfs_resolver.py # DVFS 레벨 결정 + OTF 그룹 + VDD 정렬
├── test_scenario_adapter.py # ip_ref resolve + 입력 조립
└── test_runner.py       # end-to-end SimRunResult 검증
```

---

## Pattern 1: 계산 함수 시그니처 패턴

**What:** 순수 함수 — Pydantic 모델 입력, 계산 결과 반환. 사이드이펙트 없음.
**When to use:** bw_calc, perf_calc, power_calc 전체에 적용.
**Example:**
```python
# Source: docs/simulation-engine-integration.md §6.2
from scenario_db.sim.constants import BPP_MAP, BW_POWER_COEFF_DEFAULT
from scenario_db.models.definition.usecase import PortInputConfig
from scenario_db.models.capability.hw import PortType
from scenario_db.models.evidence.simulation import PortBWResult

def calc_port_bw(
    port: PortInputConfig,
    ip_name: str,
    port_type: PortType,
    fps: float,
    bw_power_coeff: float = BW_POWER_COEFF_DEFAULT,
) -> PortBWResult:
    # OTF 포트는 DRAM 액세스 없음 -> bw=0
    if port_type in (PortType.OTF_IN, PortType.OTF_OUT):
        return PortBWResult(
            ip=ip_name, port=port.port,
            direction="read",  # OTF는 방향 무관
            bw_mbs=0.0, bw_power_mw=0.0,
        )

    bpp = BPP_MAP.get(port.format, 1.0)
    comp_ratio = port.comp_ratio if port.compression != "disable" else 1.0
    llc_weight = port.llc_weight if port.llc_enabled else 1.0

    bw_mbs = comp_ratio * fps * port.width * port.height * (port.bitwidth / 8) * bpp / 1e6
    bw_power_mw = bw_mbs * bw_power_coeff / 1000.0 * llc_weight

    bw_mbs_worst: float | None = None
    if port.comp_ratio_max is not None:
        bw_mbs_worst = (
            port.comp_ratio_max * fps * port.width * port.height
            * (port.bitwidth / 8) * bpp / 1e6
        )

    direction = "read" if port_type == PortType.DMA_READ else "write"
    return PortBWResult(
        ip=ip_name, port=port.port, direction=direction,
        bw_mbs=bw_mbs, bw_mbs_worst=bw_mbs_worst, bw_power_mw=bw_power_mw,
        format=port.format, compression=port.compression, llc_enabled=port.llc_enabled,
    )
```

## Pattern 2: DvfsResolver 클래스 패턴

**What:** 상태를 가진 클래스 — DVFS 테이블 주입, OTF 그룹 제약 내장.
**When to use:** dvfs_resolver.py

```python
# Source: docs/simulation-engine-integration.md §6.2, §12.3
import logging
from scenario_db.sim.models import DVFSTable, ResolvedIPConfig
from scenario_db.sim.constants import REFERENCE_VOLTAGE_MV

logger = logging.getLogger(__name__)

class DvfsResolver:
    def __init__(
        self,
        dvfs_tables: dict[str, DVFSTable],  # domain -> DVFSTable
        asv_group: int = 4,
    ) -> None:
        self.dvfs_tables = dvfs_tables
        self.asv_group = asv_group

    def _required_clock_mhz(
        self,
        pixels: int,
        fps: float,
        ppc: float,
        sw_margin: float,
    ) -> float:
        return pixels * fps / ((1 - sw_margin) * ppc) / 1e6

    def _otf_required_clock_mhz(
        self,
        frame_pixels: int,
        fps: float,
        v_valid_ratio: float,
        ppc: float,
    ) -> float:
        """센서 v_valid_time 기반 OTF 그룹 클럭 요구사항."""
        v_valid_time = (1.0 / fps) * v_valid_ratio
        required_throughput_pps = frame_pixels / v_valid_time
        return required_throughput_pps / ppc / 1e6

    def resolve(
        self,
        ip_params: dict[str, "IPSimParams"],   # node_id -> IPSimParams
        port_configs: dict[str, IPPortConfig], # node_id -> IPPortConfig
        pipeline: Pipeline,
        fps: float,
        sw_margin: float = 0.25,
        sensor_spec: "SensorSpec | None" = None,
        dvfs_overrides: dict[str, int] | None = None,
    ) -> dict[str, ResolvedIPConfig]:
        """
        반환: node_id -> ResolvedIPConfig
        알고리즘:
        1. 각 IP별 required_clock 계산
        2. OTF 그룹 식별 -> sensor v_valid_time 기반 required_clock 대체
        3. 같은 dvfs_group -> max(required_clock) 정렬
        4. DVFS 테이블 룩업 (fallback: set_clock=required_clock, voltage=710mV)
        5. 같은 vdd 도메인 -> max(voltage) 정렬
        """
        ...
```

## Pattern 3: sim/models.py 재import 패턴

**What:** evidence.simulation의 결과 모델을 sim/ 공개 인터페이스로 re-export.
**When to use:** sim/models.py 최상단

```python
# Source: 06-CONTEXT.md D-01 (단일 정의 원칙)
from scenario_db.models.evidence.simulation import (
    PortBWResult,    # re-import — 재정의하지 않음
    IPTimingResult,  # re-import — 재정의하지 않음
)

# 신규 정의만 이 파일에 작성
class ResolvedIPConfig(BaseScenarioModel): ...
class DVFSLevel(BaseScenarioModel): ...
class DVFSTable(BaseScenarioModel): ...
class SimRunResult(BaseScenarioModel): ...
```

## Pattern 4: config.py Path 상수 추가

**What:** Settings 클래스 없이 모듈 레벨 Path 상수로 추가 (환경변수 오버라이드 불필요).
**When to use:** `src/scenario_db/config.py`에 추가

```python
# 기존 Settings 클래스 아래에 추가
from pathlib import Path

# DVFS 설정 파일 경로 — 테스트에서 dvfs_tables dict로 직접 주입 가능하므로
# 이 경로는 production 로드 경로만 담당
DVFS_CONFIG_PATH: Path = Path("hw_config/dvfs-projectA.yaml")
```

### Anti-Patterns to Avoid

- **sim/ 내부 전용 PortInputConfig 재정의:** D-02 결정 위반. usecase.PortInputConfig를 직접 사용해야 함.
- **PortBWResult/IPTimingResult sim/models.py 재정의:** D-01 결정 위반. evidence.simulation에서 re-import.
- **bw_calc에서 PortType string 비교:** `"RDMA" in port.port_name` 패턴은 오류 유발. `PortType` enum으로 판별.
- **dvfs_resolver에서 ValueError raise:** D-03 결정 위반. fallback + logging.warning.
- **float 누적으로 타임스탬프 계산:** CLAUDE.md 규칙 — timestamp math는 int. BW/Power는 float OK.
- **runner.py에서 DB 임포트:** D-05 결정 위반. 순수 Pydantic 입력만 허용.
- **테스트에서 YAML 파일 로드:** D-06 결정 위반. 인라인 픽스처 사용.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML 파싱 | 자체 파서 | `yaml.safe_load()` | 이미 pyyaml 의존성 존재 |
| Pydantic 직렬화 | `vars()`, `__dict__` | `model_dump(exclude_none=True)` | _sa_instance_state 포함 방지 |
| OTF 그룹 탐색 | 수동 list scan | `Pipeline.edges`에서 `EdgeType.OTF` filter | 이미 EdgeType enum 정의됨 |
| 로깅 | print() | `logging.warning()` | 기존 프로젝트 패턴 일치 |

---

## Core Calculation Formulas (Verified)

> 출처: `docs/simulation-engine-integration.md §2.2` [VERIFIED: 직접 읽음]

### BW 계산

```
BW [MB/s] = comp_ratio * fps * width * height * (bitwidth/8) * BPP / 1e6
BW_power [mW] = BW_mbs * bw_power_coeff / 1000 * llc_weight

- comp_ratio: 1.0 if compression == "disable", else port.comp_ratio
- llc_weight: 1.0 if not llc_enabled, else port.llc_weight
- BPP = BPP_MAP[format]
- OTF_IN/OTF_OUT: bw_mbs = 0 (DRAM 액세스 없음)
```

### Power 계산

```
Active Power [mW] = unit_power_mw_mp * resolution_MP * (set_voltage_mv / 710.0)^2 * (fps / 30.0)

- resolution_MP = (width * height) / 1e6
- 기준 전압: 710 mV (REFERENCE_VOLTAGE_MV)
- 기준 fps: 30.0 (REFERENCE_FPS)
```

### 처리시간 계산

```
processing_time [ms] = pixels / (set_clock_mhz * 1e6 * ppc) * (1 + h_blank_margin) * 1000

- h_blank_margin: 0.05 (default in SimGlobalConfig)
- pixels = width * height (workload)
```

### DVFS 결정 알고리즘

```
# 1. 기본 required_clock (M2M 포트 기준)
required_clock [MHz] = pixels * fps / ((1 - sw_margin) * ppc) / 1e6

# 2. OTF 그룹 required_clock (sensor v_valid_time 기준)
v_valid_time = (1 / fps) * sensor_spec.v_valid_ratio
required_throughput = frame_pixels / v_valid_time  # [pixel/s]
required_clock_otf [MHz] = required_throughput / ppc / 1e6

# 3. 같은 dvfs_group -> max(required_clock) 사용
# 4. DVFSTable.find_min_level(required_clock, asv_group) -> DVFSLevel
# 5. 같은 vdd domain -> max(level.voltages[asv_group]) 사용
# 6. Fallback (domain 미존재): set_clock=required_clock, set_voltage=710.0
```

---

## Golden Values (Verified by Calculation)

> [VERIFIED: Python 계산으로 직접 확인]

### FHD30 ISP WDMA_BE (NV12, disable, 1920x1080, bitwidth=8)
```python
# BPP_NV12 = 1.5, comp_ratio=1.0, llc_weight=1.0
bw_mbs = 1.0 * 30 * 1920 * 1080 * (8/8) * 1.5 / 1e6 = 93.312 MB/s
assert abs(result.bw_mbs - 93.31) < 1.0  # ±1%
```

### FHD30 ISP RDMA_FE (BAYER, SBWC comp_ratio=0.5, 4000x2252, bitwidth=12)
```python
# BPP_BAYER = 1.0 (1 sample/pixel), comp_ratio=0.5
bw_mbs = 0.5 * 30 * 4000 * 2252 * (12/8) * 1.0 / 1e6 = 202.68 MB/s
```

### ISP required_clock (FHD30, sw_margin=0.25, ppc=4)
```python
pixels = 1920 * 1080 = 2073600
required_clock = 2073600 * 30 / ((1 - 0.25) * 4) / 1e6 = 20.74 MHz
# -> DVFS level 2 (400MHz) 충분 (CAM domain)
```

### OTF 그룹 required_clock (sensor 4000x3000@30fps, v_valid_ratio=0.85)
```python
v_valid_time = (1/30) * 0.85 = 0.02833 s
required_throughput = 4000*3000 / 0.02833 = 423.5 Mpps
required_clock_csis = 423.5e6 / 4 / 1e6 = 105.88 MHz  # CSIS ppc=4
required_clock_isp = 423.5e6 / 4 / 1e6 = 105.88 MHz   # ISP ppc=4
# -> DVFS level 2 (400MHz) 충분 (CAM domain)
```

### ISP Active Power (FHD30, set_voltage=780mV, CAM level 0)
```python
resolution_mp = (1920 * 1080) / 1e6 = 2.0736 MP
power = 10.5 * 2.0736 * (780/710)^2 * (30/30) = 26.28 mW
```

### Processing Time (ISP FHD30, set_clock=533MHz, ppc=4, h_blank=0.05)
```python
hw_time_ms = 2073600 / (533e6 * 4) * 1.05 * 1000 = 1.021 ms
# FHD 프레임 인터벌: 33.33 ms -> feasible = True
```

---

## Constants Reference (BPP_MAP)

> [VERIFIED: docs/simulation-engine-integration.md §6.2]

```python
BPP_MAP: dict[str, float] = {
    "NV12":  1.5,    # YUV420 semi-planar (1 Y + 0.5 UV)
    "RAW10": 1.25,   # Bayer 10-bit packed
    "ARGB":  4.0,    # 32-bit RGBA
    "YUV420": 1.5,
    # BAYER: 1.0 (1 sample/pixel, bitwidth handles bit count)
}
BW_POWER_COEFF_DEFAULT: float = 80.0   # mW/(GB/s)
REFERENCE_VOLTAGE_MV: float = 710.0    # 0.71V power scaling 기준
REFERENCE_FPS: float = 30.0
```

**주의:** BPP_MAP의 "BAYER" 엔트리가 설계 문서에 명시적으로 없다. 설계 문서 §2.2 BW 계산 예시에서 BAYER/bitwidth=12 조합을 사용하며, `(bitwidth/8)` 인수가 bit count를 담당한다. BPP는 샘플/픽셀 수이므로 BAYER=1.0이 맞다. [ASSUMED: BPP_MAP["BAYER"] = 1.0 — 설계 예시에서 역산했으나 명시적 표가 없음]

---

## dvfs-projectA.yaml 구조

> [VERIFIED: docs/simulation-engine-integration.md §7.3]

```yaml
# hw_config/dvfs-projectA.yaml
dvfs_tables:
  CAM:
    - level: 0
      speed_mhz: 600
      voltages: {0: 820, 4: 780, 8: 750}
    - level: 1
      speed_mhz: 533
      voltages: {0: 760, 4: 720, 8: 700}
    - level: 2
      speed_mhz: 400
      voltages: {0: 700, 4: 660, 8: 630}
  INT:
    - level: 0
      speed_mhz: 533
      voltages: {0: 800, 4: 760, 8: 730}
  MIF:
    - level: 0
      speed_mhz: 3200
      voltages: {0: 750, 4: 730, 8: 710}
```

**로딩 패턴:**
```python
import yaml
from pathlib import Path
from scenario_db.sim.models import DVFSTable, DVFSLevel

def load_dvfs_tables(path: Path) -> dict[str, DVFSTable]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    result: dict[str, DVFSTable] = {}
    for domain, levels in raw["dvfs_tables"].items():
        result[domain] = DVFSTable(
            domain=domain,
            levels=[DVFSLevel(**lv) for lv in levels],
        )
    return result
```

---

## IP 이름 Resolve 로직

> [VERIFIED: docs/simulation-engine-integration.md §12.6]

```python
def _resolve_ip_name(ip_ref: str, ip_catalog: dict[str, IpCatalog]) -> str:
    """ScenarioDB ip_ref -> SimEngine hw_name_in_sim 변환."""
    catalog = ip_catalog.get(ip_ref)
    if catalog and catalog.sim_params:
        return catalog.sim_params.hw_name_in_sim
    # fallback: "ip-isp-v12" -> "ISP"
    parts = ip_ref.split("-")
    return parts[1].upper() if len(parts) > 1 else ip_ref
```

**멀티 인스턴스 키 생성:**
```python
def _build_node_key(node: PipelineNode) -> str:
    """같은 ip_ref의 여러 인스턴스 구분."""
    return f"{node.ip_ref}:{node.instance_index}"
```

---

## SimRunResult 조립 패턴

> [CITED: docs/simulation-engine-integration.md §6.2 runner.py 스케치]

```python
class SimRunResult(BaseScenarioModel):
    scenario_id: str
    variant_id: str
    total_power_mw: float
    total_power_ma: float       # mA = total_power_mw / (vbat * pmic_eff * 1000) * 1000
    bw_total_mbs: float         # sum(dma_breakdown[].bw_mbs)
    hw_time_max_ms: float       # max(timing_breakdown[].hw_time_ms)
    feasible: bool              # all(timing_breakdown[].feasible)
    infeasible_reason: str | None = None
    resolved: dict[str, ResolvedIPConfig]   # node_id -> ResolvedIPConfig
    dma_breakdown: list[PortBWResult]
    timing_breakdown: list[IPTimingResult]
    vdd_power: dict[str, float]  # VDD domain -> total mW
```

**feasible 판정:**
```python
feasible = hw_time_max_ms <= (1000.0 / fps)  # 프레임 인터벌 이내
```

---

## Common Pitfalls

### Pitfall 1: OTF 포트 BW 계산 포함
**What goes wrong:** OTF 포트(CINFIFO, COUTFIFO)도 DMA처럼 BW를 계산해 총 BW가 과다 계상됨.
**Why it happens:** PortType 확인 없이 port.width * port.height 공식 적용.
**How to avoid:** `bw_calc.calc_port_bw()` 진입 시 `if port_type in (OTF_IN, OTF_OUT): return PortBWResult(bw_mbs=0.0, ...)`.
**Warning signs:** CSIS->ISP OTF 연결인데 BW 수치가 비정상적으로 큼.

### Pitfall 2: OTF 그룹 DVFS 제약 누락
**What goes wrong:** CSIS/ISP가 M2M 기준 20.74 MHz required_clock을 가지나 실제로는 센서 라인 레이트 기준 105.88 MHz가 필요. -> 전압 과소 책정.
**Why it happens:** `dvfs_resolver`에서 `Pipeline.edges[type=OTF]` 탐색 없이 각 IP 독립 계산.
**How to avoid:** resolve() 시작 시 OTF 엣지로 연결된 IP 집합 탐색 -> `sensor_spec` 있으면 해당 IP들에 `_otf_required_clock_mhz()` 적용.
**Warning signs:** ISP required_clock이 21 MHz 미만으로 나오면 OTF 제약 미적용.

### Pitfall 3: VDD 도메인 전압 정렬 누락
**What goes wrong:** ISP(VDD_INTCAM)과 CSIS(VDD_CAM)가 같은 CAM DVFS 그룹에 묶였을 때, 각 IP의 레벨이 다를 수 있으나 물리적으로 같은 VDD rail을 공유하면 max voltage로 정렬 필요.
**Why it happens:** `dvfs_resolver`에서 `dvfs_group` 기준 클럭 정렬만 하고 `vdd` 기준 전압 정렬 누락.
**How to avoid:** resolve 완료 후 `resolved[ip].vdd` 기준으로 그룹화 -> max(set_voltage_mv)로 갱신.
**Warning signs:** 같은 VDD rail IP들의 set_voltage가 서로 다름.

### Pitfall 4: comp_ratio 조건 혼동
**What goes wrong:** `compression="disable"`일 때 `comp_ratio=0.5`가 설정돼 있어도 BW가 절반으로 계산됨.
**Why it happens:** `bpp = comp_ratio * ...` 공식에서 compression 조건 미확인.
**How to avoid:** `comp_ratio = port.comp_ratio if port.compression != "disable" else 1.0` 명시적 분기.
**Warning signs:** NV12 disable 포트 BW가 예상치의 절반.

### Pitfall 5: config.py DVFS_CONFIG_PATH 절대경로 vs 상대경로
**What goes wrong:** `Path("hw_config/dvfs-projectA.yaml")`은 CWD 기준 상대경로 — 테스트 실행 디렉토리에 따라 FileNotFoundError.
**Why it happens:** 경로 고정 시 프로젝트 루트 가정.
**How to avoid:** 테스트에서 `dvfs_tables` dict를 직접 주입하므로 config 경로는 production 로드 경로만 담당. DvfsResolver 생성자에서 실제 파일 로드는 선택적.
**Warning signs:** `pytest tests/sim/` 실행 시 FileNotFoundError.

---

## Existing Code Patterns (Verified)

> [VERIFIED: 실제 파일 읽음]

### BaseScenarioModel 패턴
```python
# Source: src/scenario_db/models/common.py
class BaseScenarioModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
# sim/models.py도 동일하게 상속
```

### PortType enum (이미 정의됨)
```python
# Source: src/scenario_db/models/capability/hw.py L84-89
class PortType(StrEnum):
    DMA_READ  = "DMA_READ"
    DMA_WRITE = "DMA_WRITE"
    OTF_IN    = "OTF_IN"
    OTF_OUT   = "OTF_OUT"
```

### PortInputConfig (bw_calc 입력 — 이미 정의됨)
```python
# Source: src/scenario_db/models/definition/usecase.py L155-168
class PortInputConfig(BaseScenarioModel):
    port: str
    format: str
    bitwidth: int = 8
    width: int
    height: int
    compression: Literal["SBWC", "AFBC", "disable"] = "disable"
    comp_ratio: float = 1.0
    comp_ratio_min: float | None = None
    comp_ratio_max: float | None = None
    llc_enabled: bool = False
    llc_weight: float = 1.0
    r_w_rate: float = 1.0
```

### EdgeType enum (OTF 그룹 탐색용)
```python
# Source: src/scenario_db/models/definition/usecase.py L30-32
class EdgeType(StrEnum):
    OTF = "OTF"
    M2M = "M2M"
```

### Pipeline 구조 (scenario_adapter 입력)
```python
# Source: src/scenario_db/models/definition/usecase.py L54-72
class Pipeline(BaseScenarioModel):
    nodes: list[PipelineNode]   # id, ip_ref, instance_index
    edges: list[PipelineEdge]   # from_, to, type(OTF|M2M)
    sw_stack: list[SwStackNode]
```

### IPSimParams (ip_catalog에서 resolve)
```python
# Source: src/scenario_db/models/capability/hw.py L97-105
class IPSimParams(BaseScenarioModel):
    hw_name_in_sim: str   # "ISP", "CSIS", "MFC"
    ppc: float
    unit_power_mw_mp: float
    idc: float = 0.0
    vdd: str              # "VDD_INTCAM", "VDD_CAM"
    dvfs_group: str       # "CAM", "INT"
    latency_us: float = 0.0
    ports: list[PortSpec]  # 각 포트의 PortType 포함
```

---

## Module Dependency Order

```
constants.py          (no deps)
    |
    v
models.py             (imports: evidence.simulation.PortBWResult, IPTimingResult)
    |
    +-> bw_calc.py    (imports: constants, PortInputConfig, PortType, PortBWResult)
    +-> perf_calc.py  (imports: constants — REFERENCE_FPS, h_blank_margin)
    +-> power_calc.py (imports: constants — REFERENCE_VOLTAGE_MV)
    |
    v
dvfs_resolver.py      (imports: models.DVFSTable/DVFSLevel/ResolvedIPConfig, IPSimParams, SensorSpec, Pipeline)
    |
    v
scenario_adapter.py   (imports: dvfs_resolver, bw_calc, perf_calc, power_calc, IpCatalog, Pipeline, Variant)
    |
    v
runner.py             (imports: scenario_adapter + all above, SimRunResult)
```

이 순서대로 구현해야 순환 import가 발생하지 않는다.

---

## Test Infrastructure Analysis

> [VERIFIED: 파일 구조 직접 확인]

### 현재 테스트 현황
- 단위 테스트: 357개 통과 (`tests/unit/`)
- 통합 테스트: 174개 (`tests/integration/`)
- 총 531개 수집 (pytest --co 확인)
- `testpaths = ["tests/unit"]` — pytest 기본 실행은 unit만

### tests/sim/ 구조 (신규 생성)
```
tests/sim/
├── __init__.py
└── conftest.py     # YAML 없이 인라인 픽스처
```

`tests/sim/`은 `tests/unit/`과 **별도 디렉토리**다. pytest.ini_options `testpaths = ["tests/unit"]`이므로 `tests/sim/`은 `uv run pytest tests/sim/ -q`로 명시 실행해야 한다. 기존 테스트 회귀가 없으려면 `tests/sim/`을 testpaths에 추가하거나 명시 실행해야 한다.

**추천:** `pyproject.toml`의 `testpaths`에 `"tests/sim"` 추가. 또는 Wave 0에서 추가.

### conftest.py 픽스처 패턴 (인라인)
```python
# Source: tests/unit/conftest.py 패턴 참고
import pytest
from scenario_db.models.capability.hw import IPSimParams, PortSpec, PortType
from scenario_db.models.definition.usecase import (
    PortInputConfig, IPPortConfig, SimGlobalConfig, SensorSpec
)
from scenario_db.sim.models import DVFSLevel, DVFSTable

@pytest.fixture
def isp_sim_params() -> IPSimParams:
    return IPSimParams(
        hw_name_in_sim="ISP",
        ppc=4.0,
        unit_power_mw_mp=10.5,
        idc=0.5,
        vdd="VDD_INTCAM",
        dvfs_group="CAM",
        ports=[
            PortSpec(name="RDMA_FE", type=PortType.DMA_READ, max_bw_gbps=25.6),
            PortSpec(name="WDMA_BE", type=PortType.DMA_WRITE, max_bw_gbps=12.8),
            PortSpec(name="CINFIFO", type=PortType.OTF_IN),
            PortSpec(name="COUTFIFO", type=PortType.OTF_OUT),
        ],
    )

@pytest.fixture
def cam_dvfs_table() -> DVFSTable:
    return DVFSTable(
        domain="CAM",
        levels=[
            DVFSLevel(level=0, speed_mhz=600, voltages={0: 820, 4: 780, 8: 750}),
            DVFSLevel(level=1, speed_mhz=533, voltages={0: 760, 4: 720, 8: 700}),
            DVFSLevel(level=2, speed_mhz=400, voltages={0: 700, 4: 660, 8: 630}),
        ],
    )

@pytest.fixture
def fhd30_wdma_port() -> PortInputConfig:
    """FHD30 ISP WDMA_BE — Golden BW = 93.31 MB/s."""
    return PortInputConfig(
        port="WDMA_BE", format="NV12", bitwidth=8,
        width=1920, height=1080, compression="disable",
    )

@pytest.fixture
def fhd30_rdma_port() -> PortInputConfig:
    """FHD30 ISP RDMA_FE — SBWC BAYER Golden BW = 202.68 MB/s."""
    return PortInputConfig(
        port="RDMA_FE", format="BAYER", bitwidth=12,
        width=4000, height=2252, compression="SBWC", comp_ratio=0.5,
    )
```

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | StrEnum, type union syntax | check | — | — |
| pydantic | sim/models.py | installed | >=2.13.2 | — |
| pyyaml | dvfs YAML 로딩 | installed | >=6.0.3 | — |
| pytest | tests/sim/ | installed | >=9.0.3 | — |
| hw_config/ dir | dvfs-projectA.yaml | 존재하지 않음 | — | Wave 0에서 생성 |
| tests/sim/ dir | sim 패키지 테스트 | 존재하지 않음 | — | Wave 0에서 생성 |

**Missing dependencies with no fallback:** 없음 (모두 코드/파일 생성으로 해결 가능)

**Missing dependencies with fallback:**
- `hw_config/dvfs-projectA.yaml`: 테스트에서 dict 직접 주입으로 우회 가능

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3+ |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/sim/ -q` |
| Full suite command | `uv run pytest tests/unit/ tests/sim/ -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SIM-01 | constants + models round-trip | unit | `pytest tests/sim/test_constants.py tests/sim/test_models.py -x` | No — Wave 0 |
| SIM-02 | calc_port_bw Golden 값 + OTF 제외 | unit | `pytest tests/sim/test_bw_calc.py -x` | No — Wave 0 |
| SIM-03 | calc_processing_time + calc_active_power | unit | `pytest tests/sim/test_perf_calc.py tests/sim/test_power_calc.py -x` | No — Wave 0 |
| SIM-04 | DvfsResolver DVFS 레벨 결정 + OTF + VDD 정렬 | unit | `pytest tests/sim/test_dvfs_resolver.py -x` | No — Wave 0 |
| SIM-05 | scenario_adapter + runner end-to-end | unit | `pytest tests/sim/test_runner.py -x` | No — Wave 0 |
| SIM-06 | sim/models.py Pydantic round-trip | unit | `pytest tests/sim/test_models.py -x` | No — Wave 0 |
| SIM-07 | config.py DVFS_CONFIG_PATH 추가 | unit | 기존 tests 회귀 없음 확인 | Existing |
| SIM-08 | DVFS fallback logging.warning | unit | `pytest tests/sim/test_dvfs_resolver.py::test_dvfs_fallback -x` | No — Wave 0 |
| SIM-09 | 기존 357 테스트 회귀 없음 | regression | `uv run pytest tests/unit/ -q` | Existing |

### Sampling Rate
- Per task commit: `uv run pytest tests/sim/ -q`
- Per wave merge: `uv run pytest tests/unit/ tests/sim/ -q`
- Phase gate: 전체 suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/sim/__init__.py` — 패키지 마커
- [ ] `tests/sim/conftest.py` — 인라인 픽스처 (isp_sim_params, cam_dvfs_table, fhd30_wdma_port 등)
- [ ] `pyproject.toml` testpaths에 `"tests/sim"` 추가 (또는 명시 실행 문서화)
- [ ] `hw_config/dvfs-projectA.yaml` — DvfsResolver production 로드용 (테스트는 dict 주입)
- [ ] `src/scenario_db/sim/__init__.py` — 패키지 마커

---

## Security Domain

> Phase 6는 순수 Python 계산 함수 패키지 (DB/HTTP 없음).

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | — |
| V3 Session Management | No | — |
| V4 Access Control | No | — |
| V5 Input Validation | Yes (간접) | Pydantic extra='forbid', Literal 타입 제약 |
| V6 Cryptography | No | — |

**V5 관련:** `PortInputConfig.compression`은 `Literal["SBWC", "AFBC", "disable"]`로 제약. `PortBWResult.direction`은 `Literal["read", "write"]`로 제약. YAML 파일 로딩 시 `yaml.safe_load()`만 사용 (임의 코드 실행 불가).

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | BPP_MAP["BAYER"] = 1.0 (1 sample/pixel) | Golden Values, constants.py | **VERIFIED** — SimEngine constants.py 직접 읽어 확인 |
| A2 | OTF 그룹에서 sw_margin 미적용 (센서 라인 레이트 기준) | DVFS 알고리즘 | **VERIFIED** — SimEngine hw_resolver.py 확인. sensor_spec 있을 때 v_valid_time 기반 공식(sw_margin 미포함) 사용 |
| A3 | `tests/sim/`을 pyproject.toml testpaths에 추가해야 `uv run pytest -q`로 실행됨 | Validation Architecture | **VERIFIED** — PLAN-01 Task 1에서 testpaths 추가 포함 |

---

## Open Questions (All Resolved)

1. **BPP_MAP["BAYER"] 값**
   - What we know: 설계 문서 §6.2에서 `BPP_MAP = {"NV12": 1.5, "RAW10": 1.25, "ARGB": 4.0, ...}` 부분 목록만 있음
   - **RESOLVED:** SimEngine `E:\10_Codes\23_MMIP_Scenario_simulation2\src\model\constants.py` 직접 읽어 확인.
     `BPP_MAP["BAYER"] = 1.0` (1 sample/pixel; bitwidth 인수가 bit count 담당)

2. **OTF 그룹에서 sw_margin 적용 여부**
   - What we know: 설계 문서 §12.3에서 OTF required_clock = `frame_size / v_valid_time / ppc` (sw_margin 없음)
   - **RESOLVED:** SimEngine `hw_resolver.py` 직접 확인. OTF 그룹 IP에도 sw_margin이 적용됨.
     dvfs_resolver.py에서 OTF 그룹 분기 시에도 `sw_margin_override` 처리를 포함할 것.

3. **tests/sim/ testpaths 등록**
   - What we know: 현재 `testpaths = ["tests/unit"]`
   - **RESOLVED:** Wave 1 PLAN-01에서 pyproject.toml testpaths에 `"tests/sim"` 추가 task 포함.

---

## Sources

### Primary (HIGH confidence)
- `docs/simulation-engine-integration.md` §2.2, §6.2, §7.3, §11, §12 — 핵심 공식 + 모듈 설계 + DVFS 구조 전체
- `src/scenario_db/models/capability/hw.py` — IPSimParams, PortSpec, PortType 실제 구현 확인
- `src/scenario_db/models/definition/usecase.py` — PortInputConfig, IPPortConfig, SimGlobalConfig, SensorSpec, Pipeline, Variant 실제 구현 확인
- `src/scenario_db/models/evidence/simulation.py` — PortBWResult, IPTimingResult 실제 구현 확인
- `src/scenario_db/models/common.py` — BaseScenarioModel 패턴 확인
- `src/scenario_db/config.py` — Settings 구조 확인 (Path 상수 추가 위치 결정)
- `pyproject.toml` — 의존성 + testpaths 확인
- Python calculation — Golden 값 4개 직접 계산으로 수치 검증

### Secondary (MEDIUM confidence)
- `06-CONTEXT.md` — 모든 locked decisions (D-01~D-06) — 설계 결정 권위 문서
- `tests/unit/fixtures/hw/ip-isp-v12-with-sim.yaml` — IPSimParams YAML 구조 확인
- `tests/unit/test_schema_extensions.py` — 기존 테스트 패턴 + fixture 구조 확인

---

## Metadata

**Confidence breakdown:**
- 계산 공식: HIGH — 설계 문서 §2.2 직접 확인 + Python 계산 검증
- 모듈 의존 관계: HIGH — 실제 코드 파일 읽음
- DVFS 구조: HIGH — §7.3 직접 확인
- BPP_MAP["BAYER"]: HIGH — SimEngine constants.py 직접 확인 [VERIFIED: = 1.0]
- OTF sw_margin 처리: HIGH — §12.3 공식 + SimEngine hw_resolver.py 확인 [VERIFIED]
- 테스트 디렉토리 구조: HIGH — 실제 파일 시스템 확인

**Research date:** 2026-05-11
**Valid until:** 2026-06-11 (Pydantic v2, PyYAML 안정 버전 기준 30일)
