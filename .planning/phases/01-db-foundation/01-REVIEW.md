---
phase: 01-db-foundation
reviewed: 2026-05-07T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - src/scenario_db/etl/validate_loaded.py
  - src/scenario_db/etl/loader.py
  - src/scenario_db/db/repositories/scenario_graph.py
  - src/scenario_db/db/repositories/view_projection.py
  - src/scenario_db/view/service.py
  - demo/fixtures/02_definition/uc-camera-recording.yaml
  - tests/unit/test_validate_loaded.py
  - tests/integration/test_validate_loaded.py
  - tests/unit/test_scenario_graph_models.py
  - tests/integration/test_scenario_graph.py
  - tests/integration/test_view_projection.py
findings:
  critical: 2
  warning: 5
  info: 3
  total: 10
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-05-07
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Phase 1 DB Foundation 구현체를 리뷰했다. ETL loader, validate_loaded, scenario_graph repository, view_projection repository, view service가 검토 범위다.

전반적인 구조는 4-Layer 설계 원칙을 따르고 있으며 ORM 오염(`_sa_instance_state`) 방지, SAVEPOINT per-file, 수동 다중 쿼리 N+1 방지 전략은 올바르게 적용되었다.

**핵심 결함 2건:** Pydantic v2 가변 기본값 공유 버그(`ValidationReport`), YAML fixture와 코드 사이의 `profile_constraints` 스키마 불일치로 인한 SW profile 조회 완전 실패. 모두 런타임에서 조용히 잘못된 결과를 반환한다.

---

## Critical Issues

### CR-01: ValidationReport 가변 기본값 공유 — Pydantic v2 클래스 변수 공유 버그

**File:** `src/scenario_db/etl/validate_loaded.py:24-25`

**Issue:**
`ValidationReport` 모델에서 `errors`와 `warnings` 필드의 기본값이 bare mutable list (`[]`)로 선언되어 있다.

```python
class ValidationReport(BaseModel):
    errors: list[str] = []
    warnings: list[str] = []
```

Pydantic v2는 list/dict 기본값을 자동으로 `default_factory`로 변환하기 때문에 Pydantic 자체는 인스턴스 간 공유를 막는다. **그러나** 이 선언 방식은 테스트 코드에서 동일한 `ValidationReport` 인스턴스를 재사용하거나, 반환된 report 객체의 리스트를 외부에서 mutate할 경우 (`report.errors.append(...)`) 후속 호출 간 상태 오염이 발생하는 패턴을 유도한다. 더 심각한 점은, `validate_loaded()` 함수 내부(line 55-56)에서도 동일하게 `errors: list[str] = []` 로컬 리스트를 생성하여 `ValidationReport(errors=errors, warnings=warnings)` 로 전달하는데, Pydantic이 해당 list를 그대로 참조로 저장하므로 caller가 `errors` 변수를 계속 수정하면 이미 반환된 `report.errors`도 변경된다.

실제 버그 시나리오: `validate_loaded()` 호출자가 반환된 `report`를 캐싱하고 이후에 `errors` list를 참조하는 경우, 동일 session 재사용 패턴에서 stale 데이터를 볼 수 있다.

**Fix:**
```python
from pydantic import Field

class ValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
```

`validate_loaded()` 내부에서 `ValidationReport` 생성 시에는 복사본을 전달해야 한다:
```python
return ValidationReport(errors=list(errors), warnings=list(warnings))
```

---

### CR-02: `sw_profiles` 조회 로직이 실제 YAML fixture 스키마와 불일치 — 항상 빈 dict 반환

**File:** `src/scenario_db/db/repositories/scenario_graph.py:294-300`

**Issue:**
`get_canonical_graph()`에서 `SwProfile` 조회를 위해 `variant.sw_requirements`에서 `profile_constraints[*].profile_ref`를 추출하는 코드가 있다:

```python
sw_req = variant.sw_requirements or {}
sw_profile_refs: set[str] = set()
for item in sw_req.get("profile_constraints", []) if isinstance(sw_req, dict) else []:
    if isinstance(item, dict) and "profile_ref" in item:
        sw_profile_refs.add(item["profile_ref"])
```

