# External Integrations

**Analysis Date:** 2026-05-05

## APIs & External Services

**Internal REST API (self-hosted):**
- ScenarioDB API — FastAPI application serving mobile SoC multimedia scenario data
  - Base URL: `http://localhost:8000/api/v1/`
  - Auth: None (read-only public API; CORS-restricted to localhost)
  - Routers: `capability`, `definition`, `evidence`, `decision`, `view`
  - Health endpoints: `GET /health/live`, `GET /health/ready`
  - Implementation: `src/scenario_db/api/app.py`

**Dashboard → API:**
- Streamlit dashboard calls the FastAPI backend via HTTP (`requests` library)
- Dashboard entry: `dashboard/Home.py`
- API consumer: `dashboard/pages/1_Pipeline_Viewer.py`
- Default API origin expected at `http://localhost:8000`

## Data Storage

**Databases:**
- **PostgreSQL 16** (primary store)
  - Docker image: `postgres:16`
  - DB name: `scenario_db`
  - User: `scenario_user` (defined in `docker-compose.yml`)
  - Connection env var: `SCENARIO_DB_DATABASE_URL` or `DATABASE_URL`
  - Connection string format: `postgresql://scenario_user:<pass>@localhost:5432/scenario_db`
  - ORM client: SQLAlchemy 2.0 (`src/scenario_db/db/session.py`, `src/scenario_db/db/base.py`)
  - JSONB columns used for: `design_conditions`, `execution_axes`, `feature_flags` (queried via `src/scenario_db/db/jsonb_ops.py`)
  - Migrations: Alembic (`alembic/versions/0001_initial_schema.py`)
  - Pool config: `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`, `pool_recycle=3600`

- **SQLite** (fallback/test only)
  - Used when `DATABASE_URL` is not set; default: `sqlite:///:memory:`
  - Configured in `src/scenario_db/config.py` (`lifespan` skips pool args for SQLite)

**File Storage:**
- YAML scenario files — local filesystem only
  - Source: project YAML files conforming to v2.2 schema (`scenario-db-yaml-design-v2.2.md`)
  - ETL reads YAML dir → loads into PostgreSQL (`src/scenario_db/etl/loader.py`)
  - Demo fixtures: `demo/fixtures/`

**Caching:**
- In-memory `RuleCache` — `GateRule` and `Issue` rows preloaded at startup
  - Implementation: `src/scenario_db/api/cache.py`
  - Stored on `app.state.rule_cache`; no Redis or external cache

## Authentication & Identity

**Auth Provider:**
- None — API is read-only, no authentication layer implemented
- CORS middleware restricts origins to `localhost:8501` and `localhost:3000` by default (`src/scenario_db/api/app.py`)

## Monitoring & Observability

**Health Checks:**
- `GET /health/live` — liveness probe (FastAPI up)
- `GET /health/ready` — readiness probe (DB connectivity check)
- Implementation: `src/scenario_db/api/routers/utility.py`

**Logging:**
- Python stdlib `logging` module — no third-party logger (e.g., structlog, loguru)
- Log level configured via `SCENARIO_DB_LOG_LEVEL` env var (default: `INFO`)
- ETL loader uses `logger = logging.getLogger(__name__)` pattern

**Error Tracking:**
- None (no Sentry, Datadog, etc.)

## CI/CD & Deployment

**Hosting:**
- Local / self-hosted only (no cloud deployment config detected)
- Docker Compose for local dev: `docker-compose.yml` (PostgreSQL + pgAdmin)

**CI Pipeline:**
- None detected (no `.github/`, `.gitlab-ci.yml`, etc.)

**Database Admin:**
- pgAdmin 4 — web UI for PostgreSQL inspection
  - URL: `http://localhost:5050`
  - Default login: `admin@scenariodb.local` / `admin`
  - Service defined in `docker-compose.yml`

## Testing Infrastructure

**Integration Tests:**
- `testcontainers[postgresql]` 0.28.1 — spins up ephemeral PostgreSQL Docker container
  - Config: `tests/integration/conftest.py`
  - Marker: `@pytest.mark.integration`
  - Separate from unit tests (unit tests run without Docker)

**API Tests:**
- `httpx` — FastAPI `TestClient` wrapper for endpoint tests
  - Location: `tests/api/`
  - Tests: `test_api_capability.py`, `test_api_definition.py`, `test_api_evidence.py`, `test_api_decision.py`

## Webhooks & Callbacks

**Incoming:** None

**Outgoing:** None

## Environment Configuration

**Required env vars (production):**
- `SCENARIO_DB_DATABASE_URL` — full PostgreSQL DSN (e.g., `postgresql://user:pass@host:5432/scenario_db`)

**Optional env vars:**
- `DATABASE_URL` — legacy alias for `SCENARIO_DB_DATABASE_URL`
- `SCENARIO_DB_API_PORT` — default `8000`
- `SCENARIO_DB_LOG_LEVEL` — default `INFO`
- `SCENARIO_DB_CORS_ORIGINS` — JSON list of allowed origins
- `SCENARIO_DB_DB_POOL_SIZE` — default `10`
- `SCENARIO_DB_DB_MAX_OVERFLOW` — default `20`

**Secrets location:**
- `.env` file (local, not committed) — loaded automatically by `pydantic-settings`

---

*Integration audit: 2026-05-05*
