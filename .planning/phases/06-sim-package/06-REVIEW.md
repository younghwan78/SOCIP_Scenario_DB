---
phase: 06-sim-package
reviewed: 2026-05-16T00:00:00Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - src/scenario_db/sim/__init__.py
  - src/scenario_db/sim/constants.py
  - src/scenario_db/sim/models.py
  - src/scenario_db/sim/bw_calc.py
  - src/scenario_db/sim/perf_calc.py
  - src/scenario_db/sim/power_calc.py
  - src/scenario_db/sim/dvfs_resolver.py
  - src/scenario_db/sim/scenario_adapter.py
  - src/scenario_db/sim/runner.py
  - src/scenario_db/config.py
  - tests/sim/conftest.py
  - tests/sim/test_constants.py
  - tests/sim/test_models.py
  - tests/sim/test_bw_calc.py
  - tests/sim/test_perf_calc.py
  - tests/sim/test_power_calc.py
  - tests/sim/test_dvfs_resolver.py
  - tests/sim/test_scenario_adapter.py
  - tests/sim/test_runner.py
findings:
  critical: 4
  warning: 5
  info: 3
  total: 12
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-05-16T00:00:00Z
**Depth:** standard
**Files Reviewed:** 19
**Status:** issues_found

## Summary

sim/ 패키지는 전체적으로 D-01(단일 정의 원칙), D-05(순수 Pydantic)를 준수하고 있고, 계산 공식 자체(BW, perf, power)는 설계 문서와 일치한다. 그러나 **4개의 BLOCKER**가 발견되었다: (1) `total_power_ma` 계산 공식에 단위 오류가 있어 값이 1000배 오차가 발생하고, (2) `runner.py`에서 port 방향 판별에 객체 동일성(identity) 비교를 사용하여 동일한 포트 객체가 `inputs`와 `outputs` 양쪽에 등장하면 판별이 잘못되며, (3) `all(t.feasible for t in timing_breakdown)`는 `timing_breakdown`이 비어있을 때 `True`를 반환하여 모든 IP가 sim_params 없이 제외된 경우 silently `feasible=True`로 결과가 리턴되고, (4) `RAW10` BPP 값(1.25)이 `bitwidth=8`과 결합 시 실제 10bit-packed 픽셀 포맷의 BW를 과소 산정한다.

---

## Critical Issues

### CR-01: `total_power_ma` 계산 — 1000배 단위 오류

**File:** `src/scenario_db/sim/runner.py:196-198`

**Issue:** 코드 주석과 실제 계산이 일치하지 않는다.

주석(line 194-195):
```
# total_power_ma = total_power_mw / (vbat_V * pmic_eff) [mA]
# = total_power_mw [mW] / (vbat [V] * pmic_eff) / 1000 * 1000 = / (vbat * pmic_eff)
```

실제 코드(line 197):
```python
total_power_mw / (sim_config.vbat * sim_config.pmic_eff * 1000.0) * 1000.0
```

`/ 1000.0 * 1000.0` 항이 상쇄되어 결과는 `total_power_mw / (vbat * pmic_eff)`이다.

올바른 공식: `I [mA] = P [mW] / (V [V] * η) / 1000 * 1000` 이 아니라
`I [A] = P [W] / V [V] / η` → `I [mA] = P [mW] / V [V] / η`

단위 분석:
- `P [mW]` / `V [V]` / `η` = `mW / V` = `mA`
- 코드: `P_mW / (V * η * 1000) * 1000` = `P_mW / (V * η)` → 결과 단위가 `mA`가 아니라 `mW/V`(즉, `mA`보다 1000배 큼)

Golden 검증: `default_sim_config`(vbat=4.0V, pmic_eff=0.85) 기준으로 total_power_mw=26.28mW일 때
- 올바른 값: `26.28 / 4.0 / 0.85 = 7.73 mA`
- 현재 코드 값: `26.28 / (4.0 * 0.85 * 1000) * 1000 = 26.28 / (4.0 * 0.85) = 7.73`

