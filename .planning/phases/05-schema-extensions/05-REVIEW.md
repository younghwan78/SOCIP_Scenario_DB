---
phase: 05-schema-extensions
reviewed: 2026-05-10T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - src/scenario_db/models/capability/hw.py
  - src/scenario_db/models/definition/usecase.py
  - src/scenario_db/models/evidence/simulation.py
  - src/scenario_db/db/models/capability.py
  - src/scenario_db/db/models/definition.py
  - src/scenario_db/db/models/evidence.py
  - src/scenario_db/etl/mappers/capability.py
  - src/scenario_db/etl/mappers/definition.py
  - src/scenario_db/etl/mappers/evidence.py
  - alembic/versions/0002_schema_extensions.py
  - tests/unit/test_schema_extensions.py
  - tests/integration/test_schema_extensions.py
findings:
  critical: 2
  warning: 4
  info: 3
  total: 9
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-05-10T00:00:00Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Phase 5 (Schema Extensions)은 8개 신규 Pydantic 모델, 6개 nullable JSONB 컬럼, Alembic 0002 마이그레이션, ETL mapper 확장, 유닛·통합 테스트 총 24개를 추가했다. 전반적으로 구조가 일관적이고 backward compatibility 전략도 올바르다.

하지만 **critical 2건**을 포함한 실질적 결함이 발견되었다.

1. **ETL mapper에서 `sw_baseline_ref`가 None일 때 런타임 AttributeError** — 실제 데이터로 재현 가능.
2. **`PortBWResult` KPI 키 검증 누락** — 도메인 네이밍 규약(소문자 스네이크케이스)이 새 breakdown 필드 `ip`, `port`에 적용되지 않는다.
3. Warning 4건: `PortInputConfig.r_w_rate` 범위 미검증, `IPSimParams.ppc` 양수 미검증, `sim-FHD30-with-breakdown.yaml` fixture `variant_ref` 미스매치, 통합 테스트 session-scope 공유 DB에서 id 충돌 위험.

---

## Critical Issues

### CR-01: ETL `upsert_simulation` — `sw_baseline_ref` None 시 AttributeError 런타임 크래시

**File:** `src/scenario_db/etl/mappers/evidence.py:20`

**Issue:**
```python
row.sw_baseline_ref = str(obj.execution_context.sw_baseline_ref)
```
`ExecutionContext.sw_baseline_ref`는 `DocumentId` 타입으로 Pydantic 모델에서 필수 필드이므로 YAML에 누락 시 ValidationError가 먼저 발생한다. 그러나 `upsert_measurement` 쪽 (line 56)도 동일한 패턴이며, 두 함수 모두 `execution_context.sw_baseline_ref`가 빈 문자열(`""`)인 경우 `str("")` = `""` 가 DB FK 컬럼에 저장되어 FK 제약(`ForeignKey("sw_profiles.id")`) 위반이 발생한다.

더 중요한 문제는: `ExecutionContext` 스키마가 `sw_baseline_ref: DocumentId`로 **required**이지만, `Evidence` ORM 컬럼은 `sw_baseline_ref = Column(Text, ForeignKey("sw_profiles.id"))` — nullable. 통합 테스트 `test_dma_breakdown_etl_empty_default`에서 기존 fixture의 `id`를 `"sim-evidence-no-breakdown-test"`로 교체하지만, `sw_baseline_ref` 값 `"sw-vendor-v1.2.3"`이 DB에 아직 없을 수 있다. 만약 `sw_profiles` 테이블에 해당 row가 없으면 FK 위반으로 커밋이 실패한다.

`upsert_simulation` / `upsert_measurement` 는 `sw_baseline_ref`에 대한 FK 존재 여부를 silent하게 가정하는데, `session_scope` 통합 DB는 demo fixtures로 초기화되지만 **unit fixture id를 직접 주입하는 통합 테스트는 FK 부모 row 없이 insert를 시도**한다.

