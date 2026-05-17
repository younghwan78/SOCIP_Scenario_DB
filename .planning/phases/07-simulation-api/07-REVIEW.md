---
phase: 07-simulation-api
reviewed: 2026-05-17T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - alembic/versions/0003_params_hash.py
  - src/scenario_db/api/schemas/simulation.py
  - src/scenario_db/db/repositories/simulation.py
  - src/scenario_db/db/models/evidence.py
  - src/scenario_db/db/loaders.py
  - src/scenario_db/sim/models.py
  - src/scenario_db/sim/runner.py
  - src/scenario_db/api/routers/simulation.py
  - src/scenario_db/api/app.py
  - tests/unit/test_simulation_schemas.py
  - tests/unit/test_loaders.py
  - tests/integration/test_simulation_api.py
findings:
  critical: 3
  warning: 4
  info: 2
  total: 9
status: issues_found
---

# Phase 7: Code Review Report

**Reviewed:** 2026-05-17T00:00:00Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Phase 7 Simulation API 구현을 리뷰했다. 전체 구조(캐싱 플로우, ORM 저장, 분석 엔드포인트 분리)는 설계 의도에 부합하나, 타입 불일치 버그, deprecated API 사용, 런타임 경로 의존성 문제 3개의 BLOCKER가 확인됐다. 추가로 캐시 히트 경로의 silent incorrect behavior, 예외 미처리 등 4개의 WARNING이 존재한다.

---

## Critical Issues

### CR-01: `SimGlobalConfig.dvfs_overrides` 타입 불일치 — `apply_request_overrides` 가 빈 dict를 None으로 변환하지 못해 타입 오염

**File:** `src/scenario_db/db/loaders.py:90-93`

**Issue:**
`SimGlobalConfig.dvfs_overrides`는 `dict[str, int]`(non-optional, 기본값 `{}`)로 선언되어 있다. 반면 `SimulateRequest.dvfs_overrides`는 `dict[str, int] | None`이다.

`apply_request_overrides`는 `req.dvfs_overrides is not None`일 때만 덮어쓰므로, req가 `dvfs_overrides=None`을 보내면 DB에서 가져온 `sim_config.dvfs_overrides`(빈 dict `{}`)가 유지된다. 그런데 `runner.py:67`에서는:

```python
dvfs_overrides=sim_config.dvfs_overrides or None,
```

빈 dict `{}`는 falsy이므로 `None`으로 변환된다. 이것은 의도적이나, `apply_request_overrides`가 `req.dvfs_overrides={"cam": 3}`과 같은 값으로 overridden된 경우에도 같은 `or None` 변환이 적용되어, `{"cam": 3}` 처럼 비어있지 않은 dict는 정상 전달된다. 단, `SimGlobalConfig.dvfs_overrides`를 `dict[str, int]`에서 `dict[str, int] | None`으로 바꾸지 않는 이상 `model_validate(overridden)` 시 `None`을 넣으면 Pydantic ValidationError가 발생한다.

더 심각한 문제: `apply_request_overrides`에서 `overridden["dvfs_overrides"] = req.dvfs_overrides`는 `dict[str, int] | None` 값을 `SimGlobalConfig`(필드 타입 `dict[str, int]`)에 넣는다. `req.dvfs_overrides`가 `None`이 아닐 때는 dict이므로 괜찮지만, 런타임에서 이 경로가 성립하려면 Pydantic이 `None`을 `dict[str, int]`로 coerce 하는데, `extra='forbid'`/strict 설정에 따라 silent corruption 또는 ValidationError로 이어질 수 있다.

**Fix:**
`SimGlobalConfig`의 `dvfs_overrides`를 `dict[str, int] | None`으로 통일하거나, `apply_request_overrides`에서 `None` guard를 명시:

```python
# loaders.py apply_request_overrides
if req.dvfs_overrides is not None:
    overridden["dvfs_overrides"] = req.dvfs_overrides
# dvfs_overrides=None인 요청이 들어오면 기존 {} 유지 — 명시적 의도 주석 추가
```

그리고 `SimGlobalConfig` 정의를:
```python
dvfs_overrides: dict[str, int] | None = None
```
으로 통일하고 `runner.py:67`의 `or None` 변환을 제거한다.

---

### CR-02: `DVFS_CONFIG_PATH`가 상대경로 — 프로세스 CWD 의존으로 프로덕션/테스트 환경에서 FileNotFoundError

**File:** `src/scenario_db/config.py:33` / `src/scenario_db/db/loaders.py:45`

**Issue:**
```python
DVFS_CONFIG_PATH: Path = Path("hw_config/dvfs-projectA.yaml")
```

