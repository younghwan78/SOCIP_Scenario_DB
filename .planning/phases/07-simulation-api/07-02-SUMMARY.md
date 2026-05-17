---
phase: 7
plan: "07-02"
subsystem: simulation-api
tags: [simulation, orm-mapping, runner, loaders, tdd]
dependency_graph:
  requires:
    - "06-03 — run_simulation() 시그니처, SimRunResult, DvfsResolver"
    - "05-02 — SimGlobalConfig, IPPortConfig, SensorSpec, Pipeline ORM 컬럼"
    - "07-01 — SimulateRequest 스키마 (Wave 1 병렬, api/schemas/simulation.py)"
  provides:
    - "SimRunResult.ip_power 필드 (D-06)"
    - "load_runner_inputs_from_db() — ORM → runner 입력 6-튜플 변환 (D-07)"
    - "compute_params_hash() — SHA256 결정론적 해시 (D-02)"
    - "apply_request_overrides() — DB sim_config + request 오버라이드 (D-03)"
  affects:
    - "07-03 — simulation.py 라우터가 load_runner_inputs_from_db(), compute_params_hash() 직접 소비"
tech_stack:
  added:
    - "hashlib.sha256 — compute_params_hash"
    - "yaml.safe_load — DVFS YAML 로드 (_load_dvfs_tables)"
    - "unittest.mock.MagicMock — DB layer 단위 테스트 격리"
  patterns:
    - "IpCatalog.model_validate(row, from_attributes=True) — ORM→Pydantic 변환"
    - "SimGlobalConfig.model_dump() + model_validate() — immutable override 패턴"
    - "TYPE_CHECKING guard로 순환 import 방지 (SimulateRequest)"
key_files:
  created:
    - "src/scenario_db/db/loaders.py"
    - "tests/unit/test_loaders.py"
  modified:
    - "src/scenario_db/sim/models.py — SimRunResult.ip_power 필드 추가"
    - "src/scenario_db/sim/runner.py — Step 5 ip_power 수집 + 두 return 경로 갱신"
decisions:
  - "DVFS YAML 구조가 dvfs_domains 리스트가 아닌 dvfs_tables 딕셔너리임을 실제 파일 확인 후 _load_dvfs_tables() 구현 수정"
  - "07-01(Wave 1 병렬)이 api/schemas/simulation.py를 이미 생성하여 TYPE_CHECKING 없이 직접 import 가능"
  - "ip_name 변수가 runner.py Step 5에 없어서 vdd_power 집계 후 별도 라인으로 추가"
metrics:
  duration: "~15분"
  completed: "2026-05-17"
  tasks_completed: 2
  files_created: 2
  files_modified: 2
  tests_added: 13
  tests_total_passing: 454
---

# Phase 7 Plan 02: runner 확장 + ORM 변환 레이어 Summary

**One-liner:** SimRunResult에 ip_power dict 추가 및 IP별 active power 수집, DB ORM → run_simulation() 6-튜플 변환 레이어(loaders.py) 구현 — SHA256 결정론적 캐시 키 포함.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | SimRunResult.ip_power + runner Step 5 | b767f49 | sim/models.py, sim/runner.py |
| 2 (RED) | test_loaders.py TDD RED | aef810f | tests/unit/test_loaders.py |
| 2 (GREEN) | db/loaders.py 구현 | 2cc8245 | src/scenario_db/db/loaders.py |

---

## Implementation Details

### Task 1: SimRunResult.ip_power 필드 + runner.py Step 5

**models.py** — `SimRunResult` 마지막에 필드 추가:
```python
ip_power: dict[str, float] = Field(default_factory=dict)  # ip_name -> active_power_mw
```

**runner.py Step 5** 변경 사항:
- `ip_power: dict[str, float] = {}` 선언 (vdd_power 선언 바로 아래)
- Step 5 루프 내 `vdd_power` 집계 직후 `_resolve_ip_name()` 호출 + `ip_power[ip_name]` 누적
- 두 개의 `SimRunResult(...)` return 모두에 `ip_power=ip_power` 인수 추가