**Fix:**
```python
# Option 1: sw_baseline_ref가 참조하는 프로필이 없을 수 있으므로 None 허용
row.sw_baseline_ref = (
    str(obj.execution_context.sw_baseline_ref)
    if obj.execution_context.sw_baseline_ref else None
)
```
또는 통합 테스트에서 fixture의 `sw_baseline_ref`를 demo fixtures에 실제 존재하는 ID로 맞추거나, `session.merge()`로 부모 row를 먼저 확보해야 한다.

---

### CR-02: `_validate_kpi_keys` 정규식이 `total_power_mW` 같은 실제 KPI 키를 거부한다

**File:** `src/scenario_db/models/evidence/simulation.py:18,74-79`

**Issue:**
```python
_KPI_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
```
이 패턴은 소문자+숫자+밑줄만 허용한다. 그러나 `sim-FHD30-with-breakdown.yaml` fixture와 프로젝트 CLAUDE.md의 명명 규약 `_mW` (대문자 포함)는 이 패턴을 통과하지 못한다.

실제로 `sim-camera-recording-UHD60-A0-sw123.yaml`의 kpi 섹션:
```yaml
kpi:
  total_power_mw: 1200   # 소문자 → PASS
  peak_power_mw:  1400   # 소문자 → PASS
```
그리고 `sim-FHD30-with-breakdown.yaml`도 동일하게 소문자를 사용하므로 현재 fixture는 통과한다.

하지만 CLAUDE.md 코딩 컨벤션은 명시적으로 **`_mW` (대문자 W) 접미사**를 요구한다:
> Naming suffixes: `_ps` (time), `_bytes` (size), `_dva` (address), `_GBps` (bandwidth)

그리고 `PortBWResult.bw_power_mw`, `IPTimingResult.set_voltage_mv` 등 모델 필드 자체가 소문자를 사용한다.

더 심각한 것은 validator 오류 메시지가 `total_power_mW`를 예시로 제시하면서(`f"KPI key must be lowercase snake_case (e.g. total_power_mW)."`) 실제 허용하지 않는 모순이 있다:

```python
raise ValueError(
    f"KPI key must be lowercase snake_case (e.g. total_power_mW). "  # 'mW'는 대문자 포함
    f"Got: '{key}'"
)
```

`total_power_mW`라는 키를 실제로 KPI에 저장하면 ValidationError가 발생한다. 에러 메시지의 예시(`total_power_mW`)가 실제 허용 패턴과 불일치하여 사용자를 잘못 안내한다.

**Fix:**
정규식을 대문자 허용으로 수정하거나, 예시 메시지를 실제 패턴에 맞게 수정하라:
```python
# 옵션 A: 메시지만 수정 (패턴 유지)
raise ValueError(
    f"KPI key must be lowercase snake_case (e.g. total_power_mw). "
    f"Got: '{key}'"
)

# 옵션 B: 실제 도메인 관행 반영 (대문자 단위 접미사 허용)
_KPI_KEY_RE = re.compile(r"^[a-z][a-zA-Z0-9_]*$")
```

---

## Warnings

### WR-01: `PortInputConfig.r_w_rate` — 값 범위 검증 없음

**File:** `src/scenario_db/models/definition/usecase.py:168`

**Issue:**
`r_w_rate: float = 1.0` 는 Read/Write 비율을 나타낸다. 이 값은 물리적으로 0.0 ~ 1.0 범위여야 하지만, 아무런 범위 제약이 없다. 음수나 2.0 같은 값이 검증 없이 저장된다. 동일 모델의 `comp_ratio: float = 1.0`도 마찬가지다(0.0 초과여야 함). 이 값들이 시뮬레이션 엔진에서 대역폭 계산에 직접 사용될 경우 잘못된 결과를 낳는다.

