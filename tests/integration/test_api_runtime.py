"""Runtime API (graph/resolve/gate) + view mode 분기 통합 테스트."""
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

# WR-06: VARIANT_ID is hard-coded and must match the demo ETL fixture
# (data/fixtures/demo/uc-camera-recording.yaml → variants[*].id).
# Future improvement: discover this id dynamically via a conftest fixture
# that calls GET /api/v1/scenarios/{SCENARIO_ID}/variants after ETL.
SCENARIO_ID = "uc-camera-recording"
VARIANT_ID = "UHD60-HDR10-H265"
BASE = f"/api/v1/scenarios/{SCENARIO_ID}/variants/{VARIANT_ID}"


def test_graph_returns_200(api_client: TestClient):
    resp = api_client.get(f"{BASE}/graph")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("scenario_id", "variant_id", "pipeline", "ip_catalog", "issues", "waivers", "reviews"):
        assert key in data, f"응답에 '{key}' 키 없음"
    assert data["scenario_id"] == SCENARIO_ID
    assert data["variant_id"] == VARIANT_ID


def test_graph_404(api_client: TestClient):
    resp = api_client.get("/api/v1/scenarios/no-such-id/variants/no-such-vid/graph")
    assert resp.status_code == 404


def test_resolve_returns_200(api_client: TestClient):
    resp = api_client.get(f"{BASE}/resolve")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("ip_resolutions", "sw_resolutions", "unresolved_requirements", "warnings"):
        assert key in data, f"응답에 '{key}' 키 없음"


def test_resolve_404(api_client: TestClient):
    resp = api_client.get("/api/v1/scenarios/no-such-id/variants/no-such-vid/resolve")
    assert resp.status_code == 404


def test_gate_returns_200(api_client: TestClient):
    resp = api_client.get(f"{BASE}/gate")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("status", "matched_rules", "matched_issues", "applicable_waivers", "missing_waivers"):
        assert key in data, f"응답에 '{key}' 키 없음"
    assert data["status"] in {"PASS", "WARN", "BLOCK", "WAIVER_REQUIRED"}


def test_gate_404(api_client: TestClient):
    resp = api_client.get("/api/v1/scenarios/no-such-id/variants/no-such-vid/gate")
    assert resp.status_code == 404


def test_view_architecture_mode(api_client: TestClient):
    resp = api_client.get(
        f"/api/v1/scenarios/{SCENARIO_ID}/variants/{VARIANT_ID}/view",
        params={"level": 0, "mode": "architecture"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "architecture"
    assert data["scenario_id"] == SCENARIO_ID
    assert data["variant_id"] == VARIANT_ID
    assert "nodes" in data


def test_view_topology_mode_returns_200(api_client: TestClient):
    """topology mode가 04-03 구현 완료 후 200을 반환한다 (이전 501 → 200으로 업데이트)."""
    resp = api_client.get(
        f"/api/v1/scenarios/{SCENARIO_ID}/variants/{VARIANT_ID}/view",
        params={"level": 0, "mode": "topology"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "topology"


def test_view_architecture_404(api_client: TestClient):
    resp = api_client.get(
        "/api/v1/scenarios/no-such-id/variants/no-such-vid/view",
        params={"level": 0, "mode": "architecture"},
    )
    assert resp.status_code == 404
