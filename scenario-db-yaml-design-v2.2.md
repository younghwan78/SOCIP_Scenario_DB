# Scenario DB — YAML 설계 문서 v2.2

> SoC Multimedia Scenario DB 구축을 위한 YAML 스키마, 파일 구조, 네이밍 규칙, 조건축 분리 설계
>
> **v2.2 주요 변경**: Gemini feedback 반영 — SW Catalog 도입, Resolver Violation Policy, Decision Integrity, Sweep 그룹화, Matcher DSL Syntax Sugar
>
> **v2.1 → v2.2 철학 연속성**: 3-경계선 원칙은 그대로. SW를 HW와 대칭적으로 Capability 레이어에 추가하여 경계선 완성.

---

## 목차

1. [v2.1 대비 주요 변경점](#1-v21-대비-주요-변경점)
2. [3-경계선 원칙 (v2.2 확장)](#2-3-경계선-원칙-v22-확장)
3. [설계 원칙](#3-설계-원칙)
4. [4-Layer 분리 구조 (v2.2 — SW Catalog 포함)](#4-4-layer-분리-구조-v22--sw-catalog-포함)
5. [식별자(ID) 체계](#5-식별자id-체계)
6. [Schema Version 정책](#6-schema-version-정책)
7. [전체 파일 구조 및 네이밍 규칙](#7-전체-파일-구조-및-네이밍-규칙)
8. [HW Catalog 설계](#8-hw-catalog-설계)
9. [**SW Catalog 설계 (v2.2 신규)**](#9-sw-catalog-설계-v22-신규)
10. [Scenario 설계 (Definition Layer)](#10-scenario-설계-definition-layer)
11. [Design Axes vs Execution Axes](#11-design-axes-vs-execution-axes)
12. [Requirement → Capability Resolution](#12-requirement--capability-resolution)
13. [**Resolver Violation Policy (v2.2 신규)**](#13-resolver-violation-policy-v22-신규)
14. [Size / Crop / Scale 처리](#14-size--crop--scale-처리)
15. [**Parametric Sweep 그룹화 (v2.2 강화)**](#15-parametric-sweep-그룹화-v22-강화)
16. [Evidence Layer](#16-evidence-layer)
17. [Decision Layer](#17-decision-layer)
18. [**Decision Integrity — Triple-Track Attestation (v2.2 신규)**](#18-decision-integrity--triple-track-attestation-v22-신규)
19. [Matcher DSL](#19-matcher-dsl)
20. [**Matcher DSL Syntax Sugar (v2.2 신규)**](#20-matcher-dsl-syntax-sugar-v22-신규)
21. [**Review Gate Rules (v2.2 신규)**](#21-review-gate-rules-v22-신규)
22. [DB 스키마 전략](#22-db-스키마-전략)
23. [DB Table ↔ 파일명 매핑](#23-db-table--파일명-매핑)
24. [마이그레이션 가이드 (v2.1 → v2.2)](#24-마이그레이션-가이드-v21--v22)
25. [핵심 설계 원칙 요약](#25-핵심-설계-원칙-요약)

---

## 1. v2.1 대비 주요 변경점

| Gemini 지적 | v2.1 (Before) | v2.2 (After) | 우선순위 |
|-----------|--------------|--------------|---------|
| SW Catalog 부재 | `sw_baseline: "vendor-v1.2.3"` (string) | **`sw_catalog/` + 구조화된 SW profile** | P1 |
| Resolver 실패 처리 미정의 | matching 로직만 정의 | **3단 Violation Policy** (per-req/overall/result) | P1 |
| Decision 위변조 가능 | `approver: LeeSR` (YAML만) | **Triple-track Attestation** (claim/git/auth) | P1 |
| Sweep 결과 추적 불가 | evidence가 개별적 | **`sweep_job_id` + sweep_context 블록** | P2 |
| Matcher DSL 장황함 | AST만 사용 | **Syntax Sugar 허용 + AST canonical** | P2 |
| Matcher에 SW 조건 없음 | axis/ip 필드만 | **`sw_feature`, `sw_component` 필드 추가** | P2 |
| Sweep × Aggregation 모순 | 미정의 | **2단 aggregation 명시** | P3 |
| Review Gate rule 미정의 | 예시만 | **`gate_rules/` 설정 파일** | P3 |
| Issue SW 회귀 추적 없음 | 발견 시점만 | **`discovered_in_sw` + regression 필드** | P3 |

---

## 2. 3-경계선 원칙 (v2.2 확장)

v2.2의 핵심은 v2.1의 3-경계선을 유지하되 **SW 영역까지 확장**하는 것.

### 2-1. Variant ≠ Instance (변경 없음)

```
VARIANT (설계 의도)          INSTANCE (실행 조건)
design_axes                  execution_axes
- resolution, fps, codec     - thermal, power_state
- hdr, concurrency           - silicon_rev, sw_baseline_ref
```

### 2-2. Capability ≠ Requirement (v2.2 확장)

```
┌──────────────────────────┐      ┌──────────────────────────┐
│  CAPABILITY (추상)         │      │  REQUIREMENT (usecase)   │
├──────────────────────────┤      ├──────────────────────────┤
│  HW: normal/low_power/    │      │  required_throughput     │
│      high_throughput       │ ←──→ │  required_bitdepth       │
│                            │      │  required_codec_level    │
│  SW: hal/kernel/fw        │      │  required_sw_features    │ ← v2.2 신규
│      feature_flags         │      │  required_sw_version     │
└──────────────────────────┘      └──────────────────────────┘
```

### 2-3. Canonical ≠ Derived (v2.2 강화)

| 레이어 | Canonical (YAML) | Derived (DB) |
|--------|------------------|--------------|
| Scenario | variant 정의 | parametric 전개된 instances |
| Issue | `match_rule` AST | `issue_variant_matches` MV |
| Matcher | AST (normalized) | **Syntax Sugar (input only)** |
| Decision | `approver_claim` | **`approved_by_auth` (server)** |

---

## 3. 설계 원칙

| 원칙 | v2.2 상태 |
|------|-----------|
| HW/SW/Scenario 분리 | **v2.2 확장** — SW 독립 |
| 계층 표현 (IP + submodule) | 유지 |
| 참조는 ID로만 (`*_ref`) | 유지 |
| 파일명 = ID | 유지 |
| 조건은 필드, 파일명 아님 | 유지 |
| Design axes vs Execution axes | 유지 |
| Capability는 추상, Requirement는 scenario | 유지 |
| Canonical vs Derived 분리 | 유지 |
| **HW와 SW는 대칭 구조** | **v2.2 신규** |
| **Resolver 실패는 명시적 policy** | **v2.2 신규** |
| **Decision은 3-track 무결성** | **v2.2 신규** |

---

## 4. 4-Layer 분리 구조 (v2.2 — SW Catalog 포함)

```
┌─────────────────────────────────────────────────────────┐
│ Layer 1: DEFINITION                                      │
│   scenarios/projects/*/usecase/uc-*.yaml                │
│   - pipeline, design_axes, variants                      │
│   - ip_requirements, sw_requirements (v2.2 신규)         │
│   - violation_policy (v2.2 신규)                         │
└─────────────────────────────────────────────────────────┘
                      ↓ 참조
┌─────────────────────────────────────────────────────────┐
│ Layer 2: CAPABILITY (v2.2: HW + SW 대칭)                 │
│                                                           │
│   ┌─── HW Catalog ──────┐  ┌─── SW Catalog (신규) ─┐    │
│   │ hw_catalog/          │  │ sw_catalog/             │   │
│   │   soc-*.yaml         │  │   sw-*.yaml             │   │
│   │   ip-*.yaml          │  │   hal-*.yaml            │   │
│   │   sub-*.yaml         │  │   kernel-*.yaml         │   │
│   │   conn-*.yaml        │  │   fw-*.yaml             │   │
│   └──────────────────────┘  └─────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                      ↓ resolver (v2.2: violation policy)
┌─────────────────────────────────────────────────────────┐
│ Layer 3: EVIDENCE                                        │
│   results/*/sim/sim-*.yaml                              │
│   results/*/measure/meas-*.yaml                         │
│   - execution_context (sw_baseline_ref)                  │
│   - sweep_context (v2.2 신규)                           │
│   - resolution_result + violations (v2.2 강화)           │
│   - provenance (measurement 필수)                        │
└─────────────────────────────────────────────────────────┘
                      ↓ 분석
┌─────────────────────────────────────────────────────────┐
│ Layer 4: DECISION                                        │
│   reviews/rev-*.yaml                                    │
│   issues/iss-*.yaml                                     │
│   waivers/waiver-*.yaml                                 │
│   gate_rules/*.yaml (v2.2 신규)                         │
│   - match_rule (AST + Syntax Sugar 지원)                 │
│   - triple-track attestation (v2.2 신규)                 │
└─────────────────────────────────────────────────────────┘
```

---

## 5. 식별자(ID) 체계

### 3-Level ID (v2.2 — sw_baseline_ref 추가)

```
Level 1: scenario_id  = uc-camera-recording

Level 2: variant_id   = UHD60-HDR10-H265
                        (design 축만)

Level 3: instance_id  = {scenario}/{variant}/{silicon}/{sw_baseline}/{thermal}/run-{ts}
                        예: uc-camera-recording/UHD60-HDR10-H265/
                            A0/sw-vendor-v1.2.3/hot/run-20260417T014100
```

v2.2에서는 instance_id에 `sw_baseline` 참조가 명확해짐 (문자열 아닌 SW catalog FK).

---

## 6. Schema Version 정책

SemVer 유지:

| Bump | 조건 | v2.1 → v2.2 해당 여부 |
|------|------|---------------------|
| Major (→ 3.0) | Breaking | ❌ v2.2는 backward-compatible |
| Minor (→ 2.2) | 선택 필드 추가 | ✅ SW Catalog, violation_policy 등 신규 |
| Patch (→ 2.2.1) | 문서만 | — |

```yaml
schema_version: "2.2"
schema_compat:
  min_reader: "2.1"                      # v2.1 reader로 핵심 필드 읽기 가능
  new_optional_fields:
    - sw_baseline_ref
    - violation_policy
    - sweep_context
    - triple_track_attestation
```

---

## 7. 전체 파일 구조 및 네이밍 규칙

```
scenario-db/
├── hw_catalog/                          # Layer 2a: HW CAPABILITY
│   ├── soc/soc-*.yaml
│   ├── ip/
│   │   ├── camera/ip-*.yaml
│   │   ├── codec/ip-*.yaml
│   │   ├── display/ip-*.yaml
│   │   └── memory/ip-*.yaml
│   └── connectivity/conn-*.yaml
│
├── sw_catalog/                          # Layer 2b: SW CAPABILITY (v2.2 신규)
│   ├── profiles/                        # 통합 SW baseline profile
│   │   └── sw-vendor-v1.2.3.yaml
│   ├── hal/                             # HAL 컴포넌트
│   │   ├── hal-cam-v4.5.yaml
│   │   ├── hal-codec-v3.1.yaml
│   │   └── hal-disp-v2.7.yaml
│   ├── kernel/                          # Kernel/Driver
│   │   └── kernel-6.1.50-android15.yaml
│   └── firmware/                        # FW
│       ├── fw-isp-0x41.yaml
│       └── fw-dsp-0x22.yaml
│
├── scenarios/                           # Layer 1: DEFINITION
│   └── projects/
│       └── proj-A-exynos2500/
│           ├── project.yaml
│           └── usecase/uc-*.yaml
│
├── results/                             # Layer 3: EVIDENCE
│   └── proj-A-exynos2500/
│       ├── sim/sim-*.yaml
│       └── measure/meas-*.yaml
│
├── reviews/                             # Layer 4: DECISION
│   └── proj-A-exynos2500/
│       ├── rev-*.yaml
│       └── waiver-*.yaml
│
├── issues/                              # Layer 4: DECISION
│   └── iss-*.yaml
│
└── gate_rules/                          # Layer 4: DECISION (v2.2 신규)
    └── rule-*.yaml
```

### 파일명 Prefix (v2.2 추가분)

| Prefix | Layer | 예시 | v2.2 신규? |
|--------|-------|------|-----------|
| `soc-`, `ip-`, `sub-`, `conn-` | HW Capability | `ip-isp-v12.yaml` | — |
| `sw-` | SW Capability (profile) | `sw-vendor-v1.2.3.yaml` | ✅ |
| `hal-` | SW Capability (HAL) | `hal-cam-v4.5.yaml` | ✅ |
| `kernel-` | SW Capability (kernel) | `kernel-6.1.50-android15.yaml` | ✅ |
| `fw-` | SW Capability (firmware) | `fw-isp-0x41.yaml` | ✅ |
| `rule-` | Decision (gate rule) | `rule-feasibility-check.yaml` | ✅ |
| `proj-`, `uc-` | Definition | — | — |
| `sim-`, `meas-` | Evidence | — | — |
| `rev-`, `waiver-`, `iss-` | Decision | — | — |

---

## 8. HW Catalog 설계

v2.1과 동일. 변경 없음. (§8의 IP 계층, abstract capability, mode catalog 등 그대로 유지)

### 8-1. 간략 예시

```yaml
# hw_catalog/ip/camera/ip-isp-v12.yaml
id: ip-isp-v12
schema_version: "2.2"
kind: ip
category: camera

hierarchy:
  type: composite
  submodules:
    - { ref: sub-3aa-v4,  instance_id: ISP.3AA0 }
    - { ref: sub-tnr-v3,  instance_id: ISP.TNR }
    # ...

capabilities:
  operating_modes:
    - { id: normal,         throughput_mpps: 500 }
    - { id: low_power,      max_clock_mhz: 266, throughput_mpps: 250 }
    - { id: high_throughput, min_clock_mhz: 533, throughput_mpps: 800 }

  supported_features:
    bitdepth: [8, 10, 12]
    hdr_formats: [HDR10, HDR10plus, DolbyVision]
    compression: [SBWC_v4, AFBC_v2]
```

---

## 9. SW Catalog 설계 (v2.2 신규)

### 9-1. 설계 철학

HW Catalog와 **완전 대칭**:

| 항목 | HW Catalog | SW Catalog |
|------|-----------|-----------|
| 최상위 | `soc-*.yaml` | `sw-*.yaml` (SW profile) |
| 컴포넌트 | `ip-*.yaml` | `hal-*.yaml`, `kernel-*.yaml`, `fw-*.yaml` |
| 하위 단위 | `sub-*.yaml` | (HAL sub-modules, driver files) |
| 특성 | `capabilities`, `performance` | `capabilities`, `feature_flags` |
| 버전 | `rtl_version` | `version` |
| 호환성 | `compatible_soc` | `compatible_soc`, `replaces` |

### 9-2. SW Profile (통합) — `sw-vendor-v1.2.3.yaml`

```yaml
id: sw-vendor-v1.2.3
schema_version: "2.2"
kind: sw_profile

metadata:
  baseline_family: vendor                # vendor | aosp | engineering
  version: "1.2.3"
  release_date: "2026-03-15"
  release_type: production               # engineering | beta | production
  compatible_soc: [soc-exynos2500]
  git_branch: "release/vendor-v1.2.3"
  git_commit_sha: "abc1234def"

# --- 컴포넌트 구성 (HW Catalog의 ips[] 대칭) ---
components:
  hal:
    - { domain: camera,  ref: hal-cam-v4.5 }
    - { domain: codec,   ref: hal-codec-v3.1 }
    - { domain: display, ref: hal-disp-v2.7 }
    - { domain: audio,   ref: hal-audio-v1.8 }

  kernel:
    ref: kernel-6.1.50-android15
    config_deltas:                       # vanilla kernel 대비 변경
      - "CONFIG_EXYNOS_CAM_LLC=y"

  firmware:
    - { target: isp, ref: fw-isp-0x41 }
    - { target: dsp, ref: fw-dsp-0x22 }
    - { target: mfc, ref: fw-mfc-0x18 }

# --- SW feature flags (정책/기능 on/off) ---
feature_flags:
  # Camera stack
  camera_zsl: enabled
  camera_ois_hw: enabled
  camera_super_hdr: enabled

  # Memory/Power
  LLC_dynamic_allocation: enabled        # HW LLC 동적 할당
  LLC_per_ip_partition: disabled
  ddr_governor: "performance"

  # ISP
  TNR_early_abort: enabled               # 저조도 아닌 경우 skip
  DNS_adaptive_strength: enabled
  ISP_bypass_for_preview: disabled

  # Codec
  MFC_hwae: enabled                      # hardware adaptive encoding
  MFC_b_frame: enabled

  # Display
  DPU_write_back_cache: disabled
  DPU_compositing_mode: "layered"

# --- 버전 호환성/회귀 추적 ---
compatibility:
  replaces: sw-vendor-v1.2.2
  min_compatible_version: "v1.2.0"
  breaking_changes:
    - area: camera.llc_policy
      description: "LLC allocation now per-IP instead of shared"
      regression_risk: medium

# --- 알려진 이슈 ---
known_issues_at_release:
  - ref: iss-LLC-thrashing-0221
    status: workaround_applied
```

### 9-3. HAL 컴포넌트 — `hal-cam-v4.5.yaml`

```yaml
id: hal-cam-v4.5
schema_version: "2.2"
kind: sw_component
category: hal

metadata:
  name: "Camera HAL v4.5"
  version: "4.5.0"
  compatible_android: ["15", "16"]
  compatible_soc: [soc-exynos2500, soc-exynos2600]
  source: vendor

# --- HAL 하위 구조 ---
components:
  interfaces:
    - AIDL: "android.hardware.camera.device@3.7"
  providers:
    - cam-provider-exynos2500
  sub_modules:
    - name: MetadataProcessor
      version: "2.1"
    - name: BufferManager
      version: "3.3"
      capabilities:
        allocation_strategy: [ion_heap, dmabuf_heap]
        caching_policy: [write_back, write_through]

# --- HAL feature flags ---
feature_flags:
  zsl_ring_buffer: enabled
  hdr_fusion_inline: enabled
  preview_buffer_count: 8
  capture_buffer_count: 4

# --- HW 연동 (HW Catalog 참조) ---
hw_bindings:
  required_ips: [ip-isp-v12, ip-csis-v8]
  required_min_ip_version:
    ip-isp-v12: "12.0"

# --- 알려진 성능 특성 ---
performance_notes:
  preview_latency_overhead_ms: 2.5
  capture_processing_overhead_ms: 8.0
```

### 9-4. Kernel — `kernel-6.1.50-android15.yaml`

```yaml
id: kernel-6.1.50-android15
schema_version: "2.2"
kind: sw_component
category: kernel

metadata:
  version: "6.1.50"
  android_gki_version: "android15-6.1"
  branch: "android15-6.1-lts"
  compatible_soc: [soc-exynos2500]

# --- 드라이버 목록 ---
drivers:
  camera:
    - { name: exynos-cam,  version: "2.1", git_sha: "9f3c21b" }
    - { name: exynos-csis, version: "1.8", git_sha: "e2a1c9f" }
  codec:
    - { name: exynos-mfc, version: "5.3" }
  memory:
    - { name: exynos-llc, version: "1.2" }

# --- Kernel config capabilities ---
capabilities:
  config_flags:
    CONFIG_EXYNOS_CAM_LLC: y
    CONFIG_EXYNOS_CAM_DVFS: y
    CONFIG_ANDROID_VENDOR_HOOKS: y
  governor_support:
    cpu: [schedutil, performance, powersave]
    gpu: [simpleondemand, performance]
```

### 9-5. Firmware — `fw-isp-0x41.yaml`

```yaml
id: fw-isp-0x41
schema_version: "2.2"
kind: sw_component
category: firmware

metadata:
  target_ip: ip-isp-v12
  version: "0x41"
  binary_sha256: "..."

capabilities:
  supported_modes: [normal, low_power, high_throughput]
  tuning_profile_ids: [TP-2500-v2, TP-2500-v3]
  max_sensor_count: 4
```

### 9-6. Scenario에서 SW 요구사항 선언 (v2.2 신규)

```yaml
# uc-camera-recording.yaml 내 variant
variants:
  - id: UHD60-HDR10-H265
    design_conditions: { ... }

    # --- HW 요구사항 (v2.1과 동일) ---
    ip_requirements:
      isp0:
        required_throughput_mpps: 498
        required_features: [HDR10]
      mfc:
        required_codec: H.265
        required_level: "5.1"

    # --- SW 요구사항 (v2.2 신규) ---
    sw_requirements:
      profile_constraints:
        min_version: "v1.2.0"              # SW profile 최소 버전
        baseline_family: [vendor]

      required_features:                   # feature_flag 요구
        - LLC_dynamic_allocation: enabled
        - TNR_early_abort: enabled
        - MFC_hwae: enabled

      required_hal:
        camera:
          min_version: "4.5"
        codec:
          min_version: "3.0"
          required_capabilities: [B_frame_support]

      required_firmware:
        isp: { min_version: "0x41" }
```

### 9-7. Execution Context에 SW 참조 (v2.2 수정)

```yaml
# sim-*.yaml / meas-*.yaml
execution_context:
  silicon_rev: A0
  sw_baseline_ref: sw-vendor-v1.2.3      # v2.1 문자열 → v2.2 FK 참조
  thermal: hot
  ambient_temp_c: 35
  power_state: charging

  # SW feature 상태는 profile에 이미 있지만,
  # runtime override가 있었다면 기록
  sw_runtime_overrides:
    LLC_dynamic_allocation: disabled      # 이 측정에서만 비활성
```

### 9-8. DB 스키마 영향

```sql
-- SW Catalog 테이블 (HW와 대칭)
CREATE TABLE sw_profiles (
    id              TEXT PRIMARY KEY,
    metadata        JSONB NOT NULL,
    components      JSONB NOT NULL,       -- hal/kernel/firmware refs
    feature_flags   JSONB NOT NULL,
    compatibility   JSONB,
    yaml_sha256     TEXT NOT NULL
);

CREATE TABLE sw_components (
    id              TEXT PRIMARY KEY,
    category        TEXT CHECK (category IN ('hal','kernel','firmware')),
    version         TEXT NOT NULL,
    metadata        JSONB,
    capabilities    JSONB,
    feature_flags   JSONB
);

CREATE INDEX idx_sw_profile_features ON sw_profiles USING GIN (feature_flags);

-- evidence에 SW FK 추가
ALTER TABLE evidence ADD COLUMN sw_baseline_ref TEXT
    REFERENCES sw_profiles(id);

-- Hot path
ALTER TABLE evidence ADD COLUMN sw_version_hint TEXT
    GENERATED ALWAYS AS (execution_context->>'sw_baseline_ref') STORED;
```

### 9-9. SW Catalog의 실무 가치

| 쿼리 | v2.1 (불가) | v2.2 (가능) |
|------|-----------|------------|
| "LLC_dynamic_allocation 켜진 빌드에서 power 회귀" | ❌ | ✅ |
| "HAL v4.5 이상에서만 발생하는 issue" | ❌ | ✅ |
| "kernel 6.1.50 이후 camera 회귀" | ❌ | ✅ |
| "FW 0x41 → 0x42 변경 영향 IP" | ❌ | ✅ |
| "SW profile 간 KPI 비교" | ❌ | ✅ |

---

## 10. Scenario 설계 (Definition Layer)

### 10-1. Project 메타 (v2.2 — SW 기본 설정 추가)

```yaml
id: proj-A-exynos2500
schema_version: "2.2"
kind: project

metadata:
  name: "Project A"
  soc_ref: soc-exynos2500
  target_launch_date: "2026-10-31"

globals:
  # ... (v2.1과 동일)

  # --- v2.2 신규: 기본 SW profile ---
  default_sw_profile_ref: sw-vendor-v1.2.3
  tested_sw_profiles:                    # 이 과제에서 측정한 SW profile들
    - sw-vendor-v1.2.0
    - sw-vendor-v1.2.3
    - sw-vendor-v1.3.0-beta
```

### 10-2. Usecase (v2.2 — sw_requirements + violation_policy)

```yaml
id: uc-camera-recording
schema_version: "2.2"
kind: scenario.usecase
project_ref: proj-A-exynos2500

metadata:
  name: "Camera Recording Pipeline"
  category: [camera, codec]
  domain: [camera]

pipeline:
  nodes:
    - { id: csis0, ip_ref: ip-csis-v8, instance_index: 0 }
    - { id: isp0,  ip_ref: ip-isp-v12, instance_index: 0, role: main }
    - { id: mfc,   ip_ref: ip-mfc-v14 }
    - { id: dpu,   ip_ref: ip-dpu-v9 }
    - { id: llc,   ip_ref: ip-llc-v2 }
  edges:
    - { from: csis0, to: isp0, type: OTF }
    - { from: isp0,  to: mfc,  type: M2M, buffer: "RECORD_BUF" }
    - { from: isp0,  to: dpu,  type: M2M, buffer: "PREVIEW_BUF" }

size_profile:
  anchors:
    sensor_full: "4000x3000"
    record_out:  "1920x1080"
    preview_out: "1920x1080"

design_axes:
  - { name: resolution,  enum: [FHD, UHD, 8K] }
  - { name: fps,         enum: [30, 60, 120] }
  - { name: codec,       enum: [H.264, H.265, AV1] }
  - { name: hdr,         enum: [SDR, HDR10, HDR10plus] }
  - { name: concurrency, enum: [single, with_preview, dual_cam] }

variants:
  # ============================================================
  # Production variant (Strict)
  # ============================================================
  - id: UHD60-HDR10-H265
    severity: heavy
    design_conditions:
      resolution: UHD
      fps: 60
      codec: H.265
      hdr: HDR10
      concurrency: with_preview
    size_overrides:
      record_out:  "3840x2160"
      preview_out: "1920x1080"

    # --- HW 요구사항 ---
    ip_requirements:
      isp0:
        required_throughput_mpps: 498
        required_bitdepth: 10
        required_features: [HDR10]
      mfc:
        required_codec: H.265
        required_level: "5.1"
      llc:
        required_allocations: { ISP.TNR: 2MB, MFC: 1MB }

    # --- SW 요구사항 (v2.2 신규) ---
    sw_requirements:
      profile_constraints:
        min_version: "v1.2.0"
      required_features:
        - LLC_dynamic_allocation: enabled
        - TNR_early_abort: enabled
        - MFC_hwae: enabled
      required_hal:
        camera: { min_version: "4.5" }
        codec:  { min_version: "3.0" }

    # --- Violation Policy (v2.2 신규) ---
    violation_policy:
      classification: production              # production | exploration | research
      per_requirement:
        default:
          action: FAIL_FAST                   # production이면 엄격
      overall:
        if_any_fail: abort_simulation
        report_level: error

    tags: [thermal_sensitive, ddr_bw_critical]

  # ============================================================
  # Exploration variant (Best Effort)
  # ============================================================
  - id: 8K120-HDR10plus-AV1-exploration
    severity: critical
    design_conditions:
      resolution: 8K
      fps: 120
      codec: AV1
      hdr: HDR10plus
      concurrency: single

    ip_requirements:
      isp0:
        required_throughput_mpps: 3981         # HW 한계 초과!
      mfc:
        required_codec: AV1
        required_level: "6.2"

    sw_requirements:
      required_features:
        - LLC_per_ip_partition: enabled        # 아직 미구현 feature

    # --- Exploration variant는 policy가 관대 ---
    violation_policy:
      classification: exploration
      per_requirement:
        isp0.required_throughput_mpps:
          action: WARN_AND_CAP
          cap_source: capability_max           # HW max로 cap
          report_gap: true
        sw_requirements.required_features:
          action: WARN_AND_EMULATE             # emulation으로 진행
      overall:
        if_any_fail: continue_with_flag
        result_flag: "exploration_only"

  # ============================================================
  # Derived (상속)
  # ============================================================
  - id: UHD60-HDR10-sustained-10min
    severity: critical
    derived_from_variant: UHD60-HDR10-H265
    design_conditions_override:
      duration_category: sustained_10min

inheritance_policy:
  max_depth: 3
  cycle_detection: required

parametric_sweeps:
  - id: zoom_sweep
    applies_to: [UHD60-HDR10-H265]
    axis: size_profile.transforms[1].crop_ratio
    values: [1.0, 0.5, 0.25, 0.1]

references:
  known_issues:
    - iss-LLC-thrashing-0221
```

---

## 11. Design Axes vs Execution Axes

v2.1과 동일 (§10 그대로). v2.2에서는 execution_axes의 `sw_baseline`이 **FK 참조**로 명확해짐.

| 축 | 분류 | v2.2 형태 |
|----|------|-----------|
| resolution, fps, codec, hdr, concurrency | design | enum 값 |
| thermal, power_state, ambient_temp_c | execution | enum 값 |
| silicon_rev | execution | 문자열 |
| **sw_baseline_ref** | **execution** | **FK → sw_profiles** (v2.2 변경) |
| build_id, device_id | execution | 문자열 |

---

## 12. Requirement → Capability Resolution

### 12-1. v2.2 확장: HW + SW Resolution

```
Scenario Requirements      →    Resolver    →    Capability Match
─────────────────────           ────────         ────────────────
ip_requirements                   match           ip_catalog.mode
sw_requirements                   match           sw_profile.features
                                                  + sw_components
```

### 12-2. Resolver 동작 (v2.2)

```yaml
# 입력
variant.ip_requirements.isp0:
  required_throughput_mpps: 498
variant.sw_requirements:
  required_features: [LLC_dynamic_allocation: enabled]
execution_context.sw_baseline_ref: sw-vendor-v1.2.3

# Resolver 로직
1. HW resolver
   - ip-isp-v12.capabilities.operating_modes에서 throughput >= 498 찾기
   - → matched: high_throughput (max 800)

2. SW resolver (v2.2 신규)
   - sw-vendor-v1.2.3.feature_flags 조회
   - LLC_dynamic_allocation == enabled → OK
   - 모든 required_features 만족 확인

3. Violation 판정
   - 모두 만족 → PASS
   - 일부 미달 → violation_policy에 따라 분기
```

### 12-3. Evidence 기록 (v2.2 강화)

```yaml
# sim-*.yaml
resolution_result:
  hw_resolution:
    isp0:
      requested: { throughput_mpps: 498 }
      matched_mode: high_throughput
      headroom: { throughput: 302 }
    mfc:
      matched_mode: normal

  sw_resolution:                          # v2.2 신규
    profile_ref: sw-vendor-v1.2.3
    required_features_check:
      - { feature: LLC_dynamic_allocation, required: enabled, actual: enabled, status: PASS }
      - { feature: TNR_early_abort,        required: enabled, actual: enabled, status: PASS }
    hal_compatibility:
      camera: { required_min: "4.5", actual: "4.5", status: PASS }

  overall_feasibility: production_ready   # v2.2 신규
  violations: []
```

---

## 13. Resolver Violation Policy (v2.2 신규)

### 13-1. 3단 Policy 구조

```
┌─────────────────────────────────────┐
│ Level 1: per_requirement             │
│   개별 requirement별 action          │
│   (FAIL_FAST / WARN_AND_CAP 등)     │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ Level 2: overall                     │
│   전체 variant 판정                   │
│   (abort / continue_with_flag)       │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ Level 3: result_classification       │
│   결과 label                          │
│   (production_ready / exploration /  │
│    infeasible)                       │
└─────────────────────────────────────┘
```

### 13-2. Action Enum

| Action | 의미 | 적용 사례 |
|--------|------|----------|
| `FAIL_FAST` | 즉시 중단, 에러 리포트 | Production variant의 critical requirement |
| `WARN_AND_CAP` | HW max로 cap하고 진행 | Exploration 시 throughput 한계 초과 |
| `WARN_AND_EMULATE` | 기능 emulation으로 진행 | 미구현 SW feature |
| `SKIP_AND_LOG` | 해당 체크 건너뛰고 기록 | 선택적 feature |
| `DEFAULT_TO` | 기본값으로 대체 | optional parameter |

### 13-3. 전체 예시

```yaml
violation_policy:
  classification: production               # production | exploration | research

  # Level 1: per-requirement
  per_requirement:
    default:                               # 명시 안 된 항목의 기본 action
      action: FAIL_FAST

    # 특정 requirement override
    isp0.required_throughput_mpps:
      action: WARN_AND_CAP
      cap_source: capability_max           # HW max 사용
      report_gap: true

    sw_requirements.required_features.LLC_per_ip_partition:
      action: WARN_AND_EMULATE
      emulation_strategy: "software_partition"

    mfc.required_level:
      action: FAIL_FAST                    # codec level은 양보 불가

  # Level 2: overall
  overall:
    if_any_fail: abort_simulation          # abort | continue_with_flag
    if_any_warn: continue_with_flag
    flag_label: "has_violations"
    report_level: error                    # error | warning | info

  # Level 3: result classification
  result_classification:
    rules:
      - { condition: "no_violations",           result: production_ready }
      - { condition: "only_warn_and_cap",       result: exploration_only }
      - { condition: "has_fail_fast",           result: infeasible }
      - { condition: "has_emulation",           result: research_mode }
```

### 13-4. Evidence에서의 Violation 기록

```yaml
# sim-*.yaml
resolution_result:
  hw_resolution:
    isp0:
      requested: { throughput_mpps: 1000 }
      matched_mode: high_throughput
      capability_max: 800
      violations:
        - requirement: throughput_mpps
          requested: 1000
          provided: 800
          action_taken: WARN_AND_CAP
          gap_pct: 25.0
          reason: "exceeds HW capability_max"

  sw_resolution:
    violations:
      - feature: LLC_per_ip_partition
        required: enabled
        actual: disabled
        action_taken: WARN_AND_EMULATE
        emulation_note: "simulated via software LLC partition model"

  overall_feasibility: exploration_only    # production_ready | exploration_only | infeasible | research_mode
  violation_summary:
    total: 2
    fail_fast: 0
    warn_and_cap: 1
    warn_and_emulate: 1
```

### 13-5. Review Gate 연동

Violation 결과는 Review Gate 자동 판정에 직접 연결:

```yaml
# gate_rules/rule-feasibility-check.yaml
id: rule-feasibility-check
trigger: on_evidence_register

condition:
  match:
    resolution_result.overall_feasibility: { $in: [infeasible] }

action:
  gate_result: BLOCK
  detail_template: "variant {{variant_ref}} marked infeasible. violations: {{violation_summary}}"
```

---

## 14. Size / Crop / Scale 처리

v2.1과 동일. 변경 없음.

---

## 15. Parametric Sweep 그룹화 (v2.2 강화)

### 15-1. 문제 인식 (v2.1 빈틈)

v2.1: "Sweep은 variant가 아니라 evidence가 늘어남"은 맞지만, **개별 evidence가 분산**되어 sweep 그룹 추적 불가.

### 15-2. Sweep Job 개념 도입

```
Scenario YAML의 parametric_sweeps 정의
         ↓ ETL/실행
Sweep Job 생성 (sweep-job-{uuid})
         ↓ N회 반복
Evidence 1 ← sweep_value: 1.0
Evidence 2 ← sweep_value: 0.5
Evidence 3 ← sweep_value: 0.25
Evidence 4 ← sweep_value: 0.1
         ↓
DB에서 sweep_job_id로 그룹 쿼리 가능
```

### 15-3. Evidence의 sweep_context (v2.2 신규)

```yaml
# sim-uc-camera-recording-UHD60-HDR10-H265-A0-20260417-zoom0.5.yaml
id: sim-uc-camera-recording-UHD60-HDR10-H265-A0-20260417-zoom0.5
schema_version: "2.2"
kind: evidence.simulation

scenario_ref: uc-camera-recording
variant_ref: UHD60-HDR10-H265

execution_context:
  silicon_rev: A0
  sw_baseline_ref: sw-vendor-v1.2.3
  thermal: hot

# --- v2.2 신규: Sweep 그룹 메타 ---
sweep_context:
  sweep_job_id: sweep-job-20260417-014100-abc123
  sweep_definition_ref: zoom_sweep         # scenario의 parametric_sweeps.id
  sweep_axis: size_profile.transforms[1].crop_ratio
  sweep_value: 0.5
  sweep_index: 2                            # values[] 내 0-based index
  sweep_total_runs: 4

run:
  timestamp: "2026-04-17T01:42:30+09:00"
  tool: mmip_simulator
  source: calculated

# --- Aggregation (v2.2: sweep 내부 구조 명시) ---
aggregation:
  strategy: single_run_in_sweep             # 이 evidence 자체는 1회
  sweep_aggregation:                        # sweep 전체에 대한 통계 strategy
    strategy: per_sample_with_across_sweep_plot
    axis: sweep_value

kpi:
  total_power_mW: 2150
  peak_power_mW: 2480
  # ...
```

### 15-4. Sweep Job 메타 테이블

```yaml
# DB에만 존재 (YAML 아님)
# sweep_jobs 테이블 row 예시
{
  "id": "sweep-job-20260417-014100-abc123",
  "scenario_ref": "uc-camera-recording",
  "variant_ref": "UHD60-HDR10-H265",
  "sweep_definition_ref": "zoom_sweep",
  "sweep_axis": "size_profile.transforms[1].crop_ratio",
  "sweep_values": [1.0, 0.5, 0.25, 0.1],
  "total_runs": 4,
  "completed_runs": 4,
  "status": "completed",
  "launched_at": "2026-04-17T01:41:00+09:00",
  "completed_at": "2026-04-17T01:45:30+09:00",
  "launched_by": "YHJOO",
  "tool_version": "mmip_simulator-2.3.1"
}
```

### 15-5. Sweep × Aggregation 모순 방지 (v2.2 Extra)

2단 aggregation 명시:

```yaml
aggregation:
  # 개별 evidence 수준
  strategy: single_run_in_sweep            # 이 evidence 하나는 1회 실행

  # Sweep 전체 수준 (선택)
  sweep_aggregation:
    strategy: per_sample_with_across_sweep_plot
    # 의미: 각 sweep_value마다 단일 샘플, 전체는 sweep_value축 플롯
    axis: sweep_value                      # X축
    plot_metrics: [total_power_mW, peak_ddr_bw_gbps]  # Y축

  # 측정 반복이 있는 경우 (sweep × repeat)
  per_sweep_value_aggregation:
    strategy: mean_with_ci_95              # 각 zoom 값마다 5회 측정
    n: 5
```

### 15-6. DB 쿼리 예시

```sql
-- Zoom ratio별 power 곡선 (꺾은선 차트 데이터)
SELECT
    (sweep_context->>'sweep_value')::FLOAT AS zoom_ratio,
    (kpi->>'peak_power_mW')::FLOAT AS peak_power,
    (kpi->>'peak_ddr_bw_gbps')::FLOAT AS peak_bw
FROM evidence
WHERE sweep_context->>'sweep_job_id' = 'sweep-job-20260417-014100-abc123'
ORDER BY zoom_ratio;

-- 완료된 sweep job 목록
SELECT id, scenario_ref, variant_ref, total_runs, completed_runs
FROM sweep_jobs
WHERE status = 'completed'
  AND scenario_ref = 'uc-camera-recording';
```

---

## 16. Evidence Layer

### 16-1. v2.2 핵심 변경

| 필드 | v2.1 | v2.2 |
|------|------|------|
| `execution_context.sw_baseline` | string | **FK `sw_baseline_ref`** |
| `sweep_context` | ❌ | **추가** |
| `resolution_result` | hw만 | **hw + sw** |
| `resolution_result.violations` | ❌ | **추가** |
| `overall_feasibility` | ❌ | **추가** |

### 16-2. Simulation Evidence (v2.2)

```yaml
id: sim-uc-camera-recording-UHD60-HDR10-H265-A0-sw123-20260417
schema_version: "2.2"
kind: evidence.simulation

scenario_ref: uc-camera-recording
variant_ref: UHD60-HDR10-H265
project_ref: proj-A-exynos2500

execution_context:
  silicon_rev: A0
  sw_baseline_ref: sw-vendor-v1.2.3     # v2.2 FK
  thermal: hot
  ambient_temp_c: 35
  power_state: charging

# v2.2 신규 (sweep 일부인 경우만)
sweep_context:
  sweep_job_id: sweep-job-20260417-014100-abc123
  sweep_value: 0.5
  sweep_index: 2

resolution_result:
  hw_resolution:
    isp0:
      requested: { throughput_mpps: 498 }
      matched_mode: high_throughput
  sw_resolution:
    profile_ref: sw-vendor-v1.2.3
    required_features_check:
      - { feature: LLC_dynamic_allocation, status: PASS }
  overall_feasibility: production_ready
  violations: []

run:
  timestamp: "2026-04-17T01:41:00+09:00"
  tool: mmip_simulator
  tool_version: "2.3.1"
  writer: YHJOO
  git_commit: abc1234
  source: calculated

aggregation:
  strategy: single_run

kpi:
  total_power_mW: 2150
  peak_power_mW: 2480
  avg_ddr_bw_gbps: 13.8
  peak_ddr_bw_gbps: 17.2
  frame_latency_ms: 15.3

ip_breakdown:
  - ip: ip-isp-v12
    instance_index: 0
    power_mW: 780
    submodules:
      - { sub: ISP.TNR, power_mW: 320 }

artifacts:
  - { type: gantt_html, storage: minio, path: "...", sha256: "..." }
```

### 16-3. Measurement Evidence (v2.2 — provenance에 SW 구조화)

```yaml
id: meas-uc-camera-recording-UHD60-HDR10-H265-A0-sw123-20260417
schema_version: "2.2"
kind: evidence.measurement

scenario_ref: uc-camera-recording
variant_ref: UHD60-HDR10-H265

execution_context:
  silicon_rev: A0
  sw_baseline_ref: sw-vendor-v1.2.3
  thermal: hot

# --- Provenance (v2.2: SW 정보 구조화) ---
provenance:
  # HW
  device_id: "EVT0-S24-SN-1234"
  chamber_controlled: true
  chamber_temp_c: 25

  # SW (v2.2: sw_baseline_ref로 대체되지만 실측 시 세부 정보 기록)
  build_id: "S9280AAAA2"
  sw_baseline_ref: sw-vendor-v1.2.3     # 이미 execution_context에 있음
  runtime_sw_state:                      # 빌드 외의 런타임 정보
    kernel_loaded_sha: "9f3c21b"
    hal_loaded_version: "4.5.0"
    active_firmware:
      isp: "0x41"
      dsp: "0x22"

  # 계측
  collection_method: "perfetto+simpleperf+power_monitor"
  collection_tool_versions:
    perfetto: "v47.0"
  sample_count: 10
  duration_per_sample_s: 180
  confidence_level: 0.95

raw_artifacts:
  - { type: perfetto_trace, path: "...", sha256: "..." }

aggregation:
  strategy: mean_with_ci_95

kpi:
  total_power_mW:
    mean: 2150
    p95: 2240
    std: 45
    ci_95: [2120, 2180]
    n: 10
```

---

## 17. Decision Layer

v2.1 구조 유지하되 **attestation 필드 확장**.

### 17-1. Review (v2.2 — triple-track 추가)

```yaml
id: rev-uc-camera-recording-UHD60-HDR10-20260417
schema_version: "2.2"
kind: decision.review

scenario_ref: uc-camera-recording
variant_ref: UHD60-HDR10-H265
evidence_refs:
  - sim-...20260417
  - meas-...20260417

gate_result: WARN
auto_checks:
  - { rule: bw_threshold,      status: WARN, detail: "peak BW 17.2 > 15.0" }
  - { rule: known_issue_match, status: WARN, matched_issues: [iss-LLC-thrashing-0221] }
  - { rule: feasibility_check, status: PASS }

# --- v2.2: Triple-Track Attestation (섹션 18 참조) ---
attestation:
  approver_claim: "YHJOO"
  claim_at: "2026-04-17"
  git_attestation:
    commit_sha: "abc1234"
    commit_author_email: "yhjoo@company.internal"
    signed: true
  server_attestation:
    approved_by_auth: null               # API 서버가 주입
    auth_method: null
    auth_timestamp: null

decision: approved_with_waiver
waiver_ref: waiver-LLC-thrashing-UHD60-A0-20260417
rationale: >
  Mitigation 적용 예정. Silicon A1에서 재평가.

validation:
  last_validated_on: "2026-04-17"
  next_review_due: "2026-09-30"
  review_cycle: quarterly

review_scope:
  variant_scope:
    scenario_ref: uc-camera-recording
    variant_ref: UHD60-HDR10-H265
  execution_scope:
    silicon_rev: A0
    sw_baseline_ref: sw-vendor-v1.2.3    # v2.2 FK
    thermal: [hot, critical]
```

### 17-2. Issue (v2.2 — SW 회귀 추적)

```yaml
id: iss-LLC-thrashing-0221
schema_version: "2.2"
kind: decision.issue

metadata:
  title: "LLC thrashing at >55°C with TNR strong mode"
  severity: high
  status: resolved
  discovered_in: proj-A-exynos2500
  discovered_at: "2026-02-21"

  # --- v2.2 신규: SW 회귀 추적 ---
  sw_regression:
    discovered_in_sw: sw-vendor-v1.2.1
    last_good_sw: sw-vendor-v1.2.0       # 이전 SW에서는 문제 없음
    root_cause_sw_change:
      area: camera.llc_policy
      description: "LLC shared → per-IP 변경으로 TNR 할당 부족"
    fixed_in_sw: sw-vendor-v1.3.0        # 이 SW부터 해결

# --- Match Rule (v2.2: SW 조건 추가) ---
affects:
  - scenario_ref: uc-camera-recording
    match_rule:
      scope:
        project_ref: "*"
        soc_ref: soc-exynos2500
      all:
        - { axis: resolution, op: in, value: [UHD, 8K] }
        - { axis: thermal,    op: in, value: [hot, critical] }
      any:
        - { ip: ISP.TNR, field: mode, op: eq, value: strong }
        - { ip: ISP.DNS, field: mode, op: eq, value: strong }
      # v2.2 신규: SW 조건
      sw_conditions:
        any:
          - { sw_feature: LLC_dynamic_allocation, op: eq, value: disabled }
          - { sw_component: kernel.drivers.camera, op: matches, value: "exynos-cam-v[12]\\..*" }
      none:
        - { axis: power_state, op: eq, value: battery }

affects_ip:
  - { ip_ref: ip-isp-v12, submodule: ISP.TNR }
  - { ip_ref: ip-llc-v2 }

pmu_signature:
  - { counter: STALL_BACKEND_MEM, threshold: ">40%" }
  - { counter: L2D_CACHE_REFILL,  threshold: ">1M/s" }

resolution:
  fix_commit: abc1234
  fix_sw_ref: sw-vendor-v1.3.0           # v2.2 신규
  fix_description: "LLC allocation policy: per-IP allocation with TNR 4MB minimum"
  verified_in_evidence: sim-...20260417
  fix_date: "2026-03-05"
```

### 17-3. Waiver (v2.2 — triple-track)

```yaml
id: waiver-LLC-thrashing-UHD60-A0-20260417
schema_version: "2.2"
kind: decision.waiver

title: "LLC thrashing on UHD60 HDR10 with Silicon A0"
issue_ref: iss-LLC-thrashing-0221

scope:
  variant_scope:
    scenario_ref: uc-camera-recording
    match_rule:
      all:
        - { axis: resolution, op: eq, value: UHD }
        - { axis: fps,        op: eq, value: 60 }
        - { axis: hdr,        op: eq, value: HDR10 }
  execution_scope:
    all:
      - { axis: silicon_rev,      op: eq, value: A0 }
      - { axis: thermal,          op: in, value: [hot, critical] }
      - { axis: sw_baseline_ref,  op: in, value: [sw-vendor-v1.2.1, sw-vendor-v1.2.3] }

justification: >
  Mitigation: LLC allocation 2MB → 4MB.
  Fixed in sw-vendor-v1.3.0 (참조: iss-LLC-thrashing-0221).

# --- v2.2: Triple-Track Attestation ---
attestation:
  approver_claim: "LeeSR (chief architect)"
  claim_at: "2026-04-17"
  git_attestation:
    commit_sha: "def5678"
    commit_author_email: "leesr@company.internal"
    signed: true
  server_attestation:
    approved_by_auth: null               # API 주입
    auth_method: null
    auth_timestamp: null
    auth_session_id: null

approved_at: "2026-04-17"
expires_on: "2026-09-30"
status: pending_auth                     # pending_auth | approved | revoked | expired
review_cycle: quarterly
next_review_due: "2026-07-31"
```

---

## 18. Decision Integrity — Triple-Track Attestation (v2.2 신규)

### 18-1. 문제 인식

Waiver/Review는 프로세스적 효력을 가지므로 위변조 방지 필수. YAML 필드만으로는 불충분.

### 18-2. 3-Track 모델

```
┌─────────────────────────────────────┐
│ Track 1: Author Claim (YAML)         │  ← 참고용
│   approver_claim: "LeeSR"            │  ← 작성자가 기입
│   claim_at: "2026-04-17"             │
└──────────────────────────────────────┘
                ↓ Git commit
┌─────────────────────────────────────┐
│ Track 2: Git Attestation             │  ← 중간 증명
│   commit_sha, commit_author          │  ← Git hook이 채움
│   signed (GPG)                       │
└──────────────────────────────────────┘
                ↓ API 승인 요청
┌─────────────────────────────────────┐
│ Track 3: Server Attestation          │  ← 최종 권위
│   approved_by_auth (SSO)             │  ← API가 주입
│   auth_method, auth_timestamp        │
│   auth_session_id                    │
└─────────────────────────────────────┘
```

### 18-3. 승인 플로우

```
1. 작성자가 waiver-*.yaml 작성
   - approver_claim 기입
   - claim_at 기입
   - server_attestation 필드는 비움 (null)

2. Git commit
   - Git pre-commit hook이 파일 검증
   - commit_sha, signed 여부 자동 기록 (별도 DB 또는 post-commit)

3. 작성자가 API 호출: POST /api/waivers/{id}/approve
   - SSO 토큰 필요
   - API 서버가:
     a. SSO identity와 approver_claim 일치 확인
     b. Git commit signature 검증
     c. server_attestation 주입
     d. status: pending_auth → approved

4. DB에 최종 저장
   - YAML의 approver_claim은 참고
   - DB의 approved_by_auth가 진실
```

### 18-4. 필수 필드 정의

```yaml
attestation:
  # Track 1: 작성자 주장 (YAML)
  approver_claim: string                  # REQUIRED
  claim_at: ISO 8601 date                 # REQUIRED

  # Track 2: Git 증명 (Git hook 채움)
  git_attestation:
    commit_sha: string                    # REQUIRED after commit
    commit_author_email: string           # REQUIRED
    signed: boolean                       # GPG sign 여부
    committed_at: ISO 8601 datetime

  # Track 3: Server 증명 (API가 주입, YAML에선 null)
  server_attestation:
    approved_by_auth: string | null       # SSO subject id
    auth_method: enum | null              # sso | mfa | signed_jwt
    auth_timestamp: ISO 8601 | null
    auth_session_id: string | null
    ip_address: string | null
```

### 18-5. DB 스키마

```sql
CREATE TABLE waivers (
    id                          TEXT PRIMARY KEY,
    yaml_sha256                 TEXT NOT NULL,

    -- Track 1: Claim
    approver_claim              TEXT NOT NULL,
    claim_at                    DATE NOT NULL,

    -- Track 2: Git
    git_commit_sha              TEXT,
    git_commit_author_email     TEXT,
    git_signed                  BOOLEAN,

    -- Track 3: Server (권위)
    approved_by_auth            TEXT,     -- ⭐ 진실
    auth_method                 TEXT,
    auth_timestamp              TIMESTAMPTZ,
    auth_session_id             TEXT,

    status                      TEXT NOT NULL CHECK (status IN
                                ('pending_auth','approved','revoked','expired')),

    scope                       JSONB NOT NULL,
    justification               TEXT,
    expires_on                  DATE
);

-- 감사 로그 (append-only)
CREATE TABLE waiver_audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    waiver_id       TEXT NOT NULL,
    action          TEXT NOT NULL,         -- created | approved | revoked | expired
    actor           TEXT,
    actor_method    TEXT,
    timestamp       TIMESTAMPTZ DEFAULT NOW(),
    before_state    JSONB,
    after_state     JSONB
);

-- Review도 동일 구조
CREATE TABLE reviews (...);
CREATE TABLE review_audit_log (...);
```

### 18-6. Review에도 동일 적용

Review는 Waiver보다 약한 권위지만 동일 triple-track 적용 권장 (단, `signed`는 선택).

---

## 19. Matcher DSL

v2.1 Canonical AST 그대로 유지. v2.2에서 **SW 조건 필드 추가**.

### 19-1. 대상 필드 확장 (v2.2)

| 필드 경로 | 출처 | v2.2 신규? |
|----------|------|-----------|
| `axis.<n>` | design/execution axes | — |
| `ip.<instance>.mode` / `.field` | variant ip_requirements | — |
| `sw_feature.<n>` | sw profile feature_flags | ✅ |
| `sw_component.<path>` | sw profile components | ✅ |
| `sw_version.<component>` | sw profile version | ✅ |
| `scope.project_ref` / `.soc_ref` / `.sw_baseline_family` | scope | ✅ (sw 추가) |

### 19-2. 예시 (SW 조건 포함)

```yaml
match_rule:
  scope:
    project_ref: "*"
    soc_ref: soc-exynos2500
    sw_baseline_family: vendor

  all:
    - { axis: resolution, op: eq, value: UHD }
    - { axis: thermal,    op: in, value: [hot, critical] }

  sw_conditions:                          # v2.2 신규
    any:
      - { sw_feature: LLC_dynamic_allocation, op: eq, value: disabled }
      - { sw_component: kernel.drivers.camera,
          op: matches, value: "exynos-cam-v[12]\\..*" }
      - { sw_version: hal.camera, op: lt, value: "4.5" }

  any:
    - { ip: ISP.TNR, field: mode, op: eq, value: strong }

  none:
    - { axis: power_state, op: eq, value: battery }
```

---

## 20. Matcher DSL Syntax Sugar (v2.2 신규)

### 20-1. 원칙

- **Canonical AST는 DB 저장 형태 (single source of truth)**
- Syntax Sugar는 **YAML 작성 시에만 허용**
- ETL/API가 Sugar → AST 단방향 변환
- Validation 에러는 **AST 기준**으로 보고

### 20-2. Sugar 문법

```yaml
# --- Sugar 허용 ---
match_rule:
  all:
    resolution: UHD                       # sugar → {op: eq}
    fps: { $gte: 60 }                     # MongoDB-style
    thermal: { $in: [hot, critical] }
    codec: { $regex: "H\\.2\\d+" }

  any:
    "ip.ISP.TNR.mode": strong

  none:
    power_state: battery
```

### 20-3. Sugar → AST 매핑표

| Sugar | Canonical AST |
|-------|---------------|
| `field: value` | `{axis: field, op: eq, value: value}` |
| `field: "*"` | `{axis: field, op: exists, value: true}` |
| `field: { $eq: V }` | `{axis: field, op: eq, value: V}` |
| `field: { $ne: V }` | `{axis: field, op: ne, value: V}` |
| `field: { $in: [...] }` | `{axis: field, op: in, value: [...]}` |
| `field: { $nin: [...] }` | `{axis: field, op: not_in, value: [...]}` |
| `field: { $gte: N }` | `{axis: field, op: gte, value: N}` |
| `field: { $gt: N }` | `{axis: field, op: gt, value: N}` |
| `field: { $lte: N }` | `{axis: field, op: lte, value: N}` |
| `field: { $lt: N }` | `{axis: field, op: lt, value: N}` |
| `field: { $regex: "..." }` | `{axis: field, op: matches, value: "..."}` |
| `field: { $exists: true }` | `{axis: field, op: exists, value: true}` |
| `field: { $between: [A, B] }` | `{axis: field, op: between, value: [A, B]}` |

### 20-4. 변환 규칙

```python
# 의사 코드 (ETL 로직)
def sugar_to_ast(rule: dict) -> dict:
    if isinstance(rule, list):
        return [sugar_to_ast(r) for r in rule]

    ast = []
    for field, value in rule.items():
        axis_or_path = classify_field(field)  # axis / ip / sw_feature / ...

        if isinstance(value, dict) and any(k.startswith('$') for k in value):
            # MongoDB-style: { $gte: 60 }
            for op_key, op_val in value.items():
                op_name = op_key.lstrip('$')
                ast.append({**axis_or_path, 'op': op_name, 'value': op_val})
        elif value == "*":
            ast.append({**axis_or_path, 'op': 'exists', 'value': True})
        else:
            # 암묵적 eq
            ast.append({**axis_or_path, 'op': 'eq', 'value': value})

    return ast
```

### 20-5. 제약

| 규칙 | 이유 |
|------|------|
| Sugar와 AST 혼용 금지 | 한 rule 블록 내에서 일관성 |
| DB에는 AST만 저장 | Single source of truth |
| 에러 메시지는 AST 기준 | 디버깅 일관성 |
| API 응답은 AST로 | 구현자 혼란 방지 |
| 역변환 금지 | AST → Sugar 자동 변환 안 함 |

### 20-6. 전체 예시 (Sugar vs AST)

```yaml
# --- Sugar (YAML 작성자 친화) ---
match_rule:
  all:
    resolution: UHD
    fps: { $gte: 60 }
    thermal: { $in: [hot, critical] }
  sw_conditions:
    any:
      sw_feature.LLC_dynamic_allocation: disabled
```

```yaml
# --- Canonical AST (DB 저장) ---
match_rule:
  all:
    - { axis: resolution, op: eq, value: UHD }
    - { axis: fps,        op: gte, value: 60 }
    - { axis: thermal,    op: in, value: [hot, critical] }
  sw_conditions:
    any:
      - { sw_feature: LLC_dynamic_allocation, op: eq, value: disabled }
```

---

## 21. Review Gate Rules (v2.2 신규)

### 21-1. 별도 설정 파일 도입

v2.1까지는 Review 파일에 `auto_checks`가 하드코딩. v2.2부터는 **재사용 가능한 gate rule**을 별도 파일로.

### 21-2. 파일 구조

```
gate_rules/
├── rule-bw-threshold.yaml
├── rule-thermal-margin.yaml
├── rule-feasibility-check.yaml
├── rule-known-issue-match.yaml
├── rule-sw-compatibility.yaml         # v2.2 신규
└── rule-regression-check.yaml
```

### 21-3. Gate Rule 예시 — `rule-feasibility-check.yaml`

```yaml
id: rule-feasibility-check
schema_version: "2.2"
kind: decision.gate_rule

metadata:
  name: "Variant Feasibility Check"
  category: [feasibility]
  severity: high

# 언제 실행?
trigger:
  events: [on_evidence_register, on_variant_update]

# 어떤 variant에 적용?
applies_to:
  match:
    variant.severity: { $in: [heavy, critical] }

# 조건
condition:
  match:
    evidence.resolution_result.overall_feasibility: { $in: [infeasible] }

# 결과
action:
  gate_result: BLOCK
  message_template: |
    variant {{variant_ref}} marked infeasible.
    Violations: {{violation_summary.total}} items, {{violation_summary.fail_fast}} fail-fast.
  required_resolution: waiver_or_redesign
  escalation:
    notify: [architect, reviewer]
```

### 21-4. Gate Rule — `rule-sw-compatibility.yaml`

```yaml
id: rule-sw-compatibility
schema_version: "2.2"
kind: decision.gate_rule

metadata:
  name: "SW Compatibility Check"
  category: [compatibility, sw]

trigger:
  events: [on_evidence_register]

condition:
  match:
    evidence.resolution_result.sw_resolution.required_features_check:
      $any_item:
        status: FAIL

action:
  gate_result: WARN
  message_template: |
    SW feature requirement unmet for {{variant_ref}}.
    Check SW profile {{execution_context.sw_baseline_ref}}.
```

### 21-5. Gate Rule 적용 결과

Review 파일에는 rule ref만 기록:

```yaml
# rev-*.yaml
auto_checks:
  - rule_ref: rule-bw-threshold
    status: WARN
    detail: "peak BW 17.2 > 15.0 GBps"
  - rule_ref: rule-feasibility-check
    status: PASS
  - rule_ref: rule-sw-compatibility
    status: PASS
  - rule_ref: rule-known-issue-match
    status: WARN
    matched_issues: [iss-LLC-thrashing-0221]
```

---

## 22. DB 스키마 전략

v2.1 고정 스키마 + JSONB 유지. v2.2에서 **SW 테이블, sweep_jobs, gate_rules 추가**.

### 22-1. v2.2 추가 테이블

```sql
-- ============================================================
-- SW Catalog
-- ============================================================
CREATE TABLE sw_profiles (
    id              TEXT PRIMARY KEY,
    schema_version  TEXT NOT NULL,
    metadata        JSONB NOT NULL,
    components      JSONB NOT NULL,
    feature_flags   JSONB NOT NULL,
    compatibility   JSONB,
    yaml_sha256     TEXT NOT NULL
);

CREATE INDEX idx_sw_prof_features ON sw_profiles USING GIN (feature_flags);
CREATE INDEX idx_sw_prof_family ON sw_profiles((metadata->>'baseline_family'));

CREATE TABLE sw_components (
    id              TEXT PRIMARY KEY,
    category        TEXT CHECK (category IN ('hal','kernel','firmware')),
    version         TEXT NOT NULL,
    metadata        JSONB,
    capabilities    JSONB,
    feature_flags   JSONB
);

-- ============================================================
-- Sweep Jobs
-- ============================================================
CREATE TABLE sweep_jobs (
    id                      TEXT PRIMARY KEY,
    scenario_ref            TEXT NOT NULL,
    variant_ref             TEXT NOT NULL,
    sweep_definition_ref    TEXT NOT NULL,
    sweep_axis              TEXT NOT NULL,
    sweep_values            JSONB NOT NULL,
    total_runs              INT NOT NULL,
    completed_runs          INT DEFAULT 0,
    status                  TEXT CHECK (status IN ('launched','running','completed','failed','cancelled')),
    launched_at             TIMESTAMPTZ NOT NULL,
    completed_at            TIMESTAMPTZ,
    launched_by             TEXT,
    tool_version            TEXT
);

CREATE INDEX idx_sweep_jobs_scenario ON sweep_jobs(scenario_ref, variant_ref);

-- ============================================================
-- Gate Rules
-- ============================================================
CREATE TABLE gate_rules (
    id              TEXT PRIMARY KEY,
    schema_version  TEXT NOT NULL,
    metadata        JSONB NOT NULL,
    trigger         JSONB NOT NULL,
    applies_to      JSONB,
    condition       JSONB NOT NULL,
    action          JSONB NOT NULL,
    yaml_sha256     TEXT NOT NULL
);

-- ============================================================
-- Evidence 확장 (v2.2)
-- ============================================================
ALTER TABLE evidence ADD COLUMN sw_baseline_ref TEXT
    REFERENCES sw_profiles(id);
ALTER TABLE evidence ADD COLUMN sweep_job_id TEXT
    REFERENCES sweep_jobs(id);
ALTER TABLE evidence ADD COLUMN overall_feasibility TEXT;

-- Generated columns (hot path)
ALTER TABLE evidence ADD COLUMN sw_version_hint TEXT
    GENERATED ALWAYS AS (execution_context->>'sw_baseline_ref') STORED;
ALTER TABLE evidence ADD COLUMN sweep_value_hint TEXT
    GENERATED ALWAYS AS (sweep_context->>'sweep_value') STORED;

CREATE INDEX idx_ev_sw ON evidence(sw_version_hint);
CREATE INDEX idx_ev_sweep ON evidence(sweep_job_id);
CREATE INDEX idx_ev_feasibility ON evidence(overall_feasibility);

-- ============================================================
-- Decision 확장 (v2.2 — triple-track)
-- ============================================================
ALTER TABLE waivers ADD COLUMN git_commit_sha TEXT;
ALTER TABLE waivers ADD COLUMN git_commit_author_email TEXT;
ALTER TABLE waivers ADD COLUMN git_signed BOOLEAN;
ALTER TABLE waivers ADD COLUMN approved_by_auth TEXT;
ALTER TABLE waivers ADD COLUMN auth_method TEXT;
ALTER TABLE waivers ADD COLUMN auth_timestamp TIMESTAMPTZ;
ALTER TABLE waivers ADD COLUMN auth_session_id TEXT;

CREATE TABLE waiver_audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    waiver_id       TEXT NOT NULL,
    action          TEXT NOT NULL,
    actor           TEXT,
    actor_method    TEXT,
    timestamp       TIMESTAMPTZ DEFAULT NOW(),
    before_state    JSONB,
    after_state     JSONB
);
```

---

## 23. DB Table ↔ 파일명 매핑

| YAML prefix | Layer | DB Table | v2.2 변경 |
|-------------|-------|----------|----------|
| `soc-`, `ip-`, `sub-`, `conn-` | HW Capability | `soc_platforms`, `ip_catalog`, `ip_submodules` | 동일 |
| **`sw-`** | **SW Capability** | **`sw_profiles`** | **신규** |
| **`hal-`, `kernel-`, `fw-`** | **SW Capability** | **`sw_components`** | **신규** |
| `proj-` | — | `projects` | 동일 |
| `uc-` | Definition | `scenarios`, `scenario_variants` | `sw_requirements` 필드 |
| `sim-`, `meas-` | Evidence | `evidence` | `sw_baseline_ref`, `sweep_job_id`, violation fields |
| — (derived) | Evidence | **`sweep_jobs`** | **신규** |
| `rev-`, `waiver-` | Decision | `reviews`, `waivers` | triple-track attestation fields |
| `iss-` | Decision | `issues` | `sw_regression` 필드 |
| **`rule-`** | **Decision** | **`gate_rules`** | **신규** |
| — (derived) | — | `issue_variant_matches` (MV) | 동일 |

---

## 24. 마이그레이션 가이드 (v2.1 → v2.2)

### 24-1. Backward Compatibility

v2.2는 v2.1에 대해 **backward-compatible**. 신규 필드는 모두 optional.

### 24-2. 자동 변환

1. **`sw_baseline` 문자열 → SW profile 참조**
   - execution_context에 `sw_baseline: "vendor-v1.2.3"` 발견
   - → sw_profiles 테이블에 stub `sw-vendor-v1.2.3` 생성
   - → `sw_baseline_ref: sw-vendor-v1.2.3`로 변환
2. **Matcher AST → Sugar 변환**: 자동 변환 안 함 (작성자 선택)
3. **Schema version bump**: "2.1" → "2.2"

### 24-3. 수동 작업

1. **SW Catalog 구성**
   - 기존 `sw_baseline` 문자열 목록 수집
   - 각 SW profile 상세 정보 수집 (HAL 버전, kernel, FW, feature flags)
   - `sw_catalog/` 파일 작성
2. **Variant의 `sw_requirements` 추가**
   - 기존 variant에 필요한 SW feature 정리
   - `required_features`, `required_hal` 기입
3. **Violation Policy 명시**
   - production/exploration variant 분류
   - 각 variant에 `violation_policy` 블록 추가
4. **Waiver/Review Triple-track 전환**
   - 기존 Waiver는 `status: pending_auth`로 재표시
   - API 서버 구현 후 재승인 필요
5. **Gate Rules 파일 생성**
   - 기존 auto_checks 항목을 별도 rule 파일로 분리
6. **Issue SW 회귀 정보 보강**
   - 과거 이슈에 `discovered_in_sw`, `fixed_in_sw` 정보 복원

### 24-4. 단계별 Roadmap

```
Phase 1 (2-3주): SW Catalog 구축
  → 현재 운영 중인 SW profile 목록화
  → sw_catalog/*.yaml 작성
  → DB sw_profiles 테이블 생성

Phase 2 (2주): Scenario SW requirements 추가
  → 각 variant에 sw_requirements 기입
  → Resolver에 SW 매칭 로직 추가

Phase 3 (2-3주): Violation Policy + Gate Rules
  → variant에 violation_policy 분류
  → gate_rules/ 파일 생성
  → Review Gate 엔진 구현

Phase 4 (3-4주): Triple-track Attestation
  → Git hook 구현
  → API 서버 SSO 연동
  → Waiver/Review 재승인 flow

Phase 5 (1-2주): Sweep Job Tracking
  → sweep_jobs 테이블
  → sweep_context 자동 주입

Phase 6 (지속): Matcher DSL Sugar
  → 작성자 교육
  → Sugar → AST 파서 배포
```

---

## 25. 핵심 설계 원칙 요약

### 25-1. 3-경계선 (v2.2 확장 유지)

| 경계선 | v2.2 상태 |
|--------|----------|
| **Variant ≠ Instance** | 유지. sw_baseline_ref는 Instance 축 |
| **Capability ≠ Requirement** | **확장** — SW도 Capability |
| **Canonical ≠ Derived** | **강화** — Sugar→AST 단방향, sweep_jobs는 DB canonical |

### 25-2. v2.2 신규 원칙

| 원칙 | 효과 |
|------|------|
| **HW와 SW는 대칭 Capability** | SW도 쿼리/추적 대상 |
| **Resolver 실패는 명시 정책** | Production/Exploration 구분 |
| **Decision은 3-track 무결성** | 위변조 방지 + 감사 로그 |
| **Sweep은 Job으로 그룹화** | 분석 쿼리 가능 |
| **Matcher Sugar + Canonical AST** | UX + 엄격성 양립 |
| **Gate Rule은 재사용 자원** | Review 자동화 확장 |

### 25-3. 전체 원칙표

| 원칙 | 효과 |
|------|------|
| HW/SW/Scenario 디렉토리 분리 | 각 레이어 독립 진화 |
| IP 계층화 (ip + sub) | 복합 IP 관리 |
| 조건은 필드, 파일명 아님 | 파일 폭발 방지 |
| 파일명 = DB ID | ETL 자동화 |
| `*_ref` FK 명명 규칙 | 관계 자동 생성 |
| Design/Execution 축 분리 | Review scope 안정화 |
| Capability 추상 mode | Catalog 재사용성 |
| **SW Capability 대칭** | **SW 추적/쿼리** |
| Requirement → Capability resolver | Scenario 독립성 |
| **Violation Policy 명시** | **실패 처리 일관성** |
| Measurement provenance 필수 | 재현성 |
| Matcher formal semantics | 구현 일관성 |
| **Matcher Sugar** | **작성자 UX** |
| Derived는 DB materialized view | Single source of truth |
| **Decision triple-track** | **무결성 + 감사** |
| **Sweep job 그룹화** | **분석 쿼리** |
| **Gate rule 재사용** | **Review 자동화** |
| ISO 8601 날짜 통일 | DB 정렬/TTL |
| Variant 상속 DAG 검증 | 순환 방지 |
| Multi-instance IP 명시 | Dual-cam 표현 |
| Schema SemVer | 호환성 추적 |

### 25-4. 한 줄 요약

> **v2.1: 시나리오 = 구조(파일) + 의도(variant) + 실행(instance) + 판단(decision)**
> **v2.2: + HW/SW 대칭 Capability + 실패 정책 + 무결성 증명**

v2.2는 v2.1의 철학을 유지하면서 **실무 운영 가능한 완결성**을 확보합니다. SW Catalog로 회귀 추적, Violation Policy로 Exploration 허용, Triple-track으로 무결성 보장. 이 상태에서 Pydantic 모델 + DDL로 1:1 번역 가능합니다.

---

## 부록 A: v2.2 Breaking Changes 체크리스트

v2.2는 backward-compatible이지만, 완전한 v2.2 운영을 위해 필요한 작업:

| 항목 | 필수? | 자동 변환 | 수동 작업 |
|------|------|----------|----------|
| SW Catalog 구축 | 권장 | stub 생성 가능 | 실제 SW profile 정보 수집 |
| `sw_baseline` → `sw_baseline_ref` | 권장 | ✅ | — |
| variant에 `sw_requirements` | 선택 | ❌ | requirement 작성 |
| `violation_policy` 추가 | 권장 | ❌ | variant 분류 + policy |
| Evidence `resolution_result` 확장 | 선택 | ❌ | Resolver 업그레이드 필요 |
| Sweep에 `sweep_context` | 권장 | ⚠️ 미래 run만 | 과거 데이터 backfill |
| Triple-track attestation | 권장 | ❌ | API 서버 필요 |
| Gate Rules 분리 | 권장 | ⚠️ 간단한 경우 | 룰 재작성 |
| Issue에 `sw_regression` | 선택 | ❌ | 과거 이슈 SW 정보 조사 |
| Matcher Sugar 사용 | 선택 | ⚠️ 역변환은 ❌ | 파서 배포 후 선택적 사용 |
| `schema_version: "2.2"` | 권장 | ✅ | — |

---

## 부록 B: v2.1 → v2.2 파일별 변경 요약

| 파일 prefix | v2.1 → v2.2 주요 변경 |
|------------|---------------------|
| `soc-*.yaml` | 없음 |
| `ip-*.yaml` | 없음 |
| **`sw-*.yaml`** | **신규** |
| **`hal-*.yaml`, `kernel-*.yaml`, `fw-*.yaml`** | **신규** |
| `project.yaml` | `default_sw_profile_ref`, `tested_sw_profiles` |
| `uc-*.yaml` | variant에 `sw_requirements`, `violation_policy` |
| `sim-*.yaml` | `sw_baseline_ref`, `sweep_context`, `resolution_result.sw_resolution`, `overall_feasibility` |
| `meas-*.yaml` | 위와 동일 + `provenance.runtime_sw_state` |
| `rev-*.yaml` | `attestation.git_attestation`, `attestation.server_attestation`, rule_ref 기반 auto_checks |
| `waiver-*.yaml` | 위와 동일 + `status: pending_auth` |
| `iss-*.yaml` | `sw_regression`, `match_rule.sw_conditions` |
| **`rule-*.yaml`** | **신규 (gate rule)** |
