# Requirements — ScenarioDB Viewer MVP & Simulation Engine

_Generated: 2026-05-05_

---

## v1 Requirements

### Milestone 1: Viewer & Runtime

#### DB Stabilization

- [ ] **DB-01**: ETL post-load semantic validation — FK-like 참조 무결성 검증 (scenario→project, variant→scenario, evidence→variant 등)
- [ ] **DB-02**: CanonicalScenarioGraph builder — DB에서 scenario + variant + project + evidence/issues/waivers/reviews를 단일 DTO로 조회
- [ ] **DB-03**: Repository 확장 — view_projection, scenario_graph 쿼리 캡슐화

#### Resolver Engine

- [ ] **RES-01**: Resolver 모델 정의 — `ResolverResult` (ip_resolutions, sw_resolutions, unresolved_requirements, warnings)
- [ ] **RES-02**: Capability mode matching — variant.ip_requirements → ip_catalog.capabilities 중 조건 충족 mode 매핑
- [ ] **RES-03**: Resolver 결과는 비영속 (runtime only) — authored Review와 분리

#### Review Gate Engine

- [ ] **GATE-01**: GateExecutionResult 모델 — status(PASS/WARN/BLOCK/WAIVER_REQUIRED), matched_rules, matched_issues, applicable_waivers, missing_waivers
- [ ] **GATE-02**: Gate rule 평가 — 기존 Matcher DSL 재사용, blocking rule 감지
- [ ] **GATE-03**: Issue matching — 기존 sql_matcher + Python fallback 통합
- [ ] **GATE-04**: Waiver applicability — issue와 waiver 연결, WAIVER_REQUIRED 판별
- [ ] **GATE-05**: Final status aggregation — BLOCK > WAIVER_REQUIRED > WARN > PASS 우선순위

#### API Endpoints

- [ ] **API-01**: `GET /api/v1/scenarios/{id}/variants/{vid}/graph` — CanonicalScenarioGraph 반환
- [ ] **API-02**: `GET /api/v1/scenarios/{id}/variants/{vid}/resolve` — ResolverResult 반환
- [ ] **API-03**: `GET /api/v1/scenarios/{id}/variants/{vid}/gate` — GateExecutionResult 반환
- [ ] **API-04**: View router 리팩토링 — `mode` 파라미터 실제 라우팅, DB-backed projection 구현, sample fallback 제거

#### Level 0 Viewer

- [ ] **VIEW-01**: `project_level0(db, scenario_id, variant_id)` DB 구현 — 하드코딩 sample data 제거
- [ ] **VIEW-02**: Level 0 architecture mode — 기존 lane view를 DB 데이터로 구동
- [ ] **VIEW-03**: Level 0 topology mode — SW task/thread/queue 노드 중심 레이아웃 (Camera App → CameraService → HAL → Driver → IP)
- [ ] **VIEW-04**: Gate overlay in viewer — GateExecutionResult를 인스펙터 패널 + risk card로 표시
- [ ] **VIEW-05**: `mode=architecture|topology` selector UI (Streamlit radio button)

---

### Milestone 2: Simulation Engine

#### sim/ Package

- [ ] **SIM-01**: `sim/constants.py` — BPP_MAP, BW_POWER_COEFF_DEFAULT, REFERENCE_VOLTAGE_MV
- [ ] **SIM-02**: `sim/models.py` — IPSimParams, DVFSLevel, DVFSTable, ResolvedIPConfig, PortBWResult, IPTimingResult, SimRunResult (Pydantic v2)
- [ ] **SIM-03**: `sim/bw_calc.py` — `calc_port_bw()` OTF 포트 제외, comp_ratio/llc_weight 적용
- [ ] **SIM-04**: `sim/perf_calc.py` — `calc_processing_time()` h_blank_margin 포함
- [ ] **SIM-05**: `sim/power_calc.py` — `calc_active_power()` V² 스케일링 + fps 스케일링
- [ ] **SIM-06**: `sim/dvfs_resolver.py` — DvfsResolver: OTF 그룹 v_valid_time 제약 + VDD 도메인 전압 정렬
- [ ] **SIM-07**: `hw_config/dvfs-projectA.yaml` — DVFS 테이블 (CAM/INT/MIF 도메인)
- [ ] **SIM-08**: `sim/scenario_adapter.py` — Usecase.pipeline + Variant.sim_port_config → runner 입력 변환
- [ ] **SIM-09**: `sim/runner.py` — 전체 파이프라인 오케스트레이터

#### Schema Extensions

- [ ] **SCH-01**: `IpCatalog.sim_params: IPSimParams | None` — ppc, unit_power_mw_mp, vdd, dvfs_group, ports (기존 문서 하위 호환 — Optional)
- [ ] **SCH-02**: `Variant.sim_port_config: dict[str, IPPortConfig] | None` — 포트별 format/size/compression
- [ ] **SCH-03**: `Variant.sim_config: SimGlobalConfig | None` — asv_group, sw_margin, bw_power_coeff, vbat, pmic_eff
- [ ] **SCH-04**: `Usecase.sensor: SensorSpec | None` — OTF 그룹 v_valid_time 기준
- [ ] **SCH-05**: `SimulationEvidence` 확장 — dma_breakdown: list[PortBWResult], timing_breakdown: list[IPTimingResult]

#### Simulation API

- [ ] **SAPI-01**: `POST /simulation/run` — SimulateRequest → 동기 계산 → SimulationEvidence 저장 + evidence_id 반환
- [ ] **SAPI-02**: `GET /simulation/results/{evidence_id}` — SimulationEvidence 상세 반환
- [ ] **SAPI-03**: `GET /simulation/bw-analysis` — PortBWResult 목록 (bw_mbs 내림차순)
- [ ] **SAPI-04**: `GET /simulation/power-analysis` — total_power, per_ip, per_vdd, bw_power
- [ ] **SAPI-05**: `GET /simulation/timing-analysis` — critical_ip, hw_time_max_ms, per_ip, feasible
- [ ] **SAPI-06**: params_hash 캐싱 — SHA256(scenario_id+variant_id+sim_params)[:16], 동일 해시 재계산 생략

---

## v2 Requirements (Deferred)

- Level 1 IP DAG 렌더링 (Sensor→CSIS→ISP→MLSC→MFC→DPU)
- Level 2 Composite drill-down (`expand=ISP` → 서브모듈)
- Evidence Dashboard Streamlit 페이지 (BW 워터폴 차트, DVFS 결정 테이블)
- ParametricSweep ↔ ExplorationEngine 어댑터 (Sim-3 연동)
- SimPy 이벤트 시뮬레이션 (Sim-5)
- gate_executions 영속 테이블 (runtime 게이트 결과 히스토리)
- Compare mode (variant 비교)

---

## Out of Scope

- Level 1/2 viewer — 다음 milestone (viewer 복잡도 분리)
- SimPy discrete-event 시뮬레이션 — Phase Sim-5로 별도 분리
- Excel/Visio import — 범위 외
- GPU multimedia IP (MDP, G3D) — 현재 ISP/MFC/DPU/CSIS 한정
- Multi-SoC 비교 — 단일 projectA 설정 기준

---

## Traceability

_(filled by roadmapper)_

| REQ-ID | Phase | Plan |
|--------|-------|------|
| DB-01~03 | | |
| RES-01~03 | | |
| GATE-01~05 | | |
| API-01~04 | | |
| VIEW-01~05 | | |
| SIM-01~09 | | |
| SCH-01~05 | | |
| SAPI-01~06 | | |
