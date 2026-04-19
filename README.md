# ScenarioDB — Mobile SoC Multimedia IP Scenario Database

SoC 멀티미디어 IP의 **HW 능력 · SW 호환성 · 시뮬레이션 결과 · 리뷰 승인**을 하나의 PostgreSQL DB로 통합 관리하는 시스템입니다.

> **Demo story**: `sw-vendor-v1.2.3`의 LLC Thrashing 버그가 SW `v1.3.0`에서 수정됐을 때,  
> feature flag 1개 변경이 전력 −8.5%, DDR 대역폭 −13.3%, 레이턴시 −11.8% 개선으로 이어진 과정을 데이터로 추적합니다.

---

## Architecture

4-Layer 분리 원칙으로 설계됐습니다.

```
Capability   →  Definition  →  Evidence   →  Decision
(HW/SW 스펙)    (시나리오 정의)  (시뮬/측정 결과)  (리뷰·승인·웨이버)
```

```
02_ScenarioDB/
├── src/scenario_db/
│   ├── models/              # Pydantic v2 — YAML 스키마 검증
│   │   ├── capability/      # SoC, IP, SW Profile, SW Component
│   │   ├── definition/      # Project, Scenario, Variant
│   │   ├── evidence/        # Simulation, Measurement, Resolution
│   │   └── decision/        # Review, Waiver, Issue, GateRule
│   ├── db/
│   │   ├── models/          # SQLAlchemy ORM (PostgreSQL JSONB)
│   │   └── session.py
│   └── etl/
│       ├── loader.py        # YAML → DB upsert (SHA256 skip)
│       └── mappers/         # 레이어별 mapper
├── alembic/                 # DB 마이그레이션
├── demo/
│   ├── fixtures/            # 시드 데이터 (LLC Before/After 스토리)
│   │   ├── 00_hw/           # SoC + IP (5개)
│   │   ├── 01_sw/           # SW Profile + Component (3개)
│   │   ├── 02_definition/   # Project + Usecase (2개)
│   │   ├── 03_evidence/     # Simulation + Measurement (3개)
│   │   └── 04_decision/     # Issue / Waiver / Review / Rule (6개)
│   └── notebooks/           # Jupyter 분석 노트북
│       ├── 00_setup.ipynb
│       ├── 02_ip_usage_analysis.ipynb
│       └── 03_sw_regression_story.ipynb
└── tests/                   # pytest (124 tests)
```

---

## Quick Start

### 1. 사전 요구사항

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)
- Docker Desktop

### 2. DB 기동

```bash
docker compose up -d
# PostgreSQL: localhost:5432
# pgAdmin:    http://localhost:5050  (admin@scenariodb.local / admin)
```

### 3. 의존성 설치 및 마이그레이션

```bash
uv sync
uv run alembic upgrade head
```

### 4. 시드 데이터 임포트

```bash
uv run python -m scenario_db.etl.loader demo/fixtures/
# Expected: 20/20 files loaded successfully
```

### 5. Jupyter 노트북 실행

```bash
uv run --group notebook jupyter lab demo/notebooks/
```

### 6. 테스트

```bash
uv run pytest tests/ -v
# 124 tests — DB 없이 Pydantic 모델만 검증
```

---

## DB Schema

| 테이블 | 레이어 | 설명 |
|--------|--------|------|
| `soc_platforms` | Capability | SoC 플랫폼 메타데이터 |
| `ip_catalog` | Capability | IP 블록 (ISP / MFC / DPU / LLC 등) |
| `sw_profiles` | Capability | SW Baseline (feature_flags JSONB + GIN 인덱스) |
| `sw_components` | Capability | HAL / Kernel / Firmware 컴포넌트 |
| `projects` | Definition | 프로젝트 |
| `scenarios` | Definition | 유스케이스 시나리오 |
| `scenario_variants` | Definition | 설계 조건 변형 (해상도 / HDR / 코덱 조합) |
| `evidence` | Evidence | 시뮬레이션·측정 결과 (Computed: `sw_version_hint`) |
| `sweep_jobs` | Evidence | 파라미터 스윕 배치 |
| `gate_rules` | Decision | 자동 게이트 규칙 |
| `issues` | Decision | 알려진 버그 이슈 |
| `waivers` | Decision | 예외 승인 (Triple-Track 지원) |
| `reviews` | Decision | 리뷰 게이트 결과 |

---

## Demo Notebooks

### `00_setup.ipynb`
DB 연결 검증, 테이블 row count, sample row 확인, LLC Before/After KPI 빠른 비교.

### `02_ip_usage_analysis.ipynb`
"DB가 없으면 grep으로 수 시간 걸릴 질문을 1초에 답한다" — 5개 분석:
- S1: IP 카테고리별 운영 주파수 분포
- S2: ISP 서브모듈 전력 분해 (sw-v1.2.3 vs v1.3.0)
- S3: IP × Resolution 사용 매트릭스 (히트맵)
- S4: ISP 처리량 헤드룸 분석
- S5: LLC 경합 타임라인

### `03_sw_regression_story.ipynb`
**30초 안에 "LLC 버그 수정 → 전력 감소" 를 데이터로 증명**:
- S1: Feasibility 분포 + KPI 그룹 바 차트
- S2: 5-KPI Dumbbell Chart (before/after 페어 비교)
- S3: Root Cause 카드 (Issue · Root Cause · Measured Impact)
- S4: Review Gate 흐름 + 30초 요약 대시보드

| KPI | v1.2.3 (before) | v1.3.0 (after) | Delta |
|-----|----------------|---------------|-------|
| Total Power | 2,350 mW | 2,150 mW | **−8.5%** |
| Peak Power | 2,680 mW | 2,480 mW | **−7.5%** |
| Avg DDR BW | 15 GBps | 13 GBps | **−13.3%** |
| Frame Latency | 17 ms | 15 ms | **−11.8%** |
| Gate Result | ⚠️ WARN | ✅ PASS | |

---

## Tech Stack

| 구분 | 기술 |
|------|------|
| 언어 | Python 3.11 |
| 스키마 검증 | Pydantic v2 |
| ORM | SQLAlchemy 2.0 |
| DB | PostgreSQL 16 (JSONB + GIN 인덱스) |
| 마이그레이션 | Alembic |
| 패키지 관리 | uv |
| 노트북 | JupyterLab + pandas / matplotlib / plotly |
| 테스트 | pytest |

---

## Environment Variables

`.env` 파일을 프로젝트 루트에 생성:

```env
DATABASE_URL=postgresql+psycopg2://scenario_user:scenario_pass@localhost:5432/scenario_db
```

`.env`는 `.gitignore`에 포함되어 있어 커밋되지 않습니다.
