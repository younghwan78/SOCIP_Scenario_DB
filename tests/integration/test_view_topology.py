"""Level 0 topology mode 통합 테스트 (VIEW-03).

conftest.py의 api_client fixture를 재사용.
ETL 완료 + PostgreSQL testcontainer 전제.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

# uc-camera-recording 시나리오의 실제 variant id
# (tests/integration/test_view_projection.py와 동일)
#
# WR-06: VARIANT_ID is hard-coded here and must match the demo ETL fixture
# (data/fixtures/demo/uc-camera-recording.yaml → variants[*].id).
# If the fixture YAML changes this id, all tests below will return 404.
# Future improvement: dynamically discover the variant id via
#   GET /api/v1/scenarios/{SCENARIO_ID}/variants
# in a conftest fixture so tests are resilient to fixture renaming.
SCENARIO_ID = "uc-camera-recording"
VARIANT_ID = "UHD60-HDR10-H265"


class TestTopologyMode:
    def test_topology_view_returns_200(self, api_client):
        """topology mode view 요청이 200을 반환한다."""
        r = api_client.get(
            f"/api/v1/scenarios/{SCENARIO_ID}/variants/{VARIANT_ID}/view",
            params={"level": 0, "mode": "topology"},
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_topology_view_has_sw_nodes(self, api_client):
        """topology ViewResponse에 SW 노드(layer in app/framework/hal/kernel)가 포함된다."""
        r = api_client.get(
            f"/api/v1/scenarios/{SCENARIO_ID}/variants/{VARIANT_ID}/view",
            params={"level": 0, "mode": "topology"},
        )
        assert r.status_code == 200
        data = r.json()
        sw_layers = {"app", "framework", "hal", "kernel"}
        sw_nodes = [n for n in data["nodes"] if n["data"]["layer"] in sw_layers]
        assert len(sw_nodes) > 0, (
            f"No SW nodes in topology view. "
            f"Nodes: {[n['data']['layer'] for n in data['nodes']]}"
        )

    def test_topology_view_has_control_edges(self, api_client):
        """topology ViewResponse에 SW→HW control 엣지가 포함된다."""
        r = api_client.get(
            f"/api/v1/scenarios/{SCENARIO_ID}/variants/{VARIANT_ID}/view",
            params={"level": 0, "mode": "topology"},
        )
        assert r.status_code == 200
        data = r.json()
        control_edges = [e for e in data["edges"] if e["data"]["flow_type"] == "control"]
        assert len(control_edges) > 0, (
            "No control edges in topology view — sw_stack ip_ref linkage may be missing"
        )

    def test_topology_mode_field(self, api_client):
        """ViewResponse.mode가 'topology'이다."""
        r = api_client.get(
            f"/api/v1/scenarios/{SCENARIO_ID}/variants/{VARIANT_ID}/view",
            params={"level": 0, "mode": "topology"},
        )
        assert r.status_code == 200
        assert r.json()["mode"] == "topology"

    def test_architecture_mode_still_works(self, api_client):
        """topology 구현 후에도 architecture mode가 정상 동작한다 (회귀 테스트)."""
        r = api_client.get(
            f"/api/v1/scenarios/{SCENARIO_ID}/variants/{VARIANT_ID}/view",
            params={"level": 0, "mode": "architecture"},
        )
        assert r.status_code == 200
        data = r.json()
        # architecture mode에는 hw 노드가 존재해야 함
        hw_nodes = [n for n in data["nodes"] if n["data"]["layer"] == "hw"]
        assert len(hw_nodes) > 0, "architecture mode: no hw nodes found"

    def test_sw_stack_node_ids_in_topology(self, api_client):
        """sw_stack에 정의된 node id가 topology ViewResponse에 포함된다."""
        r = api_client.get(
            f"/api/v1/scenarios/{SCENARIO_ID}/variants/{VARIANT_ID}/view",
            params={"level": 0, "mode": "topology"},
        )
        assert r.status_code == 200
        node_ids = {n["data"]["id"] for n in r.json()["nodes"]}
        # uc-camera-recording.yaml sw_stack에 정의된 id들 (04-01 Task 2에서 추가)
        expected_ids = {"app-camera", "fw-cam-svc", "hal-camera", "ker-v4l2"}
        assert expected_ids.issubset(node_ids), (
            f"Missing sw_stack nodes: {expected_ids - node_ids}"
        )
