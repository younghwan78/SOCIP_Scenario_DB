"""service.py _projection_to_view_response() 단위 테스트 (VIEW-02/03)."""
import pytest
from scenario_db.view.service import (
    _projection_to_view_response,
    _sw_stack_to_view_response,
    CATEGORY_TO_LANE,
)


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


def test_unknown_category_falls_back_to_hw():
    """ip_catalog에 없는 ip_ref → category="" → 'hw' fallback + warning 로그."""
    from unittest.mock import patch
    import scenario_db.view.service as svc_mod

    proj = {
        "scenario_id": "uc-test",
        "variant_id":  "v-test",
        "pipeline": {
            "nodes": [{"id": "unknown-ip", "ip_ref": "ip-unknown-v1"}],
            "edges": [],
        },
        "ip_catalog": [],  # empty catalog — no lookup possible
    }
    with patch.object(svc_mod._logger, "warning") as mock_warn:
        view = _projection_to_view_response(proj)
    assert len(view.nodes) == 1
    assert view.nodes[0].data.layer == "hw"
    # WR-01: unknown category must emit a warning, not silently fall back
    assert mock_warn.called, "Expected _logger.warning() for unknown ip_catalog category"
    assert "Unknown ip_catalog category" in mock_warn.call_args[0][0]


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


# ---------------------------------------------------------------------------
# G2: _sw_stack_to_view_response() 단위 테스트 (VIEW-03)
# ---------------------------------------------------------------------------

SW_STACK_PROJECTION = {
    "scenario_id": "uc-sw-test",
    "variant_id":  "v-sw-test",
    "project_name": "SW Stack Test",
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
        "sw_stack": [
            {"id": "ker-v4l2",   "label": "V4L2 Driver",  "layer": "kernel",    "ip_ref": "csis0"},
            {"id": "ker-mfc-drv","label": "MFC Driver",   "layer": "kernel",    "ip_ref": "mfc"},
            {"id": "hal-camera", "label": "Camera HAL",   "layer": "hal"},
            {"id": "fw-cam-svc", "label": "CameraService","layer": "framework"},
            {"id": "app-camera", "label": "Camera App",   "layer": "app"},
        ],
    },
    "ip_catalog": [
        {"id": "ip-csis-v8",  "category": "camera"},
        {"id": "ip-isp-v12",  "category": "camera"},
        {"id": "ip-mfc-v14",  "category": "codec"},
    ],
}

SW_LAYERS = {"app", "framework", "hal", "kernel"}


def test_sw_stack_result_contains_sw_nodes():
    """sw_stack 섹션의 노드들이 SW 레이어(app/framework/hal/kernel)에 포함되어야 한다."""
    view = _sw_stack_to_view_response(SW_STACK_PROJECTION)
    sw_node_layers = {n.data.layer for n in view.nodes if n.data.layer in SW_LAYERS}
    assert sw_node_layers, (
        f"Expected SW layer nodes in view.nodes, but got layers: "
        f"{[n.data.layer for n in view.nodes]}"
    )
    # 5개 SW 노드 모두 포함
    sw_node_ids = {n.data.id for n in view.nodes if n.data.layer in SW_LAYERS}
    expected_sw_ids = {"ker-v4l2", "ker-mfc-drv", "hal-camera", "fw-cam-svc", "app-camera"}
    assert expected_sw_ids == sw_node_ids, (
        f"Expected SW node ids {expected_sw_ids}, got {sw_node_ids}"
    )


def test_sw_stack_ip_ref_generates_control_edge():
    """ip_ref가 있는 sw_stack 노드 → HW 노드로 control 타입 엣지가 생성된다."""
    view = _sw_stack_to_view_response(SW_STACK_PROJECTION)
    # ker-v4l2 → csis0 (control), ker-mfc-drv → mfc (control)
    control_edges = [
        e for e in view.edges
        if e.data.flow_type == "control"
        and e.data.source in {"ker-v4l2", "ker-mfc-drv"}
    ]
    assert len(control_edges) >= 2, (
        f"Expected >=2 SW→HW control edges, got {[(e.data.source, e.data.target) for e in view.edges]}"
    )
    # 구체적으로 ker-v4l2 → csis0 엣지 확인
    v4l2_to_csis = [e for e in control_edges if e.data.source == "ker-v4l2" and e.data.target == "csis0"]
    assert v4l2_to_csis, "Expected edge ker-v4l2 → csis0 with flow_type='control'"


def test_sw_stack_node_id_collision_with_hw_is_skipped():
    """SW 노드 id가 HW 노드 id와 충돌하면 skip된다 (CR-03 guard)."""
    collision_proj = {
        "scenario_id": "uc-collision",
        "variant_id":  "v-col",
        "pipeline": {
            "nodes": [
                {"id": "csis0", "ip_ref": "ip-csis-v8"},
            ],
            "edges": [],
            "sw_stack": [
                # id "csis0"는 HW 노드 id와 충돌 → skip되어야 함
                {"id": "csis0", "label": "Duplicate CSIS", "layer": "kernel"},
                {"id": "ker-safe", "label": "Safe Kernel Node", "layer": "kernel"},
            ],
        },
        "ip_catalog": [
            {"id": "ip-csis-v8", "category": "camera"},
        ],
    }
    view = _sw_stack_to_view_response(collision_proj)
    node_ids = [n.data.id for n in view.nodes]
    # "csis0"는 HW 노드로만 존재해야 한다 (SW 노드로 중복 등록 금지)
    csis_nodes = [n for n in view.nodes if n.data.id == "csis0"]
    assert len(csis_nodes) == 1, (
        f"'csis0' should appear exactly once (as HW node), got {len(csis_nodes)} times"
    )
    assert csis_nodes[0].data.layer == "hw", (
        f"'csis0' should be an hw layer node, got layer={csis_nodes[0].data.layer}"
    )
    # "ker-safe"는 정상 등록되어야 한다
    assert "ker-safe" in node_ids, "Expected 'ker-safe' SW node to be present"


def test_sw_stack_mode_is_topology():
    """_sw_stack_to_view_response() 결과의 mode 필드가 'topology'여야 한다."""
    view = _sw_stack_to_view_response(SW_STACK_PROJECTION)
    assert view.mode == "topology", (
        f"Expected mode='topology', got mode={view.mode!r}"
    )
