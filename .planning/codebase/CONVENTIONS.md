# Code Conventions

_Last updated: 2026-05-05_

## Naming

### Files
- Snake_case for all Python source files: `hw.py`, `sql_matcher.py`, `gate_rule.py`
- Test files prefixed with `test_`: `test_capability_models.py`, `test_smoke.py`
- Module grouping by layer: `capability/hw.py`, `capability/sw.py` (not flat naming)

### Classes
- PascalCase: `IpCatalog`, `SocPlatform`, `SwProfile`, `BaseScenarioModel`, `PagedResponse`
- Pydantic models follow domain noun phrases: `OperatingMode`, `SubmoduleRef`, `IpHierarchy`
- SQLAlchemy ORM models share names with Pydantic models but live in `db/models/` (name shadowing is intentional and resolved via explicit imports)

### Functions / Methods
- Snake_case: `load_yaml_dir`, `make_session_factory`, `validate_sort_column`, `apply_sort`
- Private helpers prefixed with `_`: `_check_submodules_only_for_composite`, `_resolve_field`, `_eval_leaf`
- Fixtures and helpers in tests: `_mock_session_empty()`, `_fake_model()`, `_make_query_stub()`

### Variables / Fields
- Snake_case throughout
- Reserved Python keyword workarounds: `from_` (alias `"from"`) and `metadata_` (alias `"metadata"`) — see `src/scenario_db/models/definition/usecase.py` and `src/scenario_db/db/models/capability.py`
- Unit suffixes mandated by parent CLAUDE.md: `_ps` (picoseconds), `_bytes`, `_dva`, `_GBps`

### Type Aliases (Annotated primitives)
- Defined in `src/scenario_db/models/common.py`
- PascalCase alias names: `SchemaVersion`, `DocumentId`, `InstanceId`, `FeatureFlagValue`
- Pattern: `TypeName = Annotated[str, StringConstraints(pattern=r"...")]`

### Enum Values
- All enums subclass `StrEnum` (not plain `Enum`): easier YAML serialization
- Enum member names match their string value exactly: `Severity.light = "light"`, `ViolationAction.FAIL_FAST = "FAIL_FAST"`
- SCREAMING_SNAKE_CASE used for action-like enums (`FAIL_FAST`, `WARN_AND_CAP`); lowercase for state-like enums (`light`, `medium`, `production`)

## File Organization

### Source layout
```
src/scenario_db/
├── models/            # Pydantic v2 domain models (4-layer)
│   ├── common.py      # Shared types: BaseScenarioModel, DocumentId, Enums
│   ├── capability/    # hw.py, sw.py
│   ├── definition/    # project.py, usecase.py
│   ├── evidence/      # common.py, measurement.py, simulation.py, resolution.py
│   └── decision/      # common.py, gate_rule.py, issue.py, review.py, waiver.py
├── db/
│   ├── base.py        # SQLAlchemy declarative Base
│   ├── session.py     # make_session_factory()
│   ├── models/        # ORM models (mirror of domain layer names)
│   ├── repositories/  # DB query logic per layer
│   └── jsonb_ops.py   # JSONB query helpers
├── api/
│   ├── app.py         # create_app() factory + lifespan
│   ├── routers/       # FastAPI routers per layer
│   ├── schemas/       # Pydantic response schemas per layer
│   ├── deps.py        # FastAPI dependency providers
│   ├── pagination.py  # PagedResponse, validate_sort_column, apply_sort
│   ├── cache.py       # RuleCache
│   ├── exceptions.py  # register_handlers()
│   └── validators.py  # Domain-specific query param validation
├── etl/
│   ├── loader.py      # load_yaml_dir()
│   └── mappers/       # YAML → ORM mappers per layer
├── matcher/           # Issue-match rule engine
│   ├── context.py     # MatcherContext dataclass
│   └── runner.py      # evaluate() — recursive rule evaluator
└── config.py          # pydantic-settings Settings
```

### Test layout mirrors source structure
```
tests/
├── conftest.py                  # Root: marker declarations only
├── unit/
│   ├── test_capability_models.py
│   ├── test_definition_models.py
│   ├── test_evidence_models.py
│   ├── test_decision_models.py
│   ├── api/
│   │   ├── test_smoke.py        # All GET endpoints, mock DB
│   │   └── test_pagination.py
│   └── matcher/
│       ├── test_context.py
│       └── test_runner.py
├── integration/
│   ├── conftest.py              # Docker + Alembic + ETL setup
│   ├── test_api_capability.py
│   ├── test_api_definition.py
│   ├── test_api_evidence.py
│   ├── test_api_decision.py
│   ├── test_cache.py
│   ├── test_jsonb_queries.py
│   ├── test_matched_issues.py
│   └── test_phase_c_jsonb.py
```

