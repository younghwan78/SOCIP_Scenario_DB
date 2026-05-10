"""render_gate_inspector() 단위 테스트 (VIEW-04 — G1)."""
from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Streamlit stub — dashboard 모듈이 import 시 st.* 호출을 막기 위한 최소 mock
# ---------------------------------------------------------------------------

def _make_st_stub() -> ModuleType:
    stub = ModuleType("streamlit")
    stub.markdown = MagicMock()
    stub.write = MagicMock()
    stub.subheader = MagicMock()
    stub.caption = MagicMock()
    return stub


@pytest.fixture(autouse=True)
def _patch_streamlit(monkeypatch):
    """streamlit을 sys.modules에 stub으로 등록한 뒤 테스트 후 복원."""
    st_stub = _make_st_stub()
    monkeypatch.setitem(sys.modules, "streamlit", st_stub)
    yield st_stub
    # node_detail_panel 캐시 제거 (재import 보장)
    sys.modules.pop("dashboard.components.node_detail_panel", None)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

from scenario_db.gate.models import GateExecutionResult, GateRuleMatch
from scenario_db.models.decision.common import GateResultStatus


def _make_gate(
    status: str,
    matched_rules: list[GateRuleMatch] | None = None,
    matched_issues: list[str] | None = None,
    missing_waivers: list[str] | None = None,
) -> GateExecutionResult:
    return GateExecutionResult(
        status=GateResultStatus(status),
        matched_rules=matched_rules or [],
        matched_issues=matched_issues or [],
        missing_waivers=missing_waivers or [],
    )


# ---------------------------------------------------------------------------
# Test 1: PASS status → status badge에 "PASS" 텍스트 포함
# ---------------------------------------------------------------------------

def test_pass_status_badge_contains_PASS(_patch_streamlit):
    """PASS 상태 gate → st.markdown 호출 인자에 'PASS' 텍스트가 포함되어야 한다."""
    st_stub = _patch_streamlit
    gate = _make_gate("PASS")

    # 매 테스트마다 신선하게 import
    import importlib
    import dashboard.components.node_detail_panel as ndp
    importlib.reload(ndp)

    ndp.render_gate_inspector(gate)

    # st.markdown 호출 인자 중 하나에 "PASS" 포함 여부 확인
    all_html_args = [c.args[0] for c in st_stub.markdown.call_args_list if c.args]
    status_html_calls = [html for html in all_html_args if "PASS" in html]
    assert status_html_calls, (
        f"Expected at least one st.markdown() call containing 'PASS'. "
        f"Actual calls: {all_html_args}"
    )


# ---------------------------------------------------------------------------
# Test 2: BLOCK status → status badge에 "BLOCK" 텍스트 포함
# ---------------------------------------------------------------------------

def test_block_status_badge_contains_BLOCK(_patch_streamlit):
    """BLOCK 상태 gate → st.markdown 호출 인자에 'BLOCK' 텍스트가 포함되어야 한다."""
    st_stub = _patch_streamlit
    gate = _make_gate("BLOCK")

    import importlib
    import dashboard.components.node_detail_panel as ndp
    importlib.reload(ndp)

    ndp.render_gate_inspector(gate)

    all_html_args = [c.args[0] for c in st_stub.markdown.call_args_list if c.args]
    block_calls = [html for html in all_html_args if "BLOCK" in html]
    assert block_calls, (
        f"Expected at least one st.markdown() call containing 'BLOCK'. "
        f"Actual: {all_html_args}"
    )


# ---------------------------------------------------------------------------
# Test 3: matched_issues가 있으면 issue id가 출력에 포함
# ---------------------------------------------------------------------------

def test_matched_issues_appear_in_output(_patch_streamlit):
    """matched_issues가 있을 때 issue id가 st.markdown 호출 인자에 포함되어야 한다."""
    st_stub = _patch_streamlit
    gate = _make_gate("BLOCK", matched_issues=["iss-LLC-thrashing-0221", "iss-bw-peak-007"])

    import importlib
    import dashboard.components.node_detail_panel as ndp
    importlib.reload(ndp)

    ndp.render_gate_inspector(gate)

    all_html_args = [c.args[0] for c in st_stub.markdown.call_args_list if c.args]
    combined = " ".join(all_html_args)
    assert "iss-LLC-thrashing-0221" in combined, (
        "Expected 'iss-LLC-thrashing-0221' in rendered HTML"
    )
    assert "iss-bw-peak-007" in combined, (
        "Expected 'iss-bw-peak-007' in rendered HTML"
    )


# ---------------------------------------------------------------------------
# Test 4: matched_rules가 있으면 rule_id가 출력에 포함
# ---------------------------------------------------------------------------

def test_matched_rules_rule_id_appears_in_output(_patch_streamlit):
    """matched_rules가 있을 때 rule_id가 st.markdown 호출 인자에 포함되어야 한다."""
    st_stub = _patch_streamlit
    rule = GateRuleMatch(
        rule_id="gate-bw-001",
        result=GateResultStatus.BLOCK,
        message="Bandwidth exceeds 20 GB/s limit",
    )
    gate = _make_gate("BLOCK", matched_rules=[rule])

    import importlib
    import dashboard.components.node_detail_panel as ndp
    importlib.reload(ndp)

    ndp.render_gate_inspector(gate)

    all_html_args = [c.args[0] for c in st_stub.markdown.call_args_list if c.args]
    combined = " ".join(all_html_args)
    assert "gate-bw-001" in combined, (
        f"Expected 'gate-bw-001' in rendered HTML. Combined: {combined[:300]}"
    )


# ---------------------------------------------------------------------------
# Test 5: missing_waivers가 있으면 출력에 waiver id 포함
# ---------------------------------------------------------------------------

def test_missing_waivers_appear_in_output(_patch_streamlit):
    """missing_waivers가 있을 때 waiver id가 st.markdown 호출 인자에 포함되어야 한다."""
    st_stub = _patch_streamlit
    gate = _make_gate(
        "WAIVER_REQUIRED",
        missing_waivers=["waiver-mfc-encode-latency", "waiver-dram-bw-peak"],
    )

    import importlib
    import dashboard.components.node_detail_panel as ndp
    importlib.reload(ndp)

    ndp.render_gate_inspector(gate)

    all_html_args = [c.args[0] for c in st_stub.markdown.call_args_list if c.args]
    combined = " ".join(all_html_args)
    assert "waiver-mfc-encode-latency" in combined, (
        "Expected 'waiver-mfc-encode-latency' in rendered HTML"
    )
    assert "waiver-dram-bw-peak" in combined, (
        "Expected 'waiver-dram-bw-peak' in rendered HTML"
    )
