# Directory Structure

_Last updated: 2026-05-05_

## Root Layout

```
02_ScenarioDB/
├── src/scenario_db/          # 핵심 패키지 (설치 가능)
│   ├── api/                  # FastAPI 앱
│   │   ├── app.py            # create_app(), lifespan
│   │   ├── cache.py          # RuleCache
│   │   ├── deps.py           # get_db(), get_rule_cache()
│   │   ├── routers/          # capability, definition, evidence, decision, view, utility
│   │   └── schemas/          # Pydantic response 모델 (4 layer + common + view)
│   ├── db/                   # DB 레이어
│   │   ├── base.py           # DeclarativeBase, make_engine()
│   │   ├── session.py        # make_session_factory()
│   │   ├── jsonb_ops.py      # JSONB SQLAlchemy 표현식
│   │   ├── sql_matcher.py    # SQL 매처
│   │   ├── models/           # ORM 모델 (4 layer)
│   │   └── repositories/     # 쿼리 캡슐화 (4 layer)
│   ├── etl/                  # YAML → DB
│   │   ├── loader.py         # 디렉토리 스캔, LOAD_ORDER
│   │   └── mappers/          # 도메인별 upsert 함수 (4 layer)
│   ├── matcher/              # Rule 평가 엔진 (DB 없음)
│   │   ├── context.py        # MatcherContext
│   │   └── runner.py         # evaluate(rule, ctx)
│   ├── models/               # Pydantic 도메인 모델
│   │   ├── common.py         # BaseScenarioModel, 공통 타입
│   │   ├── capability/       # hw.py, sw.py
│   │   ├── definition/       # project.py, usecase.py
│   │   ├── evidence/         # simulation.py, measurement.py, ...
│   │   └── decision/         # gate_rule.py, issue.py, waiver.py, review.py
│   ├── view/                 # View projection
│   │   ├── service.py        # build_sample_level0(), project_level0/1/2()
│   │   └── layout.py         # 레이아웃 상수 (LANE_Y, STAGE_X 등)
│   └── config.py             # Settings (pydantic-settings)
├── dashboard/                # Streamlit UI (별도 의존 그룹)
│   ├── Home.py               # 멀티페이지 진입점
│   ├── pages/
│   │   └── 1_Pipeline_Viewer.py  # Level 0 Lane View
│   └── components/
│       ├── elk_graph_builder.py  # ELK 레이아웃 계산
│       ├── elk_viewer.py         # SVG 렌더링
│       ├── node_detail_panel.py  # 인스펙터 패널
│       ├── lane_layout.py        # 레인 레이아웃
│       └── viewer_theme.py       # 테마 상수
├── tests/
│   ├── unit/                 # pytest 기본 대상 (no external deps)
│   │   ├── fixtures/         # YAML 테스트 픽스처 (4 layer)
│   │   ├── matcher/          # matcher 단위 테스트
│   │   └── api/              # API 단위 테스트
│   └── integration/          # testcontainers PostgreSQL 필요
├── alembic/                  # DB 마이그레이션
│   └── versions/0001_initial_schema.py
├── demo/
│   ├── fixtures/             # 5개 디렉토리 (00_hw~04_decision)
│   └── notebooks/
├── scripts/
│   └── bench_matcher.py
├── pyproject.toml            # uv 패키지, 의존 그룹 (dev/notebook/dashboard)
└── docker-compose.yml        # PostgreSQL 컨테이너
```

## Key Files

| 파일 | 역할 |
|------|------|
| `src/scenario_db/api/app.py` | FastAPI 앱 생성, lifespan |
| `src/scenario_db/api/cache.py` | RuleCache (메모리 캐시) |
| `src/scenario_db/db/base.py` | DeclarativeBase, make_engine() |
| `src/scenario_db/db/jsonb_ops.py` | JSONB SQLAlchemy 표현식 |
| `src/scenario_db/etl/loader.py` | ETL 진입점, MAPPER_REGISTRY |
| `src/scenario_db/matcher/runner.py` | Rule 평가기 |
| `src/scenario_db/view/service.py` | ViewResponse 조립 |
| `src/scenario_db/config.py` | pydantic-settings 싱글턴 |
| `dashboard/Home.py` | Streamlit 멀티페이지 진입점 |
| `pyproject.toml` | uv 패키지 관리 |
| `docker-compose.yml` | PostgreSQL 컨테이너 |

## Where to Add New Code

| 작업 | 위치 |
|------|------|
| 새 도메인 엔티티 | `models/{layer}/`, `db/models/{layer}.py`, `etl/mappers/{layer}.py`, `api/routers/{layer}.py` |
| 새 Matcher 연산자 | `src/scenario_db/matcher/runner.py` (`_eval_leaf` match 블록) |
| 새 JSONB SQL 표현식 | `src/scenario_db/db/jsonb_ops.py` |
| 새 Dashboard 페이지 | `dashboard/pages/N_PageName.py` (Streamlit 자동 인식) |
| 테스트 픽스처 | `tests/unit/fixtures/{layer}/` |
