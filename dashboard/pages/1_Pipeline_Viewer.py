"""Pipeline Viewer — Level 0 Lane Architecture View (DB-backed, HTTP API).

Run:
  Terminal 1: uv run uvicorn scenario_db.api.app:app --reload
  Terminal 2: uv run --group dashboard streamlit run dashboard/Home.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make src/ importable when running from project root
_root = Path(__file__).resolve().parents[2]
for p in [str(_root / "src"), str(_root), str(_root / "dashboard")]:
    if p not in sys.path:
        sys.path.insert(0, p)

import requests
import streamlit as st

st.set_page_config(
    page_title="Pipeline Viewer — ScenarioDB",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

from scenario_db.api.schemas.view import ViewResponse
from dashboard.components.elk_viewer import render_level0
from dashboard.components.node_detail_panel import render_inspector


# ── Global CSS ────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Remove default Streamlit padding */
  .block-container { padding-top: 0rem !important; padding-bottom: 0rem !important; }

  /* Header bar */
  .viewer-header {
    background: white;
    border-bottom: 1px solid #E8E4DF;
    padding: 10px 20px;
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }
  .viewer-title {
    font-size: 20px; font-weight: 700; color: #111827;
  }
  .viewer-meta {
    font-size: 12px; color: #9CA3AF; display: flex; gap: 14px;
  }
  .meta-chip {
    background: #F3F4F6; border-radius: 6px; padding: 3px 8px;
    font-size: 11px; color: #6B7280;
  }

  /* Toolbar */
  .toolbar {
    background: #FAFAF8; border-bottom: 1px solid #E8E4DF;
    padding: 6px 20px;
    display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  }
  .toolbar-label {
    font-size: 11px; font-weight: 600; color: #9CA3AF;
  }

  /* Inspector panel */
  .inspector-panel {
    border-left: 1px solid #E8E4DF;
    padding: 14px 12px;
    height: 100%;
    background: white;
    overflow-y: auto;
  }

  /* Layer badge toggle */
  div[data-testid="stCheckbox"] label {
    font-size: 11px !important;
  }

  /* Hide Streamlit footer */
  footer { display: none !important; }
  #MainMenu { display: none !important; }
  header[data-testid="stHeader"] { display: none !important; }

  /* Column separator */
  div[data-testid="column"]:nth-child(2) {
    border-left: 1px solid #E8E4EB;
  }
</style>
""", unsafe_allow_html=True)


# ── Mode별 visible_layers 설정 (VIEW-02/03) ──────────────────────────────────
ARCH_LAYERS = ["hw", "memory"]
TOPO_LAYERS = ["app", "framework", "hal", "kernel", "hw"]

LAYERS: dict[str, list[str]] = {
    "architecture": ARCH_LAYERS,
    "topology":     TOPO_LAYERS,
}


# ── Cache functions (HTTP API) ────────────────────────────────────────────────

@st.cache_data(ttl=60)
def _fetch_scenarios(api_url: str) -> list[dict]:
    """GET /api/v1/scenarios → items 목록."""
    r = requests.get(f"{api_url}/api/v1/scenarios", params={"limit": 100}, timeout=10)
    r.raise_for_status()
    return r.json()["items"]  # PagedResponse.items 필드 (common.py 검증 완료)


