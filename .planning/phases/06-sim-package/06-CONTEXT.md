# Phase 6: sim/ Package — Context

**Gathered:** 2026-05-11
**Status:** Ready for planning

<domain>
## Phase Boundary

BW/Power/DVFS/Timing 계산 로직을 `src/scenario_db/sim/` 패키지로 이식하고,
`runner.py`가 전체 파이프라인을 오케스트레이션한다.

Phase 5에서 완성된 Pydantic 스키마(`IPSimParams`, `PortInputConfig`, `SimGlobalConfig`,
`SensorSpec`, `PortBWResult`, `IPTimingResult`)를 그대로 소비하여 순수 계산 패키지를 구성한다.
Phase 7(Simulation API)이 이 runner를 DB → Pydantic 변환 후 호출한다.

**출력 파일 구조:**
```
src/scenario_db/sim/
├── __init__.py
├── constants.py       # BPP_MAP, BW_POWER_COEFF_DEFAULT, REFERENCE_VOLTAGE_MV
├── models.py          # ResolvedIPConfig, DVFSLevel, DVFSTable, SimRunResult
├── bw_calc.py         # calc_port_bw() — OTF 포트 제외
├── perf_calc.py       # calc_processing_time()
├── power_calc.py      # calc_active_power()
├── dvfs_resolver.py   # DvfsResolver 클래스
├── scenario_adapter.py # Usecase/Variant → runner 입력 조립 + ip_ref resolve
└── runner.py          # run_simulation() 전체 파이프라인
```

</domain>

<decisions>
## Implementation Decisions

### D-01: sim/models.py 범위 (모델 중복 방지)

- **결정:** `PortBWResult`, `IPTimingResult` — `models.evidence.simulation`에서 **re-import** (재정의 없음)
- **신규 정의:** `ResolvedIPConfig`, `DVFSLevel`, `DVFSTable`, `SimRunResult`만 `sim/models.py`에 정의
- **근거:** 단일 정의 원칙 — evidence layer 모델을 복제하면 Phase 7에서 타입 불일치 발생

### D-02: bw_calc 입력 모델

- **결정:** `bw_calc.calc_port_bw(port: PortInputConfig, fps: float, ...)` — `usecase.PortInputConfig` 직접 사용
- `sim/` 내부 전용 입력 모델 신규 정의 없음

### D-03: DVFS YAML 로딩 방식

- **결정:** `config.py`에 `DVFS_CONFIG_PATH = Path("hw_config/dvfs-projectA.yaml")` 추가
- `DvfsResolver` 생성 시 이 경로에서 자동 로드 (또는 테스트에서 `dvfs_tables` dict로 직접 주입)
- DVFS 파일 없거나 domain 미매칭 → `set_clock_mhz = required_clock_mhz`, `set_voltage_mv = REFERENCE_VOLTAGE_MV(710.0)` fallback + `logging.warning` 출력 (ValueError raise 없음)

### D-04: scenario_adapter.py 역할

- **결정:** `scenario_adapter.py` 단일 파일에 두 역할 모두 담당:
  1. `Usecase.pipeline + Variant.sim_port_config + Variant.sim_config` → `runner.run_simulation()` 입력 조립
  2. `ip_ref → IpCatalog.sim_params` resolve (ip_ref에서 hw_name_in_sim 추출 포함)
- **fallback:** `sim_params`가 없는 IP는 계산에서 제외하고 `logging.warning` 출력

### D-05: runner.py 입력 계약 — 순수 Pydantic

- **결정:** `run_simulation()` 시그니처:
  ```python
  def run_simulation(
      scenario_id: str,
      variant_id: str,
      pipeline: Pipeline,                         # Usecase.pipeline
      ip_catalog: dict[str, IpCatalog],           # id → IpCatalog
      dvfs_tables: dict[str, DVFSTable],          # domain → DVFSTable
      variant_port_config: dict[str, IPPortConfig],
      sim_config: SimGlobalConfig,
      sensor_spec: SensorSpec | None = None,
  ) -> SimRunResult:
  ```
- DB/ORM 의존 없음 — 순수 Python 함수
- Phase 7 라우터가 ORM row → Pydantic 변환 후 호출

### D-06: 테스트 픽스처 전략

- **결정:** `tests/sim/conftest.py` — ISP/CSIS 수치 인라인 하드코딩 픽스처
  - YAML 파일 I/O 없음 (sim/ 테스트가 파일 시스템에 의존하지 않음)
  - `sim_params` 없는 IP 픽스처는 등장하지 않음
- **검증 방식:** 설계 문서 공식으로 수작업 계산한 **Golden 값** assert
  - FHD30 ISP WDMA_BE: `BW = 0.5 × 30 × 1920 × 1080 × 1.0 × 1.5 / 1e6 ≈ 46.7 MB/s`
  - Active Power: `unit_power × (1920×1080/1e6) × (780/710)² × (30/30) ≈ ...`
  - ±1% 허용 오차 (float 연산 오차)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 설계 문서 (최우선)
- `docs/simulation-engine-integration.md` — BW/Power/DVFS/Timing 공식 전체 + 포팅 범위 + 모듈 설계 상세 (§6~§6.3 필수)
- `docs/simulation-engine-integration.md` §2.2 — 핵심 계산 공식 4개 (BW/Power/처리시간/DVFS)
- `docs/simulation-engine-integration.md` §6.2 — sim/ 모듈별 설계 상세 + 코드 스케치
- `docs/simulation-engine-integration.md` §11 — 리스크 및 제약 (DVFS fallback, 기존 테스트 보호 등)