## Patterns & Idioms

### Pydantic models — universal rules
- All models inherit `BaseScenarioModel` from `src/scenario_db/models/common.py`
- `BaseScenarioModel` enforces `model_config = ConfigDict(extra="forbid")` project-wide
- Exception: `IpRequirementSpec` uses `extra="allow"` for open-ended IP-specific fields
- Discriminated unions use `Literal` kind field: `kind: Literal["ip"]`, `kind: Literal["soc"]`

```python
class IpCatalog(BaseScenarioModel):
    id: DocumentId
    schema_version: SchemaVersion
    kind: Literal["ip"]
    category: str
    hierarchy: IpHierarchy
    capabilities: IpCapabilities
    rtl_version: str | None = None
    compatible_soc: list[DocumentId] = Field(default_factory=list)
```

### Cross-field validators
- Use `@model_validator(mode="after")` for post-init constraint checks
- Validator method names start with `_check_`: `_check_submodules_only_for_composite`
- Raise `ValueError` (Pydantic wraps into `ValidationError`); error messages state what failed

```python
@model_validator(mode="after")
def _check_submodules_only_for_composite(self) -> IpHierarchy:
    if self.type == "simple" and self.submodules:
        raise ValueError("simple hierarchy must not declare submodules")
    if self.type == "composite" and not self.submodules:
        raise ValueError("composite hierarchy must declare at least one submodule")
    return self
```

### Field aliases for YAML keys
- When YAML key conflicts with Python keyword, use `Field(alias="from")` and rename field to `from_`
- When YAML key conflicts with SQLAlchemy ORM reserved name, rename to `metadata_` with `Column("metadata", ...)` to preserve the DB column name
- `by_alias=True` must be passed on `model_dump()` calls for round-trip fidelity

### YAML round-trip pattern
- Standard helper `roundtrip(model_cls, path, **dump_kwargs)` in each test module
- Pattern: `load_yaml → model_validate → model_dump(exclude_none=True) → model_validate → assert obj == obj2`

### SQLAlchemy ORM
- Raw columns only — no ORM relationships (`relationship()`) defined
- JSONB columns store entire sub-objects as serialized Python dicts
- `yaml_sha256` column on every ORM model for idempotent ETL (content-hash dedup)
- Column alignment: columns visually aligned with spaces for readability in model files

### FastAPI routers
- One router per domain layer: `capability.router`, `definition.router`, `evidence.router`, `decision.router`
- All routers mounted under `/api/v1` prefix in `app.py`
- Health endpoints (`/health/live`, `/health/ready`) on a separate `health_router` without the prefix
- `PagedResponse[T]` generic used as `response_model` for all list endpoints
- Query parameters follow: `limit`, `offset`, `sort_by`, `sort_dir` — consistent across all list endpoints

### Dependency injection
- `get_db` yields a `Session` from `app.state.session_factory`
- `get_rule_cache` returns `app.state.rule_cache`
- Tests override both via `app.dependency_overrides` — never patch at the module level

### Error handling
- HTTP 404: raise `NoResultFound` from SQLAlchemy (mapped to 404 by exception handler in `exceptions.py`)
- HTTP 400: raise `HTTPException(status_code=400, detail=...)` directly in router or validator
- Domain errors from Pydantic: `ValidationError` (422 by FastAPI default)
- Error messages must state what failed / what was expected / what was received (parent CLAUDE.md rule)

## Type Annotations

### Required everywhere
- All function signatures have type hints — no bare untyped functions
- Return types declared including `None`: `def foo() -> None:`
- `from __future__ import annotations` at top of every source file (deferred evaluation)

### Annotated constraints
- Constrained primitives defined as module-level `TypeAlias` in `common.py`, not inline
- Use `Annotated[str, StringConstraints(...)]` not `constr()` (Pydantic v2 style)

```python
DocumentId = Annotated[
    str,
    StringConstraints(
        pattern=r"^(soc|ip|sub|sw|hal|kernel|fw|conn|proj|uc|sim|meas|rev|waiver|iss|rule)-[a-zA-Z0-9][a-zA-Z0-9.\-]*$"
    ),
]
```

### Generic types
- `PagedResponse[T]` uses `Generic[T]` + `TypeVar` for typed API responses
- `FeatureFlagValue: TypeAlias = bool | str | int` — explicit union instead of `Any`

### Optional fields
- `X | None = None` syntax (not `Optional[X]`): `rtl_version: str | None = None`
- `list[X] = Field(default_factory=list)` for empty-list defaults (never `= []`)

### Imports
- All imports at module top — no local imports except inside `@pytest.fixture` or circular-break scenarios
- Circular imports resolved via lazy import inside `engine` fixture in integration conftest
- Standard order: `from __future__ import annotations` → stdlib → third-party → local