그런데 실제 YAML fixture(`demo/fixtures/02_definition/uc-camera-recording.yaml`, line 62)와 Pydantic 모델(`src/scenario_db/models/definition/usecase.py`, line 97-99)의 `ProfileConstraints` 구조를 보면:

```yaml
sw_requirements:
  profile_constraints:
    min_version: "v1.2.0"   # ← dict, not list
```

`ProfileConstraints`는 `{min_version: str, baseline_family: list[str]}` **단일 dict** 이지, `list[{profile_ref: str}]` 형태가 아니다. 코드는 `profile_constraints`가 `list[{profile_ref: str}]`라고 가정하지만 실제 DB에는 `{"min_version": "v1.2.0"}` dict가 저장된다.

`sw_req.get("profile_constraints", [])` 결과가 list가 아닌 dict이므로 iteration 시 key 문자열(`"min_version"`)이 나오고, `isinstance(item, dict)` 조건에서 False가 되어 `sw_profile_refs`는 항상 비어있다. 결과적으로 `CanonicalScenarioGraph.sw_profiles`는 어떤 시나리오에서도 항상 `{}`를 반환한다. 이는 silent wrong result이며 assertion으로 잡히지 않는다.

**Fix:**
`profile_constraints`가 dict 형태(`ProfileConstraints`)임을 반영하여 조회 방식을 수정해야 한다. 실제 profile_ref를 sw_requirements에서 추출하는 경로가 존재하지 않는다면, `sw_baseline_ref`(Evidence 레벨)를 사용하거나 `SwRequirements.profile_constraints.baseline_family`에서 참조를 구성해야 한다. 우선 당면한 버그 수정:

```python
sw_req = variant.sw_requirements or {}
sw_profile_refs: set[str] = set()
if isinstance(sw_req, dict):
    pc = sw_req.get("profile_constraints")
    # ProfileConstraints는 단일 dict: {min_version, baseline_family}
    # baseline_family에서 profile ref를 수집하거나,
    # 상위 스키마에서 실제 profile_ref 경로를 확인 후 반영해야 한다.
    if isinstance(pc, dict):
        for ref in pc.get("baseline_family", []):
            sw_profile_refs.add(ref)
```

단, 이 수정도 실제 스키마 설계 의도에 따라 달라질 수 있다. **`profile_ref` 필드가 어디에도 존재하지 않으므로**, sw_profiles 조회 로직 자체를 재설계해야 한다. 이 버그가 방치되면 Phase 2~4 파이프라인에서 SW profile 기반 분석이 항상 빈 결과를 사용하게 된다.

---

## Warnings

### WR-01: loader.py — 동일 파일 이중 읽기 (TOCTOU + 불필요한 I/O)

**File:** `src/scenario_db/etl/loader.py:72-78`

**Issue:**
파일 발견 루프에서 동일 파일을 두 번 읽는다:

```python
raw = yaml.safe_load(path.read_text(encoding="utf-8"))  # 1차 읽기
# ...
sha256 = hashlib.sha256(path.read_bytes()).hexdigest()   # 2차 읽기
```

두 읽기 사이에 파일 내용이 변경되면 `sha256`이 `raw`와 다른 파일 내용을 기반으로 계산된다. 이는 TOCTOU(Time-of-Check-to-Time-of-Use) 조건이다. 개발 환경에서 fixtures를 수정하면서 ETL을 실행하는 경우 sha256과 실제 로드된 내용이 불일치할 수 있다.

**Fix:**
`read_bytes()`를 먼저 수행하고 동일 bytes를 재사용한다:
```python
raw_bytes = path.read_bytes()
sha256 = hashlib.sha256(raw_bytes).hexdigest()
raw = yaml.safe_load(raw_bytes.decode("utf-8"))
```

---

### WR-02: loader.py — validation 오류를 WARNING 레벨로만 로깅, caller에게 전달 안 됨

**File:** `src/scenario_db/etl/loader.py:101-108`

