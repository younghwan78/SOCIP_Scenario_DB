# Phase 6: sim/ Package — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-11
**Phase:** 06-sim-package
**Areas discussed:** sim/models.py 범위, DVFS YAML 로딩 전략, scenario_adapter.py 입력 계약, 테스트 픽스처 전략

---

## 1. sim/models.py 범위 (모델 중복 방지)

### 1a. PortBWResult/IPTimingResult 중복 처리

| Option | Description | Selected |
|--------|-------------|----------|
| evidence re-import | PortBWResult/IPTimingResult를 sim/에서 재정의 없이 evidence.simulation에서 import | ✓ |
| sim/ 자체 모델 정의 | sim/models.py에 PortBWResult/IPTimingResult를 다시 정의. sim/이 evidence레이어에 의존하지 않아 독립적 | |

**User's choice:** evidence re-import (Recommended)
**Notes:** 단일 정의 원칙. Phase 7에서 타입 불일치 방지.

### 1b. bw_calc 입력 모델

| Option | Description | Selected |
|--------|-------------|----------|
| PortInputConfig 직접 사용 | bw_calc.calc_port_bw(port: PortInputConfig, fps, ...) — usecase레이어 모델을 그대로 받음 | ✓ |
| sim/내부 PortBWInput 종류 | sim/models.py에 bw_calc 전용 입력 모델 신규 정의. 시그니처 명확하지만 usecase 모델에 의존하지 않음 | |

**User's choice:** PortInputConfig 직접 사용 (Recommended)
**Notes:** sim/ 내부 별도 입력 모델 추가 없음.

---

## 2. DVFS YAML 로딩 전략

### 2a. DVFS 파일 경로 설정

| Option | Description | Selected |
|--------|-------------|----------|
| config.py 상수화 | config.py에 DVFS_CONFIG_PATH = Path('hw_config/dvfs-projectA.yaml') 추가. DvfsResolver 생성 시 자동 로드 | ✓ |
| 런타임 파라미터 | DvfsResolver.__init__(dvfs_tables) 시그니처로만 전달 — yaml 로드는 호출자 책임 | |

**User's choice:** config.py 상수화 (Recommended)
**Notes:** runner.py가 config에서 경로 읽어 로드.

### 2b. DVFS fallback 처리

| Option | Description | Selected |
|--------|-------------|----------|
| required_clock = set_clock fallback | DVFS 룩업 실패 시 set_clock_mhz = required_clock_mhz, set_voltage_mv = 710.0 + logging.warning | ✓ |
| ValueError raise | DVFS 테이블 리드 실패 시 ValueError 발생 — 없는 묿 계산하지 않는다 | |

**User's choice:** required_clock = set_clock fallback (Recommended)
**Notes:** ValueError 없음. 경고 로깅 포함.

---

## 3. scenario_adapter.py 입력 계약

### 3a. runner.py 입력 타입

| Option | Description | Selected |
|--------|-------------|----------|
| Pydantic 모델만 | runner.run_simulation(pipeline: Pipeline, ip_catalog: dict[str, IpCatalog], ...) — 순수 Python | ✓ |
| ORM row 직접 수용 | runner이 SQLAlchemy ORM 객체 직접 받음. sim/이 db에 의존하지만 Phase 7 라우터와 관계 단순 | |

**User's choice:** Pydantic 모델만 (Recommended)
**Notes:** DB 의존 없음. Phase 7 라우터가 ORM → Pydantic 변환 후 호출.

### 3b. adapter 역할 분리

| Option | Description | Selected |
|--------|-------------|----------|
| scenario_adapter.py 단일 파일로 | adapter가 Usecase/Variant → runner 입력 훼 변환 + IpCatalog ip_ref 매핑 모두 담당 | ✓ |
| resolve 로직 runner에 포함 | runner.py가 IpCatalog dict를 받아 ip_ref 매핑을 내부에서 수행. adapter는 타입 변환만 | |

**User's choice:** scenario_adapter.py 단일 파일로 (Recommended)
**Notes:** runner.py는 좌표 0 저수준 유지.

---

## 4. 테스트 픽스처 전략

### 4a. 픽스처 소스

| Option | Description | Selected |
|--------|-------------|----------|
| sim/ 전용 인라인 픽스처 | tests/sim/conftest.py에 ISP/CSIS 수치 하드코딩 픽스처. YAML I/O 없음 | ✓ |
| demo/fixtures IP YAML 재사용 | demo/fixtures/01_capability/ip-*.yaml에 sim_params 섹션 주입 후 재사용. 실제 YAML이 테스트되지만 I/O 의존 | |

**User's choice:** sim/ 전용 인라인 픽스처 (Recommended)
**Notes:** sim_params 없는 IP 픽스처는 등장하지 않음.

### 4b. 검증 방식

| Option | Description | Selected |
|--------|-------------|----------|
| Golden 값 검증 | 설계 문서 공식으로 수작업 계산한 FHD30 BW/Power/Timing 값을 assert. 특정 IP 고정해 계산 특성 증명 | ✓ |
| 범위기반 검증 | assert 0 < bw < 10000 수준의 sanity check. 공식 코딩 오류 감지 못할 수 있음 | |

**User's choice:** Golden 값 검증 (Recommended)
**Notes:** ±1% 허용 오차. FHD30 ISP WDMA_BE BW ≈ 93.31 MB/s.

---

## Claude's Discretion

- `hw_config/dvfs-projectA.yaml` 내용 구조 — 설계 문서 §7.3 기준으로 CAM/INT/MIF 3개 도메인 작성
- `SimRunResult.vdd_power` 계산 방식 — VDD 도메인별 IP power 합산
- `tests/sim/` 디렉토리 구조 — test_constants.py / test_bw_calc.py / test_dvfs_resolver.py / test_runner.py 분리

## Deferred Ideas

- ParametricSweep ↔ ExplorationEngine 어댑터 → Phase Sim-3
- SimPy 이벤트 시뮬레이션 → Phase Sim-5 (선택사항)
- Dashboard BW/Power 오버레이 연동 → Phase 7 이후
- params_hash 캐싱 → Phase 7 범위
