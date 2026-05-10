"""service.py _projection_to_view_response() 단위 테스트 (VIEW-02)."""
import pytest
from scenario_db.view.service import _projection_to_view_response, CATEGORY_TO_LANE


SAMPLE_PROJECTION = {
    "scenario_id": "uc-test",
    "variant_id":  "v-test",
    "project_name": "Test Project",
    "pipeline": {
        "nodes": [
            {"id": "csis0", "ip_ref": "ip-csis-v8"},
            {"id": "isp0",  "ip_ref": "ip-isp-v12"},
            {"id": "mfc",   "ip_ref": "ip-mfc-v14"},
        ],
        "edges": [
            {"from": "csis0", "to": "isp0", "type": "OTF"},
            {"from": "isp0",  "to": "mfc",  "type": "M2M"},
        ],
    },
    "ip_catalog": [
        {"id": "ip-csis-v8",  "category": "camera"},
        {"id": "ip-isp-v12",  "category": "camera"},
        {"id": "ip-mfc-v14",  "category": "codec"},
    ],
}


def test_all_nodes_assigned_hw_lane():
    """camera/codec category → hw lane."""
    view = _projection_to_view_response(SAMPLE_PROJECTION)
    for node in view.nodes:
        assert node.data.layer == "hw", (
            f"Node {node.data.id} has layer {node.data.layer}, expected hw"
        )


def test_x_coordinates_increase_with_topology():
    """topological sort → csis0(0) → isp0(1) → mfc(2); x좌표 단조 증가."""
    view = _projection_to_view_response(SAMPLE_PROJECTION)
    pos = {n.data.id: n.position["x"] for n in view.nodes}
    assert pos["csis0"] < pos["isp0"] < pos["mfc"], (
        f"Expected csis0 < isp0 < mfc in x, got {pos}"
    )


def test_y_coordinates_use_lane_y():
    """hw lane 노드의 y좌표가 LANE_Y['hw']와 일치한다."""
    from scenario_db.view.layout import LANE_Y
    view = _projection_to_view_response(SAMPLE_PROJECTION)
    for node in view.nodes:
        assert node.position["y"] == LANE_Y["hw"], (
            f"Node {node.data.id} y={node.position['y']}, expected {LANE_Y['hw']}"
        )


def test_edges_converted():
    """pipeline edges가 EdgeElement로 변환된다."""
    view = _projection_to_view_response(SAMPLE_PROJECTION)
    assert len(view.edges) == 2
    edge_types = {e.data.flow_type for e in view.edges}
    assert "OTF" in edge_types
    assert "M2M" in edge_types


def test_no_stub_positions():
    """position이 (0.0, 0.0) stub이 아니다."""
    view = _projection_to_view_response(SAMPLE_PROJECTION)
    stub_count = sum(
        1 for n in view.nodes
        if n.position["x"] == 0.0 and n.position["y"] == 0.0
    )
    assert stub_count == 0, f"{stub_count} nodes still have stub position (0,0)"


def test_category_to_lane_mapping():
    """CATEGORY_TO_LANE 상수가 올바른 값을 가진다."""
    assert CATEGORY_TO_LANE["camera"]  == "hw"
    assert CATEGORY_TO_LANE["codec"]   == "hw"
    assert CATEGORY_TO_LANE["display"] == "hw"
    assert CATEGORY_TO_LANE["memory"]  == "hw"


def test_isolated_node_gets_stage_0():
    """edge가 없는 isolated node는 stage_index 0 (x가 > LANE_LABEL_W)."""
    proj = {
        "scenario_id": "uc-test",
        "variant_id":  "v-test",
        "pipeline": {
            "nodes": [{"id": "llc", "ip_ref": "ip-llc-v2"}],
            "edges": [],
        },
        "ip_catalog": [{"id": "ip-llc-v2", "category": "memory"}],
    }
    view = _projection_to_view_response(proj)
    assert len(view.nodes) == 1
    from scenario_db.view.layout import LANE_LABEL_W
    assert view.nodes[0].position["x"] > LANE_LABEL_W


def test_unknown_category_falls_back_to_hw(caplog):
    """ip_catalog에 없는 ip_ref → category="" → 'hw' fallback + warning 로그."""
    import logging
    proj = {
        "scenario_id": "uc-test",
        "variant_id":  "v-test",
        "pipeline": {
            "nodes": [{"id": "unknown-ip", "ip_ref": "ip-unknown-v1"}],
            "edges": [],
        },
        "ip_catalog": [],  # empty catalog — no lookup possible
    }
    with caplog.at_level(logging.WARNING, logger="scenario_db.view.service"):
        view = _projection_to_view_response(proj)
    assert len(view.nodes) == 1
    assert view.nodes[0].data.layer == "hw"
    # WR-01: unknown category must emit a warning, not silently fall back
    assert any("Unknown ip_catalog category" in r.message for r in caplog.records), (
        "Expected a WARNING for unknown ip_catalog category, but none was emitted"
    )


def test_empty_pipeline_returns_empty_view():
    """빈 pipeline → nodes/edges 모두 비어있는 ViewResponse."""
    proj = {
        "scenario_id": "uc-empty",
        "variant_id":  "v-empty",
        "pipeline": {"nodes": [], "edges": []},
        "ip_catalog": [],
    }
    view = _projection_to_view_response(proj)
    assert view.nodes == []
    assert view.edges == []
