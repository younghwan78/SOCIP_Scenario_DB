# Testing

_Last updated: 2026-05-05_

## Test Structure

2-tier 구조:

```
tests/
├── unit/                     # pytest 기본 대상 (no external deps)
│   ├── conftest.py           # session-scope fixtures
│   ├── fixtures/             # YAML 테스트 픽스처 (4 layer)
│   │   ├── 00_hw/
│   │   ├── 01_sw/
│   │   ├── 02_definition/
│   │   ├── 03_evidence/
│   │   └── 04_decision/
│   ├── matcher/              # Matcher 단위 테스트
│   └── api/                  # API 단위 테스트 (MagicMock)
└── integration/              # testcontainers PostgreSQL 필요
    └── conftest.py           # pg → engine → session fixture 체인
```

## Test Types

### Unit Tests (no external deps)
- Pydantic 모델 round-trip: YAML → 모델 → dict → YAML
- Matcher rule 평가: `MatcherContext` + `evaluate()` 순수 Python
- API smoke test: `MagicMock` DB 의존성 주입 (`app.dependency_overrides`)

### Integration Tests (testcontainers)
- ETL 로드 후 DB 조회 검증
- API end-to-end (실제 PostgreSQL)
- Session-scope fixture 체인: `pg → engine → session → rule_cache → api_client`

## How to Run

```bash
# Unit tests (기본)
uv run pytest

# Integration tests (PostgreSQL 필요)
uv run pytest -m integration

# 특정 레이어만
uv run pytest tests/unit/api/

# 상세 출력
uv run pytest -v

# Coverage
uv run pytest --cov=src/scenario_db
```

## Key Fixture Patterns

### Pydantic Round-trip
```python
def test_round_trip(yaml_path):
    raw = yaml.safe_load(yaml_path.read_text())
    model = MyModel.model_validate(raw)
    assert model.model_dump(mode="json") == raw
```

### Pydantic ValidationError 매칭
```python
with pytest.raises(ValidationError) as exc_info:
    MyModel.model_validate(bad_data)
assert "field_name" in str(exc_info.value)
```

### Parametrize 패턴
```python
@pytest.mark.parametrize("fixture_file", list(FIXTURES_DIR.glob("*.yaml")))
def test_all_fixtures(fixture_file):
    ...
```

## Configuration (pyproject.toml)

```toml
[tool.pytest.ini_options]
testpaths = ["tests/unit"]
markers = [
    "integration: requires running PostgreSQL (testcontainers)",
    "slow: slow-running tests",
]
```

## Coverage Status

- Phase 1 (Capability Layer): 45 tests — all pass
- Phase A (PostgreSQL/ETL): 통합 테스트 포함
- Phase B Week 1 (FastAPI): 209 tests — all pass
- Dashboard 컴포넌트: 테스트 없음 (UI — manual verification)