이 경로는 `Path.cwd()`를 기준으로 해석된다. FastAPI 앱을 `uvicorn` 으로 기동하는 위치나 pytest 실행 디렉터리가 달라지면 파일을 찾지 못해 `FileNotFoundError`가 발생한다. 통합 테스트에서 `load_runner_inputs_from_db`를 monkeypatch하지 않는 경우(예: `test_run_invalid_scenario` — monkeypatch 없이 실제 `load_runner_inputs_from_db` 호출 직전에 `None` 반환을 가정하지만 내부에서 `_load_dvfs_tables()`를 먼저 호출하지 않으므로 이 경우는 OK), 또는 향후 monkeypatch 범위가 좁아지면 silent 장애가 된다.

특히 `_load_dvfs_tables()`에 예외 처리가 없어서 YAML 파일 없음 시 스택 트레이스가 그대로 노출된다.

**Fix:**
```python
# config.py
DVFS_CONFIG_PATH: Path = Path(__file__).parent.parent.parent.parent / "hw_config" / "dvfs-projectA.yaml"
# 또는 환경변수로 override 가능하게 Settings에 포함:
# dvfs_config_path: Path = Field(default=..., validation_alias="DVFS_CONFIG_PATH")
```

그리고 `_load_dvfs_tables()`에 `FileNotFoundError` 처리:
```python
try:
    with open(DVFS_CONFIG_PATH, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
except FileNotFoundError as e:
    raise RuntimeError(
        f"DVFS config not found: {DVFS_CONFIG_PATH}. "
        f"Set DVFS_CONFIG_PATH env or verify hw_config/ directory."
    ) from e
```

---

### CR-03: `datetime.utcnow()` — Python 3.12에서 deprecated, 향후 제거 예정

**File:** `src/scenario_db/db/repositories/simulation.py:44`

**Issue:**
```python
"timestamp": datetime.utcnow().isoformat(),
```

`datetime.utcnow()`는 Python 3.12에서 deprecation warning이 추가됐고 향후 버전에서 제거 예정이다. 반환값이 naive datetime(timezone 정보 없음)이므로 DB/API 소비자가 UTC와 로컬 시간을 혼동할 수 있다. CLAUDE.md 프로젝트 규칙은 "timestamps in absolute nanoseconds (ns)" 또는 명시적 timezone 사용을 요구한다.

**Fix:**
```python
from datetime import datetime, timezone

"timestamp": datetime.now(tz=timezone.utc).isoformat(),
```

---

## Warnings

### WR-01: 캐시 HIT 경로에서 `kpi["feasible"]` 타입 복원 오류 — `int(1)`이 `True`로 올바르게 변환되나 `0`이 아닌 다른 정수 저장 시 silently incorrect

**File:** `src/scenario_db/api/routers/simulation.py:63` / `src/scenario_db/db/repositories/simulation.py:41`

**Issue:**
저장 시 `"feasible": int(result.feasible)` — 즉 0 또는 1. 캐시 HIT 응답 시:

```python
feasible=bool(kpi.get("feasible", 0)),
```

`bool(1)=True`, `bool(0)=False`로 정상 동작하나, JSONB에서 읽힌 값이 실제로 boolean(`True`/`False`)으로 저장된 경우(PostgreSQL은 Python `int`를 JSONB integer로, `bool`을 JSONB boolean으로 다르게 저장할 수 있음) `bool(True)=True`, `bool(False)=False`로 여전히 작동한다. 그러나 SQLite의 경우 JSONB 대신 JSON 텍스트로 저장되면 `"true"` 문자열이 반환될 수 있어 `bool("true") == True` (nonempty string은 truthy)이지만 `bool("false") == True`로 silently incorrect가 된다.

타이밍 분석 응답(라인 220)도 동일 패턴:
```python
feasible=bool(kpi.get("feasible", 0)),
```

**Fix:**
저장 시 `int()` 변환하지 말고 JSON-serializable `bool`을 직접 사용:
```python
"feasible": result.feasible,   # bool — JSONB에 boolean으로 저장
```
읽을 때:
```python
feasible=bool(kpi.get("feasible", False)),
```

---

### WR-02: `find_by_params_hash` 정렬 기준 — `Evidence.id`는 lexicographic 정렬이며 UUID hex는 시간 순서를 보장하지 않음

**File:** `src/scenario_db/db/repositories/simulation.py:69-76`

**Issue:**
```python
.order_by(Evidence.id.desc())
```

`evidence_id`는 `f"evd-sim-{uuid4().hex[:8]}"` 형식이다. `uuid4()`는 완전히 랜덤이므로 hex prefix 기준 내림차순 정렬은 "가장 최근 생성"을 보장하지 않는다. 동일 `params_hash`의 여러 행 중 실제 최신 항목이 아닌 임의의 항목이 반환될 수 있다.