**Issue:**
`load_yaml_dir()` 내부에서 `validate_loaded()` 호출 후 validation 오류가 발견되어도 `logger.warning()`만 기록하고 `_report`는 함수 반환값에 포함되지 않으며 caller가 오류 여부를 알 수 없다:

```python
_report = validate_loaded(session)
if _report.errors:
    for _err in _report.errors:
        logger.warning("Validation: %s", _err)
# ...
return counts  # ValidationReport는 반환 안 됨
```

`main()` CLI나 `load_yaml_dir()`를 호출하는 API endpoint에서 validation 실패를 자동으로 탐지할 수 없다. 특히 `commit()` 이후 validation 오류 발견 시 이미 DB에 부정합 데이터가 있는 상태임에도 호출자는 성공으로 간주한다.

**Fix:**
반환 타입을 확장하거나 별도 반환으로 report를 노출한다:
```python
# 옵션 A: 튜플 반환 (하위 호환성 깨짐)
def load_yaml_dir(...) -> tuple[dict[str, int], ValidationReport]:
    ...
    return counts, _report

# 옵션 B: report를 counts dict에 side-band으로 포함 (비권장)
# 옵션 C: validation 오류 발생 시 RuntimeError raise
if _report.errors:
    raise RuntimeError(f"Post-load validation failed: {_report.errors}")
```

---

### WR-03: view/service.py — `project_level0()` DB path에서 샘플 데이터를 ID만 교체하여 반환

**File:** `src/scenario_db/view/service.py:251-254`

**Issue:**
`project_level0()` 함수에서 `db`가 주어진 경우 DB projection을 수행한다고 문서화되어 있지만, 실제로는 샘플 하드코딩 데이터를 가져온 후 `scenario_id`와 `variant_id`만 교체하여 반환한다:

```python
response = build_sample_level0()
return ViewResponse(
    **{**response.model_dump(), "scenario_id": scenario_id, "variant_id": variant_id},
)
```

이 함수는 FastAPI router에서 실제 DB 연동 경로로 호출된다. DB에 실제 데이터가 있더라도 항상 하드코딩된 `uc-camera-recording`의 노드/엣지 구조를 반환하므로, 다른 scenario_id를 요청해도 동일한 잘못된 그래프를 반환한다. Phase 4 구현 전까지 의도된 stub이지만 함수 signature와 문서가 실제 DB 연동처럼 보이게 되어 있어 API 호출자를 오해시킨다.

**Fix:**
Phase 4 전까지 명시적으로 NotImplementedError를 raise하거나, 반환 데이터가 샘플임을 응답에 포함시켜야 한다:
```python
def project_level0(scenario_id: str, variant_id: str, db=None) -> ViewResponse:
    if db is None:
        return build_sample_level0()
    # Phase 4 (VIEW-01) 미구현 — DB projection 불완전
    # NOTE: 아래 응답은 실제 DB 데이터가 아닌 샘플 레이아웃을 ID만 교체한 것
    raise NotImplementedError(
        "DB-backed Level 0 projection is Phase 4 (VIEW-01) work. "
        "Pass db=None for demo mode."
    )
```

---

### WR-04: scenario_graph.py — `_issue_affects_scenario()` 함수 중복 정의

**File:** `src/scenario_db/db/repositories/scenario_graph.py:205-215` 및 `src/scenario_db/etl/validate_loaded.py:33-40`

**Issue:**
`_issue_affects_scenario()` 함수가 두 파일에 완전히 동일한 로직으로 중복 정의되어 있다. 동작 차이도 없고, 함수 docstring의 일부 설명만 다르다. 향후 Issue.affects 구조가 변경될 때 두 군데를 동시에 수정해야 하며, 한쪽만 수정될 경우 버그 divergence가 발생한다.

**Fix:**
공유 유틸리티 모듈에 단일 정의를 두고 양쪽에서 import한다:
```python
# src/scenario_db/db/utils.py (신규)
def issue_affects_scenario(affects: list[dict] | None, scenario_id: str) -> bool:
    ...
```

---

### WR-05: validate_loaded.py Rule 3 — evidence.variant_ref가 None일 때 KeyError 가능

**File:** `src/scenario_db/etl/validate_loaded.py:85-96`

