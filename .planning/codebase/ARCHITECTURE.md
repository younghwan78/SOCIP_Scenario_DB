# Architecture

_Last updated: 2026-05-05_

## Overview

5개 레이어가 수직으로 쌓이는 구조:

```
Dashboard (Streamlit) → View Projection → FastAPI / ETL Loader → DB Layer (SQLAlchemy) → PostgreSQL
                                                                       ↕
                                                                Matcher Engine (pure Python)
```

## Layers / Components

### 4-Domain 분리 (Capability / Definition / Evidence / Decision)

| Domain | 핵심 ORM 모델 | Pydantic 모델 위치 |
|--------|---------------|--------------------|
| Capability | `SocPlatform`, `IpCatalog`, `SwProfile`, `SwComponent` | `src/scenario_db/models/capability/` |
| Definition | `Project`, `Scenario`, `ScenarioVariant` | `src/scenario_db/models/definition/` |
| Evidence | `Evidence`, `SweepJob` | `src/scenario_db/models/evidence/` |
| Decision | `GateRule`, `Issue`, `Waiver`, `Review` | `src/scenario_db/models/decision/` |

### API Layer
- FastAPI 앱 (`api/app.py`) — lifespan으로 RuleCache 초기화
- Routers: capability, definition, evidence, decision, view, utility
- Schemas: Pydantic response 모델 (4 layer + common + view)

### ETL Layer
- YAML → DB 로드 (`etl/loader.py`)
- FK 의존 순서 `LOAD_ORDER` + SAVEPOINT per file
- 도메인별 upsert 함수 (`etl/mappers/`)

### Matcher Engine
- DB 없는 순수 Python Rule 평가기
- `MatcherContext` — 도트-경로 접근
- SQL push-down (`jsonb_ops.py`) + Python fallback (`matcher/runner.py`)

### View Projection
- `view/service.py` — ViewResponse 조립
- `project_level0(db=None)` → sample data (Phase C — DB 연동 stub)

### Dashboard (Streamlit)
- `dashboard/Home.py` — 멀티페이지 진입점
- ELK 레이아웃 계산 + SVG 렌더링 (Cytoscape 대체)

## Data Flow

```
YAML fixtures
     ↓ ETL Loader (LOAD_ORDER, SAVEPOINT)
PostgreSQL (JSONB-heavy + Promoted Columns)
     ↓ SQLAlchemy ORM + Repositories
FastAPI Routers → Pydantic Response Schemas
     ↓
View Service (Level 0/1/2 projection)
     ↓
Streamlit Dashboard (ELK SVG)
```

## Key Design Patterns

- **JSONB-heavy schema** + Promoted Columns (`Computed`) for query optimization
- **RuleCache**: 앱 시작 시 Issue+GateRule 메모리 로드 (exponential backoff 재시도)
- **3-경계선 원칙**:
  1. Variant ≠ Instance (design_axes vs execution_axes)
  2. Capability ≠ Requirement (HW/SW 추상 mode vs scenario 요구사항)
  3. Canonical ≠ Derived (YAML authored vs DB materialized)
- **Discriminated Union**: Literal kind 필드 사용
- **Pydantic v2**: `model_config = ConfigDict(extra='forbid')` 전체 적용

## Key Files

- `src/scenario_db/api/app.py` — FastAPI 앱 생성, lifespan(RuleCache 초기화)
- `src/scenario_db/etl/loader.py` — ETL 진입점, MAPPER_REGISTRY
- `src/scenario_db/matcher/runner.py` — match_rule 평가기
- `src/scenario_db/matcher/context.py` — MatcherContext (도트-경로 접근)
- `src/scenario_db/db/jsonb_ops.py` — JSONB SQL 표현식 빌더
- `src/scenario_db/view/service.py` — ViewResponse 조립
- `src/scenario_db/config.py` — pydantic-settings 싱글턴
