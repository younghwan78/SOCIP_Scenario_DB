---
plan: "05-01"
phase: "05-schema-extensions"
status: complete
completed: 2026-05-10
commits:
  - "feat(05-01): Pydantic 모델 확장"
  - "feat(05-01): fixture 2종 + test_schema_extensions.py"
key-files:
  created:
    - tests/unit/test_schema_extensions.py
    - tests/unit/fixtures/hw/ip-isp-v12-with-sim.yaml
    - tests/unit/fixtures/evidence/sim-FHD30-with-breakdown.yaml
  modified:
    - src/scenario_db/models/capability/hw.py
    - src/scenario_db/models/definition/usecase.py
    - src/scenario_db/models/evidence/simulation.py
---

## Summary

Phase 5 Plan 05-01 완료 — Pydantic 모델 레이어 확장

### 수정된 Pydantic 모델 파일 (3개)

| 파일 | 변경 내용 |
|------|-----------|
| `src/scenario_db/models/capability/hw.py` | PortType/PortSpec/IPSimParams 신규, IpCatalog.sim_params 추가 |
| `src/scenario_db/models/definition/usecase.py` | PortInputConfig/IPPortConfig/SimGlobalConfig/SensorSpec 신규, Variant.sim_port_config/sim_config + Usecase.sensor 추가 |
| `src/scenario_db/models/evidence/simulation.py` | PortBWResult/IPTimingResult 신규, SimulationEvidence.dma_breakdown/timing_breakdown 추가 |

### 신규 정의된 클래스 (8개)

| 클래스 | 파일 | 설명 |
|--------|------|------|
| `PortType` | hw.py | DMA_READ/DMA_WRITE/OTF_IN/OTF_OUT StrEnum |
| `PortSpec` | hw.py | 포트 이름/타입/최대 BW |
| `IPSimParams` | hw.py | IP 시뮬레이션 파라미터 (ppc, vdd, dvfs_group 등) |
| `PortInputConfig` | usecase.py | 포트별 입력 설정 (format, compression, llc 등) |
| `IPPortConfig` | usecase.py | IP별 포트 설정 묶음 |
| `SimGlobalConfig` | usecase.py | 시뮬레이션 전역 설정 (asv_group, sw_margin 등) |
| `SensorSpec` | usecase.py | OTF 센서 스펙 (frame_width/height/fps/v_valid_ratio) |
| `PortBWResult` | simulation.py | 포트별 BW 결과 (direction Literal 사용, PortType import 없음) |
| `IPTimingResult` | simulation.py | IP별 타이밍 결과 (hw_time_ms, feasible 등) |

### 테스트 결과

- `test_schema_extensions.py`: **16개 PASSED**
- 기존 단위 테스트 전체: **357개 PASSED** (회귀 없음)

### Backward Compatibility 확인

| Fixture | 신규 필드 없음 | 결과 |
|---------|---------------|------|
| ip-isp-v12.yaml | sim_params 없음 | sim_params=None, ValidationError 없음 ✓ |
| sim-camera-recording-UHD60-A0-sw123.yaml | breakdown 없음 | dma_breakdown=[], timing_breakdown=[] ✓ |
| uc-camera-recording.yaml | sensor/sim_config 없음 | 모든 필드 None ✓ |

### Round-trip 확인

| Fixture | 설명 |
|---------|------|
| ip-isp-v12-with-sim.yaml | sim_params 포함 IpCatalog round-trip ✓ |
| sim-FHD30-with-breakdown.yaml | dma_breakdown/timing_breakdown 포함 round-trip ✓ |

## Self-Check: PASSED