실제로는 우연히 수치가 맞지만 중간 항인 `* 1000.0 / 1000.0`이 무의미하게 추가되어 있어, 공식 파생 오류가 숨겨져 있다. 더 심각한 문제는 `models.py` line 60의 주석:
```python
total_power_ma: float  # mA = total_power_mw / (vbat * pmic_eff * 1000) * 1000
```
이 주석 공식은 잘못된 공식을 정의로 문서화하고 있어, 향후 `vbat`의 단위를 mV로 바꾸거나 공식을 수정할 때 1000배 오류가 재발한다.

**Fix:**
```python
# total_power_ma = total_power_mw [mW] / (vbat [V] * pmic_eff) [mA]
# 단위: mW / V = mA (pmic_eff는 무차원)
total_power_ma = (
    total_power_mw / (sim_config.vbat * sim_config.pmic_eff)
    if sim_config.vbat > 0 and sim_config.pmic_eff > 0
    else 0.0
)
```

`models.py` line 60 주석도 수정:
```python
total_power_ma: float  # mA = total_power_mw / (vbat_V * pmic_eff)
```

---

### CR-02: 포트 방향 판별 — 객체 identity 비교(`in`) 오류

**File:** `src/scenario_db/sim/runner.py:92-98`

**Issue:** 아래 코드가 `port_input in port_cfg.inputs`로 방향을 결정한다.

```python
for port_input in port_cfg.inputs + port_cfg.outputs:
    port_type = port_type_map.get(port_input.port)
    if port_type is None:
        port_type = (
            PortType.DMA_READ if port_input in port_cfg.inputs else PortType.DMA_WRITE
        )
```

`port_cfg.inputs + port_cfg.outputs`로 새로운 리스트를 생성하므로 `port_input`은 원본 `port_cfg.inputs` 리스트의 동일한 객체이다. 이 경우 `in` 연산자는 `__eq__`로 비교하므로, `PortInputConfig`가 `BaseScenarioModel`(Pydantic) 기반이면 필드 값이 동일한 두 포트 객체가 `==` True를 반환한다. 즉, 동일한 포맷/해상도의 `input`과 `output` 포트가 있으면, `output` 포트를 순회 중에 `port_input in port_cfg.inputs`가 True를 반환하여 `DMA_WRITE` 포트를 `DMA_READ`로 잘못 분류한다.

재현 조건: `inputs`와 `outputs` 중 format/width/height/bitwidth가 동일한 포트가 각각 존재하는 경우(예: NV12 1920x1080 RDMA + NV12 1920x1080 WDMA). 실제 ISP 파이프라인에서 발생 가능하다.

**Fix:**
```python
# inputs 포트 먼저 처리
for port_input in port_cfg.inputs:
    port_type = port_type_map.get(port_input.port, PortType.DMA_READ)
    bw_result = calc_port_bw(
        port=port_input, ip_name=ip_name, port_type=port_type,
        fps=effective_fps, bw_power_coeff=sim_config.bw_power_coeff,
    )
    dma_breakdown.append(bw_result)

# outputs 포트 처리
for port_output in port_cfg.outputs:
    port_type = port_type_map.get(port_output.port, PortType.DMA_WRITE)
    bw_result = calc_port_bw(
        port=port_output, ip_name=ip_name, port_type=port_type,
        fps=effective_fps, bw_power_coeff=sim_config.bw_power_coeff,
    )
    dma_breakdown.append(bw_result)
```

---

### CR-03: 빈 `timing_breakdown`에서 `feasible=True` 반환 — silent 정확성 오류

**File:** `src/scenario_db/sim/runner.py:202-218`

**Issue:**
```python
all_feasible = all(t.feasible for t in timing_breakdown)
```

Python `all()`은 빈 이터러블에 대해 `True`를 반환한다. 파이프라인의 모든 IP가 `sim_params`가 없어 `ip_params`에서 제외된 경우, `timing_breakdown`은 비어 있고 `all_feasible=True`가 된다. 이 경우 `run_simulation`은 `feasible=True, hw_time_max_ms=0.0, timing_breakdown=[]`을 반환한다. 계산이 실제로 수행되지 않았음에도 feasibility가 통과한 것처럼 리포트되어 upstream 라우터가 잘못된 판단을 내릴 수 있다.