@st.cache_data(ttl=60)
def _fetch_variants(api_url: str, scenario_id: str) -> list[dict]:
    """GET /api/v1/scenarios/{id}/variants → items 목록."""
    r = requests.get(
        f"{api_url}/api/v1/scenarios/{scenario_id}/variants",
        params={"limit": 100},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["items"]


@st.cache_data(ttl=60)
def _load_view(api_url: str, scenario_id: str, variant_id: str, mode: str) -> ViewResponse:
    """GET /view?level=0&mode=... → ViewResponse."""
    r = requests.get(
        f"{api_url}/api/v1/scenarios/{scenario_id}/variants/{variant_id}/view",
        params={"level": 0, "mode": mode},
        timeout=10,
    )
    r.raise_for_status()
    return ViewResponse.model_validate(r.json())


@st.cache_data(ttl=30)
def _fetch_gate(api_url: str, scenario_id: str, variant_id: str):
    """GET /gate → GateExecutionResult (lazy, toggle ON 시에만 호출)."""
    from scenario_db.gate.models import GateExecutionResult
    r = requests.get(
        f"{api_url}/api/v1/scenarios/{scenario_id}/variants/{variant_id}/gate",
        timeout=10,
    )
    r.raise_for_status()
    return GateExecutionResult.model_validate(r.json())


# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ScenarioDB Viewer")

    # API URL 설정 (D-02)
    st.markdown("**API Server**")
    api_url = st.text_input(
        "Base URL",
        value=st.session_state.get("api_url", "http://localhost:8000"),
        label_visibility="collapsed",
    )
    if api_url != st.session_state.get("api_url"):
        st.session_state["api_url"] = api_url
        st.cache_data.clear()
        st.rerun()
    st.session_state["api_url"] = api_url

    st.divider()

    # Scenario dropdown (D-03)
    st.markdown("**Scenario**")
    try:
        scenarios = _fetch_scenarios(api_url)
    except Exception as e:
        st.error(f"API 연결 실패: {e}")
        st.stop()

    if not scenarios:
        st.warning("Scenario 없음 — DB에 데이터가 있는지 확인하세요.")
        st.stop()

    # ScenarioResponse.metadata_ 는 dict → name 추출 (D-03)
    scenario_labels = [
        s.get("metadata_", {}).get("name", s["id"]) for s in scenarios
    ]
    scenario_ids = [s["id"] for s in scenarios]
    sel_scenario_idx = st.selectbox(
        "scenario",
        range(len(scenario_ids)),
        format_func=lambda i: scenario_labels[i],
        label_visibility="collapsed",
    )
    scenario_id = scenario_ids[sel_scenario_idx]

    # Variant dropdown (D-03)
    st.markdown("**Variant**")
    try:
        variants = _fetch_variants(api_url, scenario_id)
    except Exception as e:
        st.error(f"Variant 조회 실패: {e}")
        st.stop()

    variant_ids = [v["id"] for v in variants]
    if not variant_ids:
        st.warning("Variant 없음")
        st.stop()
    variant_id = st.selectbox(
        "variant",
        variant_ids,
        label_visibility="collapsed",
    )

    st.divider()

    # Mode selector (D-05, VIEW-05)
    st.markdown("**View Mode**")
    mode = st.radio(
        "mode",
        ["architecture", "topology"],
        index=0,
        label_visibility="collapsed",
    )

    st.divider()

    # Gate status 토글 (D-06, lazy fetch)
    show_gate = st.toggle("Show Gate Status", value=False)

    st.divider()
    st.markdown("**View Level**")
    st.radio(
        "Level",
        ["0 — Lane View", "1 — IP DAG (Phase C)", "2 — Drill-Down (Phase C)"],
        index=0,
        label_visibility="collapsed",
    )


# ── View 데이터 로드 ─────────────────────────────────────────────────────────
try:
    view = _load_view(api_url, scenario_id, variant_id, mode)
except requests.HTTPError as e:
    if e.response is not None and e.response.status_code == 501:
        st.warning("Topology mode는 Wave 2에서 구현됩니다 (04-03-PLAN)")
        st.stop()
    st.error(f"View 로드 실패: {e}")
    st.stop()
except Exception as e:
    st.error(f"API 오류: {e}")
    st.stop()

s = view.summary

# ── Gate 데이터 (toggle ON 시에만 lazy fetch) (D-06) ─────────────────────────
gate_result = None
if show_gate:
    try:
        gate_result = _fetch_gate(api_url, scenario_id, variant_id)
    except Exception as e:
        st.sidebar.warning(f"Gate 조회 실패: {e}")


# ── Header bar ─────────────────────────────────────────────────────────────
over_budget = s.period_ms > s.budget_ms if s.budget_ms else False
budget_chip_color = "#FEE2E2" if over_budget else "#F3F4F6"
budget_text_color = "#DC2626" if over_budget else "#6B7280"

st.markdown(f"""
<div class="viewer-header">
  <span style="font-size:20px;color:#6B7280;">&#9776;</span>
  <span class="viewer-title">{s.name}</span>
  <span class="meta-chip">{mode} mode</span>
  <span class="meta-chip">output_period {s.period_ms}ms</span>
  <span style="background:{budget_chip_color};color:{budget_text_color};border-radius:6px;
       padding:3px 8px;font-size:11px;">budget {s.budget_ms}ms</span>
  <div style="flex:1"></div>
  <span style="font-size:12px;color:#6B7280;">
    Variant: <b>{s.variant_label}</b>
  </span>
</div>
""", unsafe_allow_html=True)


# ── Main 레이아웃 ─────────────────────────────────────────────────────────────
visible_layers = LAYERS[mode]

main_col, inspector_col = st.columns([3, 1], gap="small")

with main_col:
    render_level0(
        view_response=view,
        visible_layers=visible_layers,
        canvas_height=660,
    )

with inspector_col:
    render_inspector(view)
    # Gate 패널은 Wave 2 (04-03-PLAN)에서 render_gate_inspector() 추가


# ── Sidebar 하단 통계 ────────────────────────────────────────────────────────
with st.sidebar:
    st.caption(f"Nodes: {len(view.nodes)} | Edges: {len(view.edges)}")
    st.caption(f"Risks: {len(view.risks)}")
    if gate_result is not None:
        st.caption(f"Gate: {gate_result.status}")
    if s.captured_at:
        st.caption(f"Captured: {s.captured_at}")
