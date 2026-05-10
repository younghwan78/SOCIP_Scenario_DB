"""Pipeline SwStackNode round-trip 테스트."""
import pytest
from scenario_db.models.definition.usecase import Pipeline, SwStackNode


def test_pipeline_accepts_sw_stack():
    """sw_stack 필드가 있는 Pipeline이 검증을 통과한다."""
    data = {
        "nodes": [
            {"id": "csis0", "ip_ref": "ip-csis-v8", "instance_index": 0},
        ],
        "edges": [],
        "sw_stack": [
            {"layer": "app",    "id": "app-camera", "label": "Camera App"},
            {"layer": "kernel", "id": "ker-v4l2",   "label": "V4L2 Driver", "ip_ref": "csis0"},
        ],
    }
    pipeline = Pipeline.model_validate(data)
    assert len(pipeline.sw_stack) == 2
    assert pipeline.sw_stack[0].layer == "app"
    assert pipeline.sw_stack[1].ip_ref == "csis0"


def test_pipeline_without_sw_stack_is_valid():
    """sw_stack 없는 기존 Pipeline도 그대로 유효하다 (하위 호환)."""
    data = {
        "nodes": [
            {"id": "csis0", "ip_ref": "ip-csis-v8", "instance_index": 0},
            {"id": "isp0",  "ip_ref": "ip-isp-v12", "instance_index": 0},
        ],
        "edges": [
            {"from": "csis0", "to": "isp0", "type": "OTF"},
        ],
    }
    pipeline = Pipeline.model_validate(data)
    assert pipeline.sw_stack == []


def test_sw_stack_round_trip():
    """SwStackNode round-trip serialization."""
    node = SwStackNode(layer="hal", id="hal-camera", label="Camera HAL", ip_ref=None)
    data = node.model_dump()
    restored = SwStackNode.model_validate(data)
    assert restored.layer == "hal"
    assert restored.ip_ref is None


def test_sw_stack_invalid_layer_raises():
    """hw 레이어는 SwStackNode에 허용되지 않는다."""
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        SwStackNode(layer="hw", id="bad", label="Bad Node")