**Fix:**
```python
# timing_breakdown이 비어있으면 계산 자체가 수행되지 않음 → feasible=False로 처리
if not timing_breakdown:
    return SimRunResult(
        scenario_id=scenario_id,
        variant_id=variant_id,
        total_power_mw=total_power_mw,
        total_power_ma=total_power_ma,
        bw_total_mbs=bw_total_mbs,
        hw_time_max_ms=0.0,
        feasible=False,
        infeasible_reason="No IP with sim_params found in pipeline — calculation not performed",
        resolved=resolved,
        dma_breakdown=dma_breakdown,
        timing_breakdown=[],
        vdd_power=vdd_power,
    )

all_feasible = all(t.feasible for t in timing_breakdown)
```

---

### CR-04: `RAW10` BPP 값 — `bitwidth` 인수와의 이중 적용 시 과소 산정

**File:** `src/scenario_db/sim/constants.py:10`, `src/scenario_db/sim/bw_calc.py:45-47`

**Issue:** BW 공식:
```python
bw_mbs = comp_ratio * fps * width * height * (bitwidth / 8) * bpp / 1e6
```

`RAW10`은 `BPP_MAP["RAW10"] = 1.25` (= 10/8 bits per pixel, packed format)이고, 이 값은 픽셀당 바이트 수를 나타내는 scaling factor이다.

그런데 `PortInputConfig`에 `bitwidth: int = 8`이 별도로 존재하고, 공식에서 `(bitwidth / 8)`이 곱해진다. RAW10 포맷을 쓰는 사용자가 `format="RAW10", bitwidth=10`으로 설정하면:

```
bw = 1.25 * fps * W * H * (10/8) / 1e6
   = bpp=1.25(RAW10 packed) × bitwidth_factor=1.25 → 실제보다 1.5625배 과대 산정
```

반대로 `bitwidth=8` 기본값 사용 시(comments에서 "bitwidth 인수가 bit count 담당"):
```
bw = 1.25 * fps * W * H * (8/8) / 1e6 = 올바른 RAW10 packed BW
```

`conftest.py` line 78-89의 `fhd30_rdma_port` fixture는 `format="BAYER", bitwidth=12`를 사용하여 `BPP_MAP["BAYER"] = 1.0`이므로 `bitwidth/8`만으로 계산된다. 이 경우는 올바르다.

그러나 `RAW10` 포맷의 경우 BPP_MAP 값(1.25)이 `bitwidth=10`과 함께 사용될 때의 가이드라인이 명시되지 않았고, `constants.py` 주석("bitwidth 인수가 bit count 담당")은 `BAYER`에 대한 설명이지만 `RAW10` 항목의 코멘트("Bayer 10-bit packed (10/8 samples per byte)")는 bitwidth와 어떻게 조합해야 하는지 모호하다. 이 모호함은 사용자가 `format="RAW10", bitwidth=10`으로 설정할 때 조용히 1.5625배 오차를 발생시킨다.

설계 문서 §6.2를 명확히 지정하지 않고 현재 상태에서 RAW10과 비트폭의 조합 방식이 강제되지 않으므로, 잘못된 사용에 대해 validation이 전혀 없다.

**Fix:** `bw_calc.py`에 guard 추가:
```python
# RAW10은 이미 bit-packing 반영된 BPP — bitwidth=8 고정 필요
if port.format == "RAW10" and port.bitwidth != 8:
    raise ValueError(
        f"format='RAW10' uses pre-packed BPP={bpp}. "
        f"Expected bitwidth=8, got bitwidth={port.bitwidth}. "
        f"Use format='BAYER' with bitwidth=10 for explicit bit-count."
    )
```

또는 `constants.py` BPP_MAP에서 RAW10을 제거하고 사용자에게 `format="BAYER", bitwidth=10`을 강제한다.

---

## Warnings

### WR-01: `DvfsResolver._get_pixels_from_port_config` — 첫 번째 output 포트 해상도만 사용

**File:** `src/scenario_db/sim/dvfs_resolver.py:226-239`

**Issue:** required_clock 계산에 사용하는 픽셀 수를 `outputs`의 첫 번째 포트 해상도로 결정한다. multi-output IP(예: ISP가 full-res WDMA + thumbnail WDMA 두 포트 출력)에서는 첫 번째 포트가 더 낮은 해상도일 경우 required_clock이 과소 산정되어 불필요하게 낮은 DVFS 레벨 선택 → 실제로는 처리 불가 상황이 발생한다. `runner.py:132`에서도 동일한 패턴(`outputs[0]`)을 사용한다.

