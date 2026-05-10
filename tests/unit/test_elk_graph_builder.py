"""build_elk_graph() gate_styles 파라미터 단위 테스트 (VIEW-04 — G4)."""
from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Streamlit stub — dashboard.components 의존성 차단
# ---------------------------------------------------------------------------

def _make_st_stub() -> ModuleType:
    stub = ModuleType("streamlit")
    stub.markdown = MagicMock()
    return stub


@pytest.fixture(autouse=True)
def _patch_streamlit(monkeypatch):
    st_stub = _make_st_stub()
    monkeypatch.setitem(sys.modules, "streamlit", st_stub)
    yield st_stub


# ---------------------------------------------------------------------------
# Imports (conftest.py가 루트를 sys.path에 추가한 상태)
# ---------------------------------------------------------------------------

from dashboard.components.elk_graph_builder import build_elk_graph, GATE_BORDER
from scenario_db.api.schemas.view import (
    EdgeData, EdgeElement, NodeData, NodeElement, ViewHints,
    ViewResponse, ViewSummary,
)


# ---------------------------------------------------------------------------
# Minimal ViewResponse fixture (ip 타입 HW 노드 포함)
# ---------------------------------------------------------------------------

def _make_view(num_ip_nodes: int = 2, num_sw_nodes: int = 1) -> ViewResponse:
    """ip 타입 노드를 포함한 최소 ViewResponse를 생성."""
    nodes = []
    for i in range(num_ip_nodes):
        nodes.append(NodeElement(
            data=NodeData(
                id=f"ip-hw-{i}",
                label=f"IP HW {i}",
                type="ip",
                layer="hw",
            ),
            position={"x": float(200 + i * 150), "y": 400.0},
        ))
    for i in range(num_sw_nodes):
        nodes.append(NodeElement(
            data=NodeData(
                id=f"sw-kernel-{i}",
                label=f"SW Kernel {i}",
                type="sw",
                layer="kernel",
            ),
            position={"x": float(200 + i * 150), "y": 200.0},
        ))

    summary = ViewSummary(
        scenario_id="uc-g4-test",
        variant_id="v-g4",
        name="G4 Test Scenario",
        subtitle="gate_styles test",
        period_ms=33.3,
        budget_ms=30.0,
        resolution="1920x1080",
        fps=30,
        variant_label="test",
    )
    return ViewResponse(
        level=0,
        mode="architecture",
        scenario_id="uc-g4-test",
        variant_id="v-g4",
        nodes=nodes,
        edges=[],
        risks=[],
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Test 1: gate_styles=None → ip 노드 border 색상이 GATE_BORDER 기본값(PASS)이 아님
#         (즉, lane gradient의 hw border 색상 그대로 유지)
# ---------------------------------------------------------------------------

def test_gate_styles_none_preserves_hw_border():
    """gate_styles=None → ip 노드의 border가 GATE_BORDER['PASS']로 오버라이드되지 않는다.

    hw 레이어의 LAYER_GRADIENT border는 #EA7C00 이며, GATE_BORDER['PASS']는 #D1D5DB 이다.
    gate_styles=None 이면 hw 기본 border가 유지되어야 한다.
    """
    from dashboard.components.viewer_theme import LAYER_GRADIENT

    view = _make_view()
    _, meta = build_elk_graph(view, gate_styles=None)

    hw_gradient_border = LAYER_GRADIENT["hw"]["border"]   # #EA7C00
    gate_pass_border = GATE_BORDER["PASS"]                # #D1D5DB

    # hw gradient border != GATE_BORDER['PASS'] — 전제 조건 확인
    assert hw_gradient_border != gate_pass_border, (
        "Test premise violated: hw gradient border equals GATE_BORDER['PASS']"
    )

    # gate_styles=None → ip 노드 border는 hw gradient border여야 함
    ip_meta_entries = [v for k, v in meta.items() if v.get("type") == "ip"]
    assert ip_meta_entries, "Expected at least one ip-type node in meta"
    for entry in ip_meta_entries:
        assert entry["border"] == hw_gradient_border, (
            f"With gate_styles=None, ip node border should be hw gradient border "
            f"({hw_gradient_border}), got {entry['border']}"
        )


# ---------------------------------------------------------------------------
# Test 2: gate_styles={"__global__": "BLOCK"} → ip 노드의 border가 BLOCK 색상
# ---------------------------------------------------------------------------

def test_gate_styles_global_block_overrides_ip_border():
    """gate_styles={'__global__': 'BLOCK'} → ip 타입 노드 border가 GATE_BORDER['BLOCK'] 색상이어야 한다."""
    view = _make_view()
    _, meta = build_elk_graph(view, gate_styles={"__global__": "BLOCK"})

    expected_border = GATE_BORDER["BLOCK"]   # #EF4444
    ip_meta_entries = [v for k, v in meta.items() if v.get("type") == "ip"]
    assert ip_meta_entries, "Expected at least one ip-type node in meta"

    for entry in ip_meta_entries:
        assert entry["border"] == expected_border, (
            f"Expected BLOCK border color {expected_border!r}, got {entry['border']!r}"
        )
    # warning 플래그도 True여야 함 (D-06)
    for entry in ip_meta_entries:
        assert entry.get("warning") is True, (
            f"Expected warning=True for BLOCK gate_styles, got {entry.get('warning')!r}"
        )


# ---------------------------------------------------------------------------
# Test 3: gate_styles={"__global__": "PASS"} → ip 노드의 border가 PASS 색상
# ---------------------------------------------------------------------------

def test_gate_styles_global_pass_applies_pass_border():
    """gate_styles={'__global__': 'PASS'} → ip 노드 border가 GATE_BORDER['PASS'] 색상이어야 한다."""
    view = _make_view()
    _, meta = build_elk_graph(view, gate_styles={"__global__": "PASS"})

    expected_border = GATE_BORDER["PASS"]   # #D1D5DB
    ip_meta_entries = [v for k, v in meta.items() if v.get("type") == "ip"]
    assert ip_meta_entries, "Expected at least one ip-type node in meta"

    for entry in ip_meta_entries:
        assert entry["border"] == expected_border, (
            f"Expected PASS border color {expected_border!r}, got {entry['border']!r}"
        )
    # PASS → warning=True 오버라이드 없음 (PASS는 "WARN"/"BLOCK"/"WAIVER_REQUIRED" 조건 미충족)
    for entry in ip_meta_entries:
        assert entry.get("warning") is not True, (
            f"Expected warning NOT True for PASS gate_styles, got {entry.get('warning')!r}"
        )


# ---------------------------------------------------------------------------
# Test 4: gate_styles 없이(=None) 호출 시 기존 동작 유지 (sw 노드 border 불변)
# ---------------------------------------------------------------------------

def test_gate_styles_none_does_not_affect_sw_nodes():
    """gate_styles=None → sw 타입 노드의 border가 GATE_BORDER 값으로 오버라이드되지 않는다."""
    from dashboard.components.viewer_theme import LAYER_GRADIENT

    view = _make_view(num_sw_nodes=2)
    _, meta = build_elk_graph(view, gate_styles=None)

    # sw 노드 (kernel layer)의 meta entry 확인
    sw_meta_entries = [v for k, v in meta.items() if v.get("type") == "sw"]
    assert sw_meta_entries, "Expected at least one sw-type node in meta"

    kernel_gradient_border = LAYER_GRADIENT["kernel"]["border"]  # #7C3AED
    for entry in sw_meta_entries:
        assert entry["border"] == kernel_gradient_border, (
            f"SW node border should be kernel gradient border {kernel_gradient_border!r}, "
            f"got {entry['border']!r}"
        )


# ---------------------------------------------------------------------------
# Test 5 (보너스): gate_styles={"__global__": "BLOCK"} → sw 노드는 border 오버라이드 안됨
# ---------------------------------------------------------------------------

def test_gate_styles_block_does_not_affect_sw_nodes():
    """gate_styles BLOCK 오버라이드는 ip 타입 노드에만 적용 — sw 노드는 영향 없음."""
    from dashboard.components.viewer_theme import LAYER_GRADIENT

    view = _make_view(num_sw_nodes=2)
    _, meta = build_elk_graph(view, gate_styles={"__global__": "BLOCK"})

    sw_meta_entries = [v for k, v in meta.items() if v.get("type") == "sw"]
    assert sw_meta_entries, "Expected at least one sw-type node in meta"

    kernel_gradient_border = LAYER_GRADIENT["kernel"]["border"]  # #7C3AED
    block_border = GATE_BORDER["BLOCK"]  # #EF4444

    for entry in sw_meta_entries:
        assert entry["border"] != block_border, (
            f"SW node border should NOT be overridden to BLOCK color {block_border!r}"
        )
        assert entry["border"] == kernel_gradient_border, (
            f"SW node border should remain kernel gradient {kernel_gradient_border!r}, "
            f"got {entry['border']!r}"
        )