### Phase 5 구현체 (소비 대상 모델)
- `src/scenario_db/models/capability/hw.py` — `IPSimParams`, `PortSpec`, `PortType`
- `src/scenario_db/models/definition/usecase.py` — `Pipeline`, `Variant`, `PortInputConfig`, `IPPortConfig`, `SimGlobalConfig`, `SensorSpec`
- `src/scenario_db/models/evidence/simulation.py` — `PortBWResult`, `IPTimingResult` (re-import 대상)

### 설정 파일
- `src/scenario_db/config.py` — DVFS_CONFIG_PATH 추가 위치
- `hw_config/dvfs-projectA.yaml` — DVFS 테이블 파일 (신규 작성 필요)

### Phase 6 요구사항
- `.planning/ROADMAP.md` §Phase 6 — Success Criteria 5개 항목 + Requirements SIM-01~SIM-09

</canonical_refs>

<code_context>
## Existing Code Insights

### 재사용 가능 자산

- `BaseScenarioModel` (`models/common.py`) — `ConfigDict(extra='forbid')` 기본 포함, sim/ 모델 전체에 사용
- `models/common.py` `DocumentId` — `ip_catalog` dict key로 사용
- `models/evidence/simulation.py` `PortBWResult`, `IPTimingResult` — sim/이 re-import해서 사용
- `models/definition/usecase.py` `Pipeline.edges` — OTF/M2M 분류 (`EdgeType` enum) 이미 정의됨
- `models/capability/hw.py` `PortType` — `DMA_READ/WRITE/OTF_IN/OTF_OUT` — bw_calc에서 OTF 판별에 사용

### 기존 패턴

- `extra='forbid'` — 모든 Pydantic 모델 (`ConfigDict(extra='forbid')`) — sim/models.py 동일 적용
- `model_dump(exclude_none=True)` — `vars()` / `__dict__` 금지 패턴 (CLAUDE.md 규칙)
- `int` 타입 산술 — timestamp math는 float 아닌 int (bw/power는 float OK)
- `logging.warning` — 경고 출력 패턴 (Phase 1 validate_loaded.py 참고)

### 통합 지점

- `sim/scenario_adapter.py` → `Usecase.pipeline.nodes[].ip_ref` → `IpCatalog[ip_ref].sim_params` 조회
- `sim/dvfs_resolver.py` → `config.DVFS_CONFIG_PATH` 에서 DVFSTable 로드 → `DvfsResolver.resolve()`
- `sim/runner.py` → `sim_config.dvfs_overrides` → DVFS 레벨 강제 (Phase 7 API 요청에서 전달)
- Phase 7 연결점: `run_simulation()` 반환 `SimRunResult` → `SimulationEvidence` 변환 → DB 저장

</code_context>

<specifics>
## Specific Implementation Notes

### BW 계산 공식 (설계 문서 §2.2)
```python
# bw_calc.calc_port_bw()
bpp = BPP_MAP[port.format]
comp_ratio = port.comp_ratio if port.compression != "disable" else 1.0
llc_weight = port.llc_weight if port.llc_enabled else 1.0
bw_mbs = comp_ratio * fps * port.width * port.height * (port.bitwidth / 8) * bpp / 1e6
bw_power_mw = bw_mbs * bw_power_coeff / 1000 * llc_weight
# OTF_IN/OTF_OUT 타입은 bw_mbs=0 반환
```

### DVFS 알고리즘 (설계 문서 §2.2)
```
required_clock = pixels × fps / ((1 - sw_margin) × ppc)
→ OTF 그룹: sensor v_valid_time 기반 처리량 제약 적용
→ 같은 dvfs_group: max(required_clock)으로 정렬
→ DVFS 테이블 룩업: required_clock 이상 최소 speed 레벨 선택
→ 같은 vdd domain: max(voltage)로 set_voltage 정렬
```

### Golden 값 테스트 예시
```python
# FHD30 ISP WDMA_BE (NV12, disable comp, 1920×1080, bitwidth=8)
# BW = 1.0 × 30 × 1920 × 1080 × 1.0 × 1.5 / 1e6 = 93.31 MB/s
assert abs(result.bw_mbs - 93.31) < 1.0

# FHD30 ISP RDMA_FE (BAYER, SBWC comp_ratio=0.5, 4000×2252, bitwidth=12)
# bpp = BPP_MAP["BAYER"]   → 설계 문서에서 확인 필요
# BW = 0.5 × 30 × 4000 × 2252 × (12/8) × bpp / 1e6
```

### ip_ref fallback 로직 (설계 문서 §12.6)
```python
def _resolve_ip_name(ip_ref: str, ip_catalog: dict[str, IpCatalog]) -> str:
    catalog = ip_catalog.get(ip_ref)
    if catalog and catalog.sim_params:
        return catalog.sim_params.hw_name_in_sim
    # fallback: "ip-isp-v12" → "ISP"
    parts = ip_ref.split("-")
    return parts[1].upper() if len(parts) > 1 else ip_ref
```

</specifics>

<deferred>
## Deferred Ideas

- ParametricSweep ↔ ExplorationEngine 어댑터 (`sim/exploration_adapter.py`) — Phase Sim-3으로 분리
- SimPy 이벤트 시뮬레이션 (`sim/simulator.py`) — Phase Sim-5 (선택사항)
- `NodeData.sim_overlay` + `EdgeData.bw_mbs` Dashboard 오버레이 — Phase 7 이후 (Pipeline Viewer 연동)
- Evidence Dashboard Streamlit 페이지 — Milestone 2 이후
- params_hash 캐싱 — Phase 7 (Simulation API) 범위

</deferred>

---

*Phase: 06-sim-package*
*Context gathered: 2026-05-11*
