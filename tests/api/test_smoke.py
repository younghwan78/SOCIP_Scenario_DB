"""
API smoke test — FastAPI dependency override + MagicMock (DB 없이 실행).

전략:
  - get_db: MagicMock session 반환 (query().filter_by().one_or_none() = None)
  - get_rule_cache: 빈 RuleCache(loaded=True)
  - app.state.* 직접 주입

커버리지:
  - 전체 GET 엔드포인트 2xx / 4xx 응답 검증
  - PagedResponse 구조 검증
  - /health 응답 구조
  - 404 동작, 400 validation, 501 stubs
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from scenario_db.api.app import create_app
from scenario_db.api.cache import RuleCache
from scenario_db.api.deps import get_db, get_rule_cache


# ---------------------------------------------------------------------------
# Mock session 헬퍼
# ---------------------------------------------------------------------------

def _mock_session_empty() -> MagicMock:
    """query(...).filter_by(...).one_or_none() → None, count() → 0, all() → []"""
    session = MagicMock()
    query_mock = MagicMock()
    query_mock.filter_by.return_value = query_mock
    query_mock.filter.return_value = query_mock
    query_mock.join.return_value = query_mock
    query_mock.order_by.return_value = query_mock
    query_mock.offset.return_value = query_mock
    query_mock.limit.return_value = query_mock
    query_mock.one_or_none.return_value = None
    query_mock.first.return_value = None
    query_mock.all.return_value = []
    query_mock.count.return_value = 0
    session.query.return_value = query_mock
    session.execute.return_value = MagicMock()
    session.close = MagicMock()
    return session


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    app = create_app()

    mock_session = _mock_session_empty()

    # lifespan을 no-op으로 교체 (DB 연결 없이 테스트)
    @asynccontextmanager
    async def _noop_lifespan(a):
        a.state.engine = None
        a.state.session_factory = lambda: mock_session
        a.state.rule_cache = RuleCache(loaded=True)
        a.state.start_time = time.time()
        yield

    app.router.lifespan_context = _noop_lifespan

    def _override_db():
        yield mock_session

    def _override_cache():
        return RuleCache(loaded=True)

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_rule_cache] = _override_cache

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert "rule_cache" in body
    assert "uptime_s" in body


# ---------------------------------------------------------------------------
# Capability
# ---------------------------------------------------------------------------

def test_list_soc_platforms_200(client):
    r = client.get("/api/v1/soc-platforms")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert body["total"] == 0
    assert body["has_next"] is False


def test_get_soc_platform_404(client):
    r = client.get("/api/v1/soc-platforms/nonexistent")
    assert r.status_code == 404


def test_list_ip_catalog_200(client):
    r = client.get("/api/v1/ip-catalog")
    assert r.status_code == 200


def test_list_ip_catalog_invalid_category_400(client):
    r = client.get("/api/v1/ip-catalog?category=INVALID")
    assert r.status_code == 400


def test_list_ip_catalog_valid_category_200(client):
    r = client.get("/api/v1/ip-catalog?category=ISP")
    assert r.status_code == 200


def test_list_sw_profiles_200(client):
    r = client.get("/api/v1/sw-profiles")
    assert r.status_code == 200


def test_list_sw_profiles_valid_flag_200(client):
    r = client.get("/api/v1/sw-profiles?feature_flag=LLC_per_ip_partition:enabled")
    assert r.status_code == 200


def test_list_sw_profiles_invalid_flag_400(client):
    r = client.get("/api/v1/sw-profiles?feature_flag=UNKNOWN_FLAG:enabled")
    assert r.status_code == 400


def test_list_sw_profiles_bad_format_400(client):
    r = client.get("/api/v1/sw-profiles?feature_flag=nocolon")
    assert r.status_code == 400


def test_list_sw_components_200(client):
    r = client.get("/api/v1/sw-components")
    assert r.status_code == 200


def test_list_sw_components_invalid_category_400(client):
    r = client.get("/api/v1/sw-components?category=unknown")
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Definition
# ---------------------------------------------------------------------------

def test_list_projects_200(client):
    r = client.get("/api/v1/projects")
    assert r.status_code == 200


def test_get_project_404(client):
    r = client.get("/api/v1/projects/nonexistent")
    assert r.status_code == 404


def test_list_scenarios_200(client):
    r = client.get("/api/v1/scenarios")
    assert r.status_code == 200


def test_get_scenario_404(client):
    r = client.get("/api/v1/scenarios/nonexistent")
    assert r.status_code == 404


def test_list_variants_for_unknown_scenario_404(client):
    r = client.get("/api/v1/scenarios/nonexistent/variants")
    assert r.status_code == 404


def test_get_variant_404(client):
    r = client.get("/api/v1/scenarios/s1/variants/v1")
    assert r.status_code == 404


def test_matched_issues_404(client):
    r = client.get("/api/v1/variants/nonexistent/v1/matched-issues")
    assert r.status_code == 404


def test_list_all_variants_200(client):
    r = client.get("/api/v1/variants")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

def test_list_evidence_200(client):
    r = client.get("/api/v1/evidence")
    assert r.status_code == 200


def test_get_evidence_404(client):
    r = client.get("/api/v1/evidence/nonexistent")
    assert r.status_code == 404


def test_evidence_summary_200(client):
    r = client.get("/api/v1/evidence/summary")
    assert r.status_code == 200


def test_evidence_summary_invalid_groupby_400(client):
    r = client.get("/api/v1/evidence/summary?groupby=bad_col")
    assert r.status_code == 400


def test_compare_evidence_200(client):
    r = client.get("/api/v1/compare/evidence?variant=v1&sw1=sw-v1&sw2=sw-v2")
    assert r.status_code == 200


def test_compare_variants_200(client):
    r = client.get("/api/v1/compare/variants?ref1=s1::v1&ref2=s2::v2")
    assert r.status_code == 200


def test_compare_variants_bad_ref_400(client):
    r = client.get("/api/v1/compare/variants?ref1=bad&ref2=s2::v2")
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------

def test_list_reviews_200(client):
    r = client.get("/api/v1/reviews")
    assert r.status_code == 200


def test_get_review_404(client):
    r = client.get("/api/v1/reviews/nonexistent")
    assert r.status_code == 404


def test_list_issues_200(client):
    r = client.get("/api/v1/issues")
    assert r.status_code == 200


def test_get_issue_404(client):
    r = client.get("/api/v1/issues/nonexistent")
    assert r.status_code == 404


def test_list_waivers_200(client):
    r = client.get("/api/v1/waivers")
    assert r.status_code == 200


def test_get_waiver_404(client):
    r = client.get("/api/v1/waivers/nonexistent")
    assert r.status_code == 404


def test_list_gate_rules_200(client):
    r = client.get("/api/v1/gate-rules")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Pagination 파라미터 전달 검증
# ---------------------------------------------------------------------------

def test_pagination_structure(client):
    r = client.get("/api/v1/evidence?limit=10&offset=5")
    assert r.status_code == 200
    body = r.json()
    assert body["limit"] == 10
    assert body["offset"] == 5
    assert isinstance(body["has_next"], bool)


# ---------------------------------------------------------------------------
# 501 stubs
# ---------------------------------------------------------------------------

def test_stub_generate_yaml_501(client):
    r = client.post("/api/v1/variants/generate-yaml")
    assert r.status_code == 501


def test_stub_create_variant_501(client):
    r = client.post("/api/v1/scenarios/s1/variants")
    assert r.status_code == 501


def test_stub_submit_review_501(client):
    r = client.post("/api/v1/scenarios/s1/variants/v1/review")
    assert r.status_code == 501


def test_stub_etl_trigger_501(client):
    r = client.post("/api/v1/admin/etl/trigger")
    assert r.status_code == 501