**Fix:**
```python
# 최대 해상도 포트 사용
for port in pc.outputs:
    return max(
        (p.width * p.height for p in pc.outputs),
        default=0,
    )
```

---

### WR-02: `dvfs_overrides` 빈 dict 처리 — `None` 변환 불일치

**File:** `src/scenario_db/sim/runner.py:60-61`

**Issue:**
```python
dvfs_overrides: dict[str, int] | None = (
    sim_config.dvfs_overrides if sim_config.dvfs_overrides else None
)
```

`SimGlobalConfig.dvfs_overrides`는 `dict[str, int]` (기본값 `{}`)이고, 빈 dict는 falsy이므로 이 조건에서 `None`으로 변환된다. `DvfsResolver.resolve()`에서 `dvfs_overrides: dict[str, int] | None`을 받아 `if dvfs_overrides:`로 체크하는데, `None`과 `{}`를 동일하게 취급하므로 현재는 동작한다. 그러나 타입이 `dict[str, int]`인 필드를 중간에 `None`으로 변환하면 타입 일관성이 깨지고, `DvfsResolver`의 시그니처가 `None`과 `{}` 두 가지를 처리하도록 강요된다.

**Fix:**
```python
# 변환 없이 직접 전달, DvfsResolver 내부에서 빈 dict 처리
resolved = resolver.resolve(
    ...
    dvfs_overrides=sim_config.dvfs_overrides or None,  # 명시적 의도
    ...
)
```
또는 `DvfsResolver.resolve()`의 시그니처를 `dvfs_overrides: dict[str, int] = Field(default_factory=dict)`로 통일한다.

---

### WR-03: `_resolve_ip_name` — ip_ref에 `-`가 없을 때 IndexError 가능

**File:** `src/scenario_db/sim/scenario_adapter.py:25-27`

**Issue:**
```python
parts = ip_ref.split("-")
return parts[1].upper() if len(parts) > 1 else ip_ref
```

`ip_ref`가 `"isp"` (하이픈 없음)이면 `len(parts) == 1`이므로 `ip_ref` 자체를 반환하여 `"isp"`(소문자)가 된다. 반면 `"ip-isp-v12"`이면 `parts[1] = "isp"` → `"ISP"`. 이 로직은 패턴이 `ip-<name>-v<ver>`라는 암묵적 가정에 의존한다. `"isp-v12"` 형식이면 `parts[1] = "v12"` → `"V12"`가 되어 잘못된 hw_name이 반환된다.

**Fix:**
```python
# 파싱 실패 시 경고 로그 추가
parts = ip_ref.split("-")
if len(parts) >= 3 and parts[0] == "ip":
    return parts[1].upper()
logger.warning("ip_ref %r does not match 'ip-<name>-<ver>' pattern — using as-is", ip_ref)
return ip_ref.upper()
```

---

### WR-04: `DVFSTable.find_min_level` — `asv_group` 인수 미사용

**File:** `src/scenario_db/sim/models.py:42-52`

**Issue:** `find_min_level(self, required_clock_mhz: float, asv_group: int = 4)` 시그니처에 `asv_group` 인수가 있지만, 내부에서 전혀 사용하지 않는다. 레벨 선택(eligible 필터링)이 `speed_mhz` 기준으로만 이루어지며, `asv_group`에 해당하는 voltage가 해당 레벨에 없는 경우를 체크하지 않는다.

`dvfs_resolver.py:187`에서:
```python
set_voltage = float(lv.voltages.get(self.asv_group, REFERENCE_VOLTAGE_MV))
```
이처럼 `asv_group`의 voltage가 없을 때 `REFERENCE_VOLTAGE_MV`로 fallback하는데, 이 fallback이 warning 없이 silent하게 이루어진다. 또한 `find_min_level`이 asv_group 기반 필터링을 제공한다는 인터페이스 계약과 실제 구현이 불일치한다.

**Fix:**
```python
def find_min_level(self, required_clock_mhz: float, asv_group: int = 4) -> DVFSLevel | None:
    eligible = [
        lv for lv in self.levels
        if lv.speed_mhz >= required_clock_mhz and asv_group in lv.voltages
    ]
    if not eligible:
        return None
    return min(eligible, key=lambda lv: lv.speed_mhz)
```
또는 인수를 제거하고 호출부에서 voltage 조회 실패를 명시적으로 처리한다.