**주의:** Step 4 루프에는 `ip_name` 변수가 있지만 Step 5 루프에는 없었으므로 별도 라인 추가.

### Task 2: db/loaders.py

**_load_dvfs_tables():**
- 실제 YAML 구조 확인: `dvfs_tables: {CAM: [...], INT: [...], MIF: [...]}`
- Plan 인터페이스 문서의 `dvfs_domains` 리스트 구조와 다름 → 실제 파일 기준으로 구현

**compute_params_hash(req):**
- `json.dumps(..., sort_keys=True)` → `hashlib.sha256().hexdigest()`
- 포함 필드: scenario_id, variant_id, fps, dvfs_overrides, asv_group

**apply_request_overrides(sim_config, req):**
- `model_dump()` + 수정 + `model_validate()` 패턴으로 불변성 보장
- `dvfs_overrides=None`이면 DB 값 유지 (조건부 교체)

**load_runner_inputs_from_db(db, scenario_id, variant_id):**
- 6-튜플: `(pipeline, ip_catalog, dvfs_tables, variant_port_config, sim_config, sensor_spec)`
- scenario/variant 없으면 `None` 반환 (logger.warning 포함)
- ip_catalog 조회: pipeline.nodes의 ip_ref 집합으로 배치 쿼리
- `IpCatalog.model_validate(row, from_attributes=True)` 패턴 사용

---

## Verification Results

```
tests/sim/          41/41 passed (회귀 없음)
tests/unit/test_loaders.py  13/13 passed (GREEN)
tests/unit/        392/392 passed
```

전체 테스트: 454개 통과 (기존 + 13개 신규)

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] DVFS YAML 구조 불일치 수정**
- **Found during:** Task 2 (_load_dvfs_tables 구현)
- **Issue:** Plan 인터페이스 문서에서 `dvfs_domains: [{domain: ..., levels: [...]}]` 리스트 구조로 기술했으나, 실제 `hw_config/dvfs-projectA.yaml`은 `dvfs_tables: {CAM: [...], INT: [...]}` 딕셔너리 구조
- **Fix:** `raw.get("dvfs_tables", {}).items()` 로 도메인/레벨 리스트 파싱하도록 구현
- **Files modified:** src/scenario_db/db/loaders.py
- **Commit:** 2cc8245

**2. [Rule 2 - Info] ip_name 변수 Step 5 추가**
- **Found during:** Task 1 (runner.py 실제 코드 확인)
- **Issue:** Plan에서 `ip_name`이 Step 5에 이미 있다고 가정했으나 실제 Step 5 루프에는 없음 (Step 4에만 존재)
- **Fix:** `vdd_power` 집계 직후 `ip_name = _resolve_ip_name(node.ip_ref, ip_catalog)` 라인 추가
- **Files modified:** src/scenario_db/sim/runner.py
- **Commit:** b767f49

---

## Known Stubs

없음. 모든 함수가 완전히 구현되어 있고 stub/placeholder 없음.

---

## Threat Surface Scan

| Flag | File | Description |
|------|------|-------------|
| 없음 | — | 신규 네트워크 엔드포인트 없음. loaders.py는 SQLAlchemy parameterized query 사용으로 SQL injection 차단 (T-07-04 mitigate 충족). DVFS YAML은 파일시스템 접근만 (T-07-06 accept). |

---

## Self-Check: PASSED

- src/scenario_db/db/loaders.py: 존재 확인
- src/scenario_db/sim/models.py: ip_power 필드 확인
- src/scenario_db/sim/runner.py: ip_power 수집 확인
- tests/unit/test_loaders.py: 13개 테스트 확인
- commits b767f49, aef810f, 2cc8245: git log 확인