**Fix:**
`Evidence` ORM 모델에 `created_at` 타임스탬프 컬럼을 추가하고 해당 컬럼 기준 내림차순 정렬을 사용하거나, 또는 `run_info->>'timestamp'` JSONB 경로로 정렬:
```python
from sqlalchemy import desc, cast, Text
.order_by(Evidence.run_info["timestamp"].astext.desc())
```
근본 해결책은 `created_at = Column(DateTime(timezone=True), server_default=func.now())` 컬럼 추가다.

---

### WR-03: `run_sim` 라우터가 `run_simulation()` 예외를 전혀 잡지 않음 — 500 Internal Server Error로 노출

**File:** `src/scenario_db/api/routers/simulation.py:83-93`

**Issue:**
```python
result = run_simulation(
    scenario_id=req.scenario_id,
    ...
)
```

`run_simulation()`은 순수 계산 함수지만 내부에서 `calc_port_bw`, `calc_active_power`, `DvfsResolver.resolve` 등을 호출한다. 이들에서 예상치 못한 예외(예: `ZeroDivisionError`, `KeyError`)가 발생하면 FastAPI가 500을 반환하고 스택 트레이스가 로그에 노출된다. DB에 저장(`save_sim_evidence`)이 이루어지지 않으므로 상태 불일치는 없지만, 클라이언트에 유의미한 오류 메시지 대신 500이 반환된다.

**Fix:**
```python
try:
    result = run_simulation(...)
except Exception as exc:
    logger.exception("run_simulation failed for scenario=%s variant=%s", req.scenario_id, req.variant_id)
    raise HTTPException(
        status_code=422,
        detail=f"Simulation failed: {exc}",
    ) from exc
```

---

### WR-04: `get_bw_analysis` / `get_power_analysis` / `get_timing_analysis` — `evidence.kind` 검증 없음, 측정(measurement) Evidence도 조회 가능

**File:** `src/scenario_db/api/routers/simulation.py:148-161`, `175-194`, `207-224`

**Issue:**
세 분석 엔드포인트는 `get_evidence(db, evidence_id)`로 임의의 Evidence row를 조회한다. `evidence.measurement` 타입의 evidence는 `dma_breakdown`, `timing_breakdown`, `ip_breakdown` 필드가 없거나 다른 구조를 가질 수 있다. 현재 코드는 `or []` / `or {}` 폴백으로 빈 응답을 반환하여 오류 없이 misleading 결과를 반환한다.

**Fix:**
```python
if row.kind != "evidence.simulation":
    raise HTTPException(
        status_code=422,
        detail=f"evidence '{evidence_id}' is kind='{row.kind}', expected 'evidence.simulation'",
    )
```

---

## Info

### IN-01: `alembic/versions/0003_params_hash.py` — `params_hash` 컬럼에 index가 없음

**File:** `alembic/versions/0003_params_hash.py:22-25`

**Issue:**
`find_by_params_hash()`는 `Evidence.params_hash == params_hash` 조건으로 쿼리한다. Evidence 행이 많아지면 full table scan이 발생한다. ORM 모델(`evidence.py:47`)도 `index=True` 없이 선언되어 있다.

**Fix:**
```python
# 0003_params_hash.py upgrade()에 추가
op.create_index("ix_evidence_params_hash", "evidence", ["params_hash"])
```
그리고 `downgrade()`에도:
```python
op.drop_index("ix_evidence_params_hash", table_name="evidence")
```

---

### IN-02: 통합 테스트 `test_run_invalid_scenario` — monkeypatch 없이 실제 DB 접근, 테스트 의존성 숨김

**File:** `tests/integration/test_simulation_api.py:343-351`

**Issue:**
```python
def test_run_invalid_scenario(api_client: TestClient):
    payload = {
        "scenario_id": "no-such-scenario-xyz",
        "variant_id": "no-such-variant-xyz",
        "fps": 30.0,
    }
    resp = api_client.post(f"{BASE_URL}/run", json=payload)
    assert resp.status_code == 404
```

이 테스트는 monkeypatch 없이 실제 `load_runner_inputs_from_db()`를 호출한다. 내부에서 `_load_dvfs_tables()`가 호출되지 않는 것은 Scenario 조회 실패 후 바로 `None` 반환하기 때문에 우연히 DVFS 파일 문제를 회피한다. 하지만 테스트 주석이나 픽스처에 이 의존성이 명시되지 않아 추후 `load_runner_inputs_from_db` 시그니처 변경 시 테스트 의도가 불분명해진다.

**Fix:**
테스트 docstring에 "monkeypatch 없음 — load_runner_inputs_from_db가 DB에서 scenario를 찾지 못하고 None 반환하는 경로를 실제 검증"이라고 명시하거나, 다른 테스트와 일관되게 monkeypatch를 추가한다.

---

_Reviewed: 2026-05-17T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