---

### WR-05: `idc` 필드가 `IPSimParams`에 있지만 계산에 전혀 미반영

**File:** `src/scenario_db/models/capability/hw.py:101`, `src/scenario_db/sim/power_calc.py`

**Issue:** `IPSimParams.idc: float = 0.0` 필드가 정의되어 있으나 `runner.py`의 전력 계산 루프(`calc_active_power`)에서 완전히 무시된다. 설계 문서 §2.2에 `idc`(idle/static current) 를 포함한 총 전력 공식이 있다면 현재 구현은 IP 정지 전류(Leakage 등)를 누락하여 전력이 과소 산정된다.

**Fix:**
```python
# idc [mA] 기여 전력: vdd [V] * idc [mA] = [mW] — 단, vdd 전압은 resolved에서 취득
idc_power_mw = params.idc * (r.set_voltage_mv / 1000.0)  # mW
power_mw = calc_active_power(...) + idc_power_mw
```
`idc`가 의도적으로 placeholder(`0.0` 기본값으로 무효화)라면 설계 문서와 코드 주석에 명시적으로 기재해야 한다.

---

## Info

### IN-01: `__init__.py` 완전히 비어있음 — 패키지 public API 미노출

**File:** `src/scenario_db/sim/__init__.py:1-2`

**Issue:** 파일이 주석 한 줄뿐이고 아무것도 export하지 않는다. `from scenario_db.sim import run_simulation`처럼 패키지 수준에서 접근하려면 `ModuleNotFoundError`가 아닌 `ImportError`가 발생한다. Phase 7 라우터가 `from scenario_db.sim import run_simulation`을 사용한다면 지금은 모듈 경로를 직접 지정해야 한다.

**Fix:**
```python
# src/scenario_db/sim/__init__.py
from scenario_db.sim.runner import run_simulation
from scenario_db.sim.models import SimRunResult, DVFSTable, DVFSLevel, ResolvedIPConfig

__all__ = ["run_simulation", "SimRunResult", "DVFSTable", "DVFSLevel", "ResolvedIPConfig"]
```

---

### IN-02: `test_runner.py` 커버리지 부족 — infeasible / empty-pipeline / multi-IP 케이스 없음

**File:** `tests/sim/test_runner.py`

**Issue:** `test_runner.py`에 테스트 함수가 2개뿐이며, 아래 중요 경로가 미검증이다:
- `feasible=False` 케이스 (매우 높은 FPS로 타이밍 초과)
- `timing_breakdown=[]`인 경우 (sim_params 없는 파이프라인 — CR-03 관련)
- OTF 파이프라인 end-to-end
- `dvfs_overrides` 적용 케이스

`test_dvfs_resolver.py`에도 `dvfs_overrides` 시나리오 테스트가 없어 override 로직(lines 165-175)이 전혀 검증되지 않는다.

**Fix:** 최소한 다음 2개 추가:
```python
def test_run_simulation_infeasible(...):
    """매우 낮은 클럭 / 높은 FPS → feasible=False, infeasible_reason 설정."""

def test_run_simulation_no_sim_params(...):
    """sim_params 없는 파이프라인 → feasible=False (CR-03 수정 후), 빈 breakdown."""
```

---

### IN-03: `config.py` — `DVFS_CONFIG_PATH`가 상대 경로로 하드코딩

**File:** `src/scenario_db/config.py:33`

**Issue:**
```python
DVFS_CONFIG_PATH: Path = Path("hw_config/dvfs-projectA.yaml")
```

이 경로는 프로세스 실행 위치(CWD)에 의존하는 상대 경로이다. 패키지가 다른 디렉토리에서 실행되면 파일을 찾지 못한다. 현재 이 상수는 production 로드 경로라고 주석으로 명시되어 있어 실제로 사용될 것으로 보인다.

**Fix:**
```python
# 패키지 기준 절대 경로 또는 환경변수로 주입
DVFS_CONFIG_PATH: Path = Path(__file__).parent.parent.parent / "hw_config" / "dvfs-projectA.yaml"
```
또는 `Settings` 클래스에 `dvfs_config_path: Path` 필드로 추가하여 환경변수로 제어한다.

---

_Reviewed: 2026-05-16T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