**Fix:**
```python
from pydantic import Field

r_w_rate: float = Field(default=1.0, ge=0.0, le=1.0)
comp_ratio: float = Field(default=1.0, gt=0.0, le=1.0)
comp_ratio_min: float | None = Field(default=None, gt=0.0, le=1.0)
comp_ratio_max: float | None = Field(default=None, gt=0.0, le=1.0)
```
`llc_weight: float = 1.0`도 음수 방지를 위해 `ge=0.0` 추가를 권장한다.

---

### WR-02: `IPSimParams.ppc` — 양수 검증 없음

**File:** `src/scenario_db/models/capability/hw.py:99`

**Issue:**
`ppc: float` (Pixels Per Clock)는 반드시 양수여야 한다. 0 이하 값이 입력되면 시뮬레이터에서 division-by-zero 또는 음수 처리량으로 이어질 수 있다. `unit_power_mw_mp: float`도 동일하게 양수여야 한다.

**Fix:**
```python
from pydantic import Field

ppc: float = Field(gt=0.0)
unit_power_mw_mp: float = Field(ge=0.0)
```

---

### WR-03: `sim-FHD30-with-breakdown.yaml` fixture의 `variant_ref`가 실제 Usecase variants와 불일치

**File:** `tests/unit/fixtures/evidence/sim-FHD30-with-breakdown.yaml:6`

**Issue:**
```yaml
scenario_ref: uc-camera-recording
variant_ref: UHD60-HDR10-H265
```
파일 이름은 `sim-FHD30-...`(FHD30)이지만 `variant_ref`는 `UHD60-HDR10-H265`를 참조한다. 더 심각한 것은 `id: sim-camera-recording-FHD30-A0-sw123`이다. 이 fixture는 FHD30 시나리오를 표방하지만 실제로는 UHD60 variant를 참조하고 있어 fixture 자체의 의미적 일관성이 없다.

테스트 `test_sim_evidence_with_breakdown_roundtrip`는 round-trip만 확인하고 `variant_ref`의 정합성을 확인하지 않으므로 현재 테스트는 통과하지만, 실제 DB에서 `evidence.variant_ref` → `scenario_variants.id` cross-check를 수행하는 쿼리에서 문제가 될 수 있다.

**Fix:**
fixture를 의도에 맞게 수정하라:
```yaml
# 방법 1: FHD30 전용 variant 사용
variant_ref: FHD30-SDR-H264  # uc-camera-recording에 해당 variant 추가 필요

# 방법 2: 파일명과 id를 variant에 맞게 수정
id: sim-camera-recording-UHD60-A0-sw123-with-breakdown
```

---

### WR-04: 통합 테스트 session-scope DB에서 FK 부모 없이 evidence insert 시도

**File:** `tests/integration/test_schema_extensions.py:150-169`

**Issue:**
`test_dma_breakdown_etl_empty_default`에서 fixture의 `id`를 `"sim-evidence-no-breakdown-test"`로 교체하지만 `scenario_ref: uc-camera-recording`과 `sw_baseline_ref: sw-vendor-v1.2.3`는 그대로다. 통합 DB는 demo fixtures로 초기화되는데(`DEMO_FIXTURES`), `uc-camera-recording` scenario와 `sw-vendor-v1.2.3` sw_profile이 demo fixtures에 없다면 FK 제약 위반으로 `session.commit()`이 실패한다.

마찬가지로 `test_sensor_etl_null_backward_compat`(line 105-116)에서 `upsert_usecase`는 `project_ref: proj-A-exynos2500`를 가진 Usecase를 삽입하는데, demo fixtures에 이 project가 없을 경우 동일하게 실패한다.

**Fix:**
통합 테스트의 fixture에서 사용하는 `scenario_ref`, `project_ref`, `sw_baseline_ref`는 반드시 demo fixtures에 실제 존재하는 ID를 사용하거나, 테스트 내에서 부모 row를 먼저 upsert해야 한다:
```python
# 테스트 앞에 부모 row upsert 또는
# fixture id를 demo fixtures의 실제 id로 맞추기
raw["scenario_ref"] = "uc-camera-recording"  # demo에 존재하는지 확인 필요
```

