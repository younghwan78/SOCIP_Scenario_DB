"""Pipeline Viewer — Level 0 Lane Architecture View.

Run: uv run --group dashboard streamlit run dashboard/Home.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make src/ importable when running from project root
_root = Path(__file__).resolve().parents[2]
if str(_root / "src") not in sys.path:
    sys.path.insert(0, str(_root / "src"))
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
if str(_root / "dashboard") not in sys.path:
    sys.path.insert(0, str(_root / "dashboard"))

import streamlit as st

st.set_page_config(
    page_title="Pipeline Viewer — ScenarioDB",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

from scenario_db.view.service import build_sample_level0
from dashboard.components.cytoscape_viewer import (
    ALL_EDGE_TYPES, ALL_LAYERS, render_level0,
)
from dashboard.components.node_detail_panel import render_inspector
from dashboard.components.viewer_theme import EDGE_COLOR, LAYER_GRADIENT


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
    border-left: 1px solid #E8E4DF;
  }
</style>
""", unsafe_allow_html=True)


# ── Session state defaults ─────────────────────────────────────────────────
if "visible_layers" not in st.session_state:
    st.session_state["visible_layers"] = list(ALL_LAYERS)
if "visible_edges" not in st.session_state:
    st.session_state["visible_edges"] = list(ALL_EDGE_TYPES)
if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = "Architect"


# ── Load view data ─────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def _load_view():
    return build_sample_level0()

view = _load_view()
s = view.summary


# ── Header bar ─────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="viewer-header">
  <span style="font-size:20px;color:#6B7280;">☰</span>
  <span class="viewer-title">{s.name} — {s.subtitle.split(',')[0]}</span>
  <span class="meta-chip">v1.0</span>
  <span class="meta-chip">output_period {s.period_ms}ms</span>
  <span class="meta-chip">budget {s.budget_ms}ms</span>
  <div style="flex:1"></div>
  <span style="font-size:12px;color:#6B7280;">
    Variant: <b>{s.variant_label} ({s.subtitle.split(',')[0]})</b>
  </span>
  <span style="background:#EEF2FF;color:#4338CA;border:1px solid #C7D2FE;
       border-radius:8px;padding:4px 10px;font-size:11px;font-weight:600;cursor:pointer;">
    ↑ Snapshot / Export
  </span>
  <span style="color:#9CA3AF;font-size:18px;">⋯</span>
</div>
""", unsafe_allow_html=True)


# ── Tabs ───────────────────────────────────────────────────────────────────
tab_exec, tab_arch = st.tabs(["Executive", "Architect"])

with tab_arch:
    # ── Toolbar: layer toggles + edge type toggles ─────────────────────────
    LAYER_DISPLAY = {
        "app": "App", "framework": "Framework", "hal": "HAL",
        "kernel": "Kernel", "hw": "HW", "memory": "Buffer",
    }
    EDGE_DISPLAY = {
        "OTF": "OTF", "vOTF": "vOTF", "M2M": "M2M", "control": "SW", "risk": "Risk",
    }

    with st.container():
        toolbar_cols = st.columns([0.5] + [1] * len(ALL_LAYERS) + [0.3] + [1] * len(ALL_EDGE_TYPES))
        toolbar_cols[0].markdown(
            '<p style="font-size:11px;font-weight:600;color:#9CA3AF;margin-top:6px;">Layers:</p>',
            unsafe_allow_html=True,
        )

        for i, layer in enumerate(ALL_LAYERS):
            g = LAYER_GRADIENT.get(layer, {})
            color = g.get("border", "#6B7280")
            checked = layer in st.session_state["visible_layers"]
            val = toolbar_cols[i + 1].checkbox(
                f"**{LAYER_DISPLAY[layer]}**",
                value=checked,
                key=f"layer_{layer}",
            )
            # Update session state
            if val and layer not in st.session_state["visible_layers"]:
                st.session_state["visible_layers"].append(layer)
            elif not val and layer in st.session_state["visible_layers"]:
                st.session_state["visible_layers"].remove(layer)

        sep_col = toolbar_cols[len(ALL_LAYERS) + 1]
        sep_col.markdown(
            '<p style="font-size:11px;font-weight:600;color:#9CA3AF;margin-top:6px;">Edges:</p>',
            unsafe_allow_html=True,
        )

        for j, etype in enumerate(ALL_EDGE_TYPES):
            ec = EDGE_COLOR.get(etype, "#6B7280")
            checked_e = etype in st.session_state["visible_edges"]
            val_e = toolbar_cols[len(ALL_LAYERS) + 2 + j].checkbox(
                f"**{EDGE_DISPLAY[etype]}**",
                value=checked_e,
                key=f"edge_{etype}",
            )
            if val_e and etype not in st.session_state["visible_edges"]:
                st.session_state["visible_edges"].append(etype)
            elif not val_e and etype in st.session_state["visible_edges"]:
                st.session_state["visible_edges"].remove(etype)

    st.markdown("<hr style='margin:0;border-color:#E8E4DF;'>", unsafe_allow_html=True)

    # ── Main content: diagram (left 75%) + inspector (right 25%) ──────────
    main_col, inspector_col = st.columns([3, 1], gap="small")

    with main_col:
        render_level0(
            view_response=view,
            visible_layers=st.session_state["visible_layers"],
            visible_edge_types=st.session_state["visible_edges"],
            canvas_height=640,
        )

    with inspector_col:
        with st.container():
            render_inspector(view)

with tab_exec:
    st.markdown("""
    <div style="padding:40px;text-align:center;color:#9CA3AF;">
      <p style="font-size:32px;margin-bottom:12px;">📊</p>
      <p style="font-size:16px;font-weight:600;color:#374151;">Executive View</p>
      <p style="font-size:13px;margin-top:8px;">
        Phase C: KPI summary, feasibility verdict, and top-3 risks dashboard.
      </p>
    </div>
    """, unsafe_allow_html=True)


# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ScenarioDB Viewer")
    st.markdown("**Level 0** — Lane Architecture View")
    st.divider()

    st.markdown("**Scenario**")
    st.code(view.scenario_id, language=None)
    st.markdown("**Variant**")
    st.code(view.variant_id, language=None)

    st.divider()
    st.markdown("**View Level**")
    level = st.radio(
        "Level", ["0 — Lane View", "1 — IP DAG (Phase C)", "2 — Drill-Down (Phase C)"],
        index=0, label_visibility="collapsed",
    )

    st.divider()
    st.caption(f"Nodes: {len(view.nodes)} | Edges: {len(view.edges)}")
    st.caption(f"Risks: {len(view.risks)}")
    if view.summary.captured_at:
        st.caption(f"Captured: {view.summary.captured_at}")