**Issue:**
Rule 3 검증에서 `ev_variant_ref`를 사용하여 `variant_keys` set 조회를 수행한다:

```python
elif (ev_scenario_ref, ev_variant_ref) not in variant_keys:
    errors.append(...)
```

`Evidence.variant_ref` 컬럼은 DB 모델(`evidence.py:32`)에서 `nullable=False`로 정의되어 있지만, ETL 과정에서 직접 INSERT된 데이터나 migration 이후 기존 데이터에서 `variant_ref`가 `None`인 경우 `(ev_scenario_ref, None)`으로 조회가 수행된다. 이 경우 `variant_keys`에 `(str, None)` 쌍이 존재하지 않으므로 오류 메시지를 출력하는 것은 맞지만, 이후 로직에서 `None`을 문자열처럼 다루는 코드가 있다면 TypeError가 발생할 수 있다. 또한 Rule 4의 `rev_variant_ref`에서도 동일한 패턴이 반복된다(line 114).

**Fix:**
None 체크를 추가하여 명확한 오류 메시지를 출력한다:
```python
if ev_variant_ref is None:
    errors.append(
        f"evidence '{ev_id}': variant_ref is None (nullable=False 위반)"
    )
elif (ev_scenario_ref, ev_variant_ref) not in variant_keys:
    errors.append(...)
```

---

## Info

### IN-01: loader.py — `MAPPER_REGISTRY` 타입 힌트에 `callable` (소문자) 사용

**File:** `src/scenario_db/etl/loader.py:30`

**Issue:**
```python
MAPPER_REGISTRY: dict[str, callable] = {
```

`callable`은 Python 타입 시스템에서 실제 타입이 아니라 built-in 함수이다. 타입 힌트로 사용하면 mypy/pyright에서 경고가 발생한다. 올바른 타입은 `Callable[..., None]`이다.

**Fix:**
```python
from collections.abc import Callable
MAPPER_REGISTRY: dict[str, Callable[..., None]] = {
```

---

### IN-02: uc-camera-recording.yaml — `FHD30-SDR-H265` variant의 `design_conditions.resolution` 값 불일치

**File:** `demo/fixtures/02_definition/uc-camera-recording.yaml:119-120`

**Issue:**
`FHD30-SDR-H265` variant의 `design_conditions`에서:
```yaml
design_conditions:
  resolution: "1920x1080"   # ← raw string
```
그런데 상위 `design_axes`에서 resolution enum은 `[FHD, UHD, 8K]`로 정의되어 있어 `"1920x1080"` 문자열이 유효한 enum 값이 아니다. 다른 variant들은 `resolution: UHD`, `resolution: 8K` 처럼 enum 키를 사용한다. Pydantic 모델이 `design_conditions`를 `dict` 타입으로 저장하므로 현재는 오류가 나지 않지만, 향후 Phase 3에서 design_conditions 값 검증이 추가되면 이 fixture가 실패하게 된다.

**Fix:**
```yaml
design_conditions:
  resolution: FHD    # enum 키 사용
  fps: 30
  codec: H265
  hdr: SDR           # 또는 color_format 제거하고 hdr enum 사용
```

---

### IN-03: test_scenario_graph_models.py — `test_canonical_graph_construct` 에서 `project=None` 명시 불필요

**File:** `tests/unit/test_scenario_graph_models.py:62`

**Issue:**
`CanonicalScenarioGraph`의 `project` 필드는 `ProjectRecord | None = None`으로 기본값이 `None`이다. 테스트에서 `project=None`을 명시적으로 전달하는 것은 기능적으로 무해하나, 기본값이 있는 필드를 명시적으로 None으로 전달하는 것은 테스트 의도를 모호하게 한다 ("의도적으로 None 테스트" vs "그냥 기본값"). project가 None인 경우의 동작을 검증하려는 것이라면 별도 테스트로 분리하는 것이 명확하다.

**Fix:** 기본값 검증이 목적이면 해당 인수를 생략하거나, None 처리를 검증하는 별도 테스트를 작성한다.

---

_Reviewed: 2026-05-07_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