---

## Info

### IN-01: `PortType` StrEnum에 공백 정렬 (코드 스타일 불일치)

**File:** `src/scenario_db/models/capability/hw.py:85-88`

**Issue:**
```python
class PortType(StrEnum):
    DMA_READ  = "DMA_READ"
    DMA_WRITE = "DMA_WRITE"
    OTF_IN    = "OTF_IN"
    OTF_OUT   = "OTF_OUT"
```
값 정렬을 위한 extra space가 사용되었다. 프로젝트 내 다른 StrEnum(`Severity`, `ViolationAction` 등)은 이 스타일을 쓰지 않는다. 일관성 관점에서 맞추는 것이 좋다.

**Fix:** 불필요한 공백 정렬 제거.

---

### IN-02: `IPSimParams.dvfs_group` — `str` 타입으로 선언되었으나 `IPPortConfig`의 DVFS override와 타입 불일치

**File:** `src/scenario_db/models/capability/hw.py:103` / `src/scenario_db/models/definition/usecase.py:184`

**Issue:**
`IPSimParams.dvfs_group: str`은 그룹 이름(예: `"CAM"`, `"INT"`)이고, `SimGlobalConfig.dvfs_overrides: dict[str, int]`는 `{dvfs_group_name: freq_mhz}` 형태의 정수값 매핑이다. `dvfs_group` 필드는 `dvfs_overrides`의 key로 사용되므로 이 관계가 문서화되지 않아 사용 맥락이 불명확하다. 또한 `dvfs_overrides` 값이 클럭 주파수(MHz)라면 `int`보다 명시적 이름인 `freq_mhz`나 타입 앨리어스 사용을 권장한다.

**Fix:**
```python
# SimGlobalConfig
dvfs_overrides: dict[str, int] = Field(
    default_factory=dict,
    description="key=dvfs_group (matches IPSimParams.dvfs_group), value=freq_mhz override",
)
```

---

### IN-03: 단위 테스트에서 `roundtrip()` 헬퍼가 `by_alias` 옵션을 지원하지 않아 `PipelineEdge` alias 테스트에 잠재적 갭 존재

**File:** `tests/unit/test_schema_extensions.py:48-54`

**Issue:**
```python
def roundtrip(model_cls, path: Path, **dump_kwargs):
    raw = load_yaml(path)
    obj = model_cls.model_validate(raw)
    serialised = obj.model_dump(exclude_none=True, **dump_kwargs)
    obj2 = model_cls.model_validate(serialised)
    assert obj == obj2
    return obj
```
`Usecase` round-trip 테스트(`test_usecase_backward_compat_no_sim_config`, `test_usecase_backward_compat_no_sensor`)에서 `by_alias=True`를 넘기지 않는다. `PipelineEdge`는 `from_` 필드를 `"from"` alias로 직렬화해야 하는데, `by_alias=False`로 dump하면 `"from_"` 키로 직렬화된다. 이 `"from_"` 키는 `model_validate` 시 `populate_by_name=True` 덕분에 다시 파싱되므로 round-trip은 통과하지만, ETL(`upsert_usecase` line 32: `by_alias=True`)과 다른 경로를 검증하게 된다.

YAML → DB 직렬화 경로가 round-trip 테스트와 다르게 동작하는 것을 테스트가 커버하지 못한다.

**Fix:**
```python
def test_usecase_backward_compat_no_sensor():
    obj = roundtrip(
        Usecase,
        FIXTURES / "definition" / "uc-camera-recording.yaml",
        by_alias=True,  # ETL 경로와 동일하게
    )
    assert obj.sensor is None
```

---

_Reviewed: 2026-05-10T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
