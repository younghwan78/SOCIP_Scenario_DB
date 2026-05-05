# Technology Stack

**Analysis Date:** 2026-05-05

## Languages

**Primary:**
- Python 3.11+ (runtime pinned via `requires-python = ">=3.11"` in `pyproject.toml`)
  - Backend API: `src/scenario_db/`
  - ETL pipeline: `src/scenario_db/etl/`
  - Dashboard: `dashboard/`

**Secondary:**
- SQL (PostgreSQL dialect) — JSONB operator expressions via SQLAlchemy text/func (`src/scenario_db/db/jsonb_ops.py`)

## Runtime

**Environment:**
- CPython 3.11.15 (via `uv` managed venv)

**Package Manager:**
- `uv` (PEP 517 build backend: `uv_build>=0.11.2,<0.12.0`)
- Lockfile: `uv.lock` — present and committed

**Dependency groups:**
- `[project.dependencies]` — runtime (API + ETL)
- `[dependency-groups] dev` — test tooling
- `[dependency-groups] notebook` — Jupyter analysis
- `[dependency-groups] dashboard` — Streamlit viewer

## Frameworks

**API / Web:**
- FastAPI 0.136.0 — REST API server (`src/scenario_db/api/app.py`)
- Uvicorn 0.44.0 (with `[standard]` extras) — ASGI server

**Data Validation:**
- Pydantic v2 (2.13.2) — all domain models (`src/scenario_db/models/`)
- pydantic-settings 2.0+ — environment/config via `Settings` class (`src/scenario_db/config.py`)

**ORM / Database:**
- SQLAlchemy 2.0.49 — ORM + Core; `DeclarativeBase` used (`src/scenario_db/db/base.py`)
- Alembic 1.18.4 — schema migrations (`alembic/`, `alembic.ini`)

**Dashboard / UI:**
- Streamlit 1.56.0 — multi-page web viewer (`dashboard/Home.py`, `dashboard/pages/`)

**YAML Parsing:**
- PyYAML 6.0.3+ — YAML scenario file loading (`src/scenario_db/etl/loader.py`)

**Testing:**
- pytest 9.0.3 — test runner (`tests/`)
- httpx 0.27+ — async HTTP client for FastAPI test client (`tests/api/`)
- testcontainers[postgresql] 0.28.1 — Docker-based PostgreSQL for integration tests (`tests/integration/`)

## Key Dependencies

**Critical (runtime):**
- `psycopg2-binary` 2.9.11 — PostgreSQL driver (synchronous; used by SQLAlchemy)
- `pydantic` 2.13.2 — all model validation; `model_config = ConfigDict(extra='forbid')` enforced project-wide
- `fastapi` 0.136.0 — REST API contract (29+ GET endpoints, `/api/v1/` prefix)

**Dashboard extras:**
- `streamlit` 1.56.0
- `requests` 2.31+ — HTTP calls from dashboard to API

**Notebook extras (analysis only):**
- `polars` or `pandas` 2.0+ — data analysis
- `plotly` 5.20+ — visualization
- `networkx` 3.0+ — graph analysis
- `jupyterlab` 4.0+ — interactive notebooks (`demo/notebooks/`)

## Configuration

**Environment:**
- Settings loaded via `pydantic-settings` from env vars and `.env` file (`src/scenario_db/config.py`)
- Key env vars:
  - `SCENARIO_DB_DATABASE_URL` (or `DATABASE_URL` fallback) — PostgreSQL DSN
  - `SCENARIO_DB_API_PORT` — default 8000
  - `SCENARIO_DB_CORS_ORIGINS` — default includes `localhost:8501` (Streamlit), `localhost:3000`
  - `SCENARIO_DB_DB_POOL_SIZE` — default 10
  - `SCENARIO_DB_DB_MAX_OVERFLOW` — default 20
- Env prefix: `SCENARIO_DB_`

**Build:**
- `pyproject.toml` — single source of truth for all deps and tool config
- `pytest` config in `[tool.pytest.ini_options]`: `testpaths = ["tests/unit"]` (default; integration tests separate)
- Streamlit config: `.streamlit/config.toml` (theme + server settings)

## Platform Requirements

**Development:**
- Docker (for `docker-compose.yml` PostgreSQL + pgAdmin)
- `uv` package manager
- Python 3.11+

**Production:**
- ASGI server: `uvicorn` (via `uv run uvicorn scenario_db.api.app:app`)
- PostgreSQL 16 (Docker image: `postgres:16`)
- Streamlit dashboard run separately: `uv run --group dashboard streamlit run dashboard/Home.py`

---

*Stack analysis: 2026-05-05*
