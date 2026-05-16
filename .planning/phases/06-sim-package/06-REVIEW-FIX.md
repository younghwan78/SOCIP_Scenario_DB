---
phase: 06-sim-package
fixed_at: 2026-05-16T00:00:00Z
review_path: .planning/phases/06-sim-package/06-REVIEW.md
iteration: 1
findings_in_scope: 9
fixed: 9
skipped: 0
status: all_fixed
---

# Phase 6: Code Review Fix Report

**Fixed at:** 2026-05-16T00:00:00Z
**Source review:** `.planning/phases/06-sim-package/06-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 9 (CR-01~04, WR-01~05)
- Fixed: 9
- Skipped: 0

---

## Fixed Issues

### CR-01: `total_power_ma` 공식 — 상쇄되는 ×1000/1000 제거

**Files modified:** `src/scenario_db/sim/runner.py`, `src/scenario_db/sim/models.py`
**Commit:** 291a348
**Applied fix:**
- `runner.py`: `/ (vbat * pmic_eff * 1000.0) * 1000.0` → `/ (vbat * pmic_eff)` 으로 상쇄 항 제거
- `runner.py`: 주석도 올바른 단위 유도 과정으로 수정 (`mW / V = mA`)
- `models.py`: `SimRunResult.total_power_ma` 필드 주석을 `mA = total_power_mw / (vbat_V * pmic_eff)` 로 정정

---

### CR-02: 포트 방향 판별 — inputs/outputs 분리 루프로 Pydantic `__eq__` 오판별 방지

**Files modified:** `src/scenario_db/sim/runner.py`
**Commit:** 48fc2e4
**Applied fix:**
- `port_cfg.inputs + port_cfg.outputs` 합산 루프를 inputs/outputs 별도 루프 2개로 분리
- inputs 루프: `PortType.DMA_READ` 기본값, outputs 루프: `PortType.DMA_WRITE` 기본값
- 기존 `port_input in port_cfg.inputs` Pydantic `__eq__` 비교(동일 format/해상도 오판별) 제거

---

### CR-03: 빈 `timing_breakdown` → `feasible=False` 방어 코드

**Files modified:** `src/scenario_db/sim/runner.py`
**Commit:** 4678a2c
**Applied fix:**
- `hw_time_max_ms` / `all_feasible` 계산 전에 `if not timing_breakdown:` guard 추가
- sim_params 있는 IP가 없는 경우 `feasible=False`, `infeasible_reason="No IP with sim_params found in pipeline — calculation not performed"` 로 즉시 반환

---

### CR-04: `RAW10` BPP 이중 적용 방지 — `bitwidth!=8` 시 `ValueError`

**Files modified:** `src/scenario_db/sim/bw_calc.py`
**Commit:** 37bf8cf
**Applied fix:**
- `bpp = BPP_MAP.get(port.format, 1.0)` 직후에 guard 추가
- `format="RAW10"` 이면서 `bitwidth != 8`인 경우 명확한 `ValueError` 메시지와 함께 즉시 raise
- 사용자에게 `format='BAYER', bitwidth=10` 사용을 권고하는 메시지 포함

---

### WR-01: multi-output IP 최대 해상도 포트 사용

**Files modified:** `src/scenario_db/sim/dvfs_resolver.py`, `src/scenario_db/sim/runner.py`
**Commit:** 672792d
**Applied fix:**
- `dvfs_resolver.py` `_get_pixels_from_port_config`: `for port in pc.outputs: return port.width * port.height` (첫 번째만 반환) → `max(p.width * p.height for p in pc.outputs)` 로 변경
- `runner.py` timing 계산 루프: `outputs[0].width * outputs[0].height` → `max(p.width * p.height for p in port_cfg.outputs)`
- `runner.py` power 계산 루프: `outputs[0].width/height` → `max_port = max(..., key=lambda p: p.width * p.height)` 로 변경

---

### WR-02: `dvfs_overrides` 빈 dict→None 변환 정리

**Files modified:** `src/scenario_db/sim/runner.py`
**Commit:** fce6086
**Applied fix:**
- 중간 변수 `dvfs_overrides: dict[str, int] | None = (sim_config.dvfs_overrides if sim_config.dvfs_overrides else None)` 제거
- `resolver.resolve()` 호출 시 인수를 `dvfs_overrides=sim_config.dvfs_overrides or None` 으로 직접 전달

---

### WR-03: `_resolve_ip_name` fallback 파싱 강화

**Files modified:** `src/scenario_db/sim/scenario_adapter.py`
**Commit:** c1dce1f
**Applied fix:**
- 기존 `parts[1].upper() if len(parts) > 1 else ip_ref` 단순 fallback 제거
- `len(parts) >= 3 and parts[0] == "ip"` 조건을 만족할 때만 `parts[1].upper()` 반환
- 불일치 시 `logger.warning(...)` 출력 후 `ip_ref.upper()` 반환 (소문자 그대로 반환하던 버그도 수정)

---

### WR-04: `find_min_level` `asv_group` 필터링 활성화

**Files modified:** `src/scenario_db/sim/models.py`
**Commit:** 54ffdad
**Applied fix:**
- `eligible` list comprehension에 `and asv_group in lv.voltages` 조건 추가
- 해당 asv_group의 voltage 항목이 없는 레벨을 후보에서 제외하여 시그니처와 구현 일치

---

### WR-05: `idc` idle current 미적용 — 의도적 placeholder 명시

**Files modified:** `src/scenario_db/sim/runner.py`
**Commit:** 65536fa
**Applied fix:**
- `calc_active_power()` 호출 직후에 idc 미포함 이유와 향후 확장 지점을 명시하는 주석 추가
- 로직 변경 없음 — active power만 계산하는 현재 scope가 의도적임을 문서화

---

## Skipped Issues

없음 — 모든 Critical/Warning 항목이 성공적으로 수정됨.

---

## Test Results

수정 완료 후 `uv run pytest tests/sim/ tests/unit/ -v --tb=short` 실행:

- **398 passed** in 0.89s
- `run_simulation` import 정상 확인

---

_Fixed: 2026-05-16T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
