"""Cytoscape.js Level 0 renderer — builds self-contained HTML for components.html()."""
from __future__ import annotations

import json

import streamlit.components.v1 as components

from dashboard.components.lane_layout import (
    BG_CENTER_X, BG_WIDTH, CANVAS_H, CANVAS_W, LANE_COLORS,
    LANE_DISPLAY_NAMES, LANE_GAP, LANE_H, LANE_LABEL_ORDER,
    LANE_LABEL_W, LANE_Y, NODE_H, NODE_W,
    STAGE_BOUNDS, STAGE_HEADER_H, STAGE_NAMES, STAGE_X,
    LANE_ICONS,
)
from dashboard.components.viewer_theme import EDGE_COLOR, LAYER_GRADIENT, LANE_BG_RGBA

ALL_LAYERS = list(LANE_Y.keys())
ALL_EDGE_TYPES = ["OTF", "vOTF", "M2M", "control", "risk"]


def _build_layout_elements() -> list[dict]:
    """Build lane background, lane label, and stage header nodes."""
    elems: list[dict] = []

    # ── Lane background nodes ─────────────────────────────────────────────
    for lane in LANE_LABEL_ORDER:
        cy = LANE_COLORS[lane]
        elems.append({
            "data": {
                "id": f"bg-{lane}", "label": "", "type": "lane_bg",
                "layer": lane, "bg_rgba": cy["bg"], "border_color": cy["border"],
            },
            "position": {"x": BG_CENTER_X, "y": LANE_Y[lane]},
        })

    # ── Lane label nodes ──────────────────────────────────────────────────
    for lane in LANE_LABEL_ORDER:
        lc = LAYER_GRADIENT[lane]
        icon = LANE_ICONS[lane]
        elems.append({
            "data": {
                "id": f"lbl-{lane}",
                "label": f"{icon}\n{LANE_DISPLAY_NAMES[lane]}",
                "type": "lane_label", "layer": lane,
                "text_color": lc["border"],
            },
            "position": {"x": LANE_LABEL_W / 2, "y": LANE_Y[lane]},
        })

    # ── Stage header nodes ────────────────────────────────────────────────
    for key, name in STAGE_NAMES.items():
        elems.append({
            "data": {
                "id": f"hdr-{key}", "label": name,
                "type": "stage_header", "layer": "meta",
            },
            "position": {"x": STAGE_X[key], "y": STAGE_HEADER_H / 2},
        })

    # ── Stage divider nodes (thin vertical line placeholders) ─────────────
    for i, (key, (x0, x1)) in enumerate(STAGE_BOUNDS.items()):
        if i == 0:
            continue  # skip left edge
        mid_y = CANVAS_H / 2
        elems.append({
            "data": {
                "id": f"div-{key}", "label": "", "type": "stage_divider",
                "layer": "meta", "x_pos": x0,
            },
            "position": {"x": x0, "y": mid_y},
        })

    return elems


def _build_cytoscape_stylesheet() -> list[dict]:
    """Return the full Cytoscape style array."""

    def node_gradient(layer: str) -> dict:
        g = LAYER_GRADIENT.get(layer, {})
        if not g:
            return {}
        return {
            "background-fill": "linear-gradient",
            "background-gradient-direction": "to-bottom-right",
            "background-gradient-stop-colors": f"{g['g1']} {g['g2']}",
            "background-gradient-stop-positions": "0 1",
            "border-color": g["border"],
            "color": g["text"],
        }

    styles: list[dict] = [
        # ── Default node ──────────────────────────────────────────────────
        {
            "selector": "node",
            "style": {
                "label": "data(label)",
                "text-valign": "center",
                "text-halign": "center",
                "font-family": "Inter, system-ui, sans-serif",
                "font-size": 12,
                "font-weight": 600,
                "shape": "round-rectangle",
                "border-width": 1.5,
                "padding": "6px",
                "text-wrap": "none",
                "overlay-opacity": 0,
                "z-index": 10,
            },
        },

        # ── Lane background ───────────────────────────────────────────────
        {
            "selector": "node[type = 'lane_bg']",
            "style": {
                "width": BG_WIDTH,
                "height": LANE_H - 4,
                "shape": "round-rectangle",
                "background-color": "data(bg_rgba)",
                "background-opacity": 1,
                "border-color": "data(border_color)",
                "border-width": 1,
                "border-opacity": 0.4,
                "label": "",
                "events": "no",
                "z-index": 1,
                "corner-radius": "10px",
            },
        },

        # Per-lane background tints
        *[
            {
                "selector": f"node[type = 'lane_bg'][layer = '{lane}']",
                "style": {
                    "background-color": LANE_BG_RGBA[lane],
                    "border-color": LANE_COLORS[lane]["border"],
                },
            }
            for lane in LANE_LABEL_ORDER
        ],

        # ── Lane label ────────────────────────────────────────────────────
        {
            "selector": "node[type = 'lane_label']",
            "style": {
                "width": NODE_W["lane_label"],
                "height": NODE_H["lane_label"],
                "background-opacity": 0,
                "border-width": 0,
                "font-size": 11,
                "font-weight": 700,
                "text-wrap": "wrap",
                "text-max-width": f"{NODE_W['lane_label']}px",
                "color": "data(text_color)",
                "events": "no",
                "z-index": 5,
            },
        },

        # ── Stage header ──────────────────────────────────────────────────
        {
            "selector": "node[type = 'stage_header']",
            "style": {
                "width": NODE_W["stage_header"],
                "height": NODE_H["stage_header"],
                "background-opacity": 0,
                "border-width": 0,
                "font-size": 11,
                "font-weight": 600,
                "color": "#9CA3AF",
                "events": "no",
                "z-index": 5,
            },
        },

        # ── Stage divider (invisible, structure only) ─────────────────────
        {
            "selector": "node[type = 'stage_divider']",
            "style": {
                "width": 1,
                "height": CANVAS_H,
                "background-color": "#EDE9E4",
                "background-opacity": 0.6,
                "border-width": 0,
                "label": "",
                "events": "no",
                "z-index": 2,
            },
        },

        # ── Functional nodes by layer ─────────────────────────────────────
        *[
            {
                "selector": f"node[layer = '{layer}'][type != 'lane_bg'][type != 'lane_label'][type != 'stage_header'][type != 'stage_divider']",
                "style": {
                    **node_gradient(layer),
                    "color": LAYER_GRADIENT.get(layer, {}).get("text", "#111"),
                    "z-index": 10,
                },
            }
            for layer in LANE_LABEL_ORDER
        ],

        # SW node sizing
        {
            "selector": "node[type = 'sw']",
            "style": {
                "width": NODE_W["sw"],
                "height": NODE_H["sw"],
            },
        },

        # IP (HW) node sizing
        {
            "selector": "node[type = 'ip']",
            "style": {
                "width": NODE_W["ip"],
                "height": NODE_H["ip"],
                "font-size": 12,
            },
        },

        # Buffer node sizing
        {
            "selector": "node[type = 'buffer']",
            "style": {
                "width": NODE_W["buffer"],
                "height": NODE_H["buffer"],
                "font-size": 11,
            },
        },

        # ── Primary emphasis ──────────────────────────────────────────────
        {
            "selector": "node[?emphasis]",
            "style": {
                "border-width": 2.5,
            },
        },

        # ── Warning / risk nodes ──────────────────────────────────────────
        {
            "selector": "node[warning = 'true']",
            "style": {
                "border-color": "#EF4444",
                "border-width": 2.5,
                "border-style": "dashed",
            },
        },

        # ── Selected state ────────────────────────────────────────────────
        {
            "selector": "node:selected",
            "style": {
                "border-color": "#1D4ED8",
                "border-width": 3,
                "overlay-color": "#1D4ED8",
                "overlay-opacity": 0.08,
                "overlay-padding": 4,
            },
        },

        # ── Default edge ──────────────────────────────────────────────────
        {
            "selector": "edge",
            "style": {
                "width": 2,
                "target-arrow-shape": "vee",
                "arrow-scale": 1.1,
                "curve-style": "straight",
                "overlay-opacity": 0,
                "z-index": 8,
            },
        },

        # OTF — blue solid
        {
            "selector": "edge[flow_type = 'OTF']",
            "style": {
                "line-color": EDGE_COLOR["OTF"],
                "target-arrow-color": EDGE_COLOR["OTF"],
                "line-style": "solid",
                "width": 2,
            },
        },

        # vOTF — teal solid, bidirectional arrow
        {
            "selector": "edge[flow_type = 'vOTF']",
            "style": {
                "line-color": EDGE_COLOR["vOTF"],
                "target-arrow-color": EDGE_COLOR["vOTF"],
                "source-arrow-color": EDGE_COLOR["vOTF"],
                "target-arrow-shape": "vee",
                "source-arrow-shape": "none",
                "line-style": "solid",
                "width": 2.5,
            },
        },

        # M2M — orange solid
        {
            "selector": "edge[flow_type = 'M2M']",
            "style": {
                "line-color": EDGE_COLOR["M2M"],
                "target-arrow-color": EDGE_COLOR["M2M"],
                "line-style": "solid",
                "width": 2,
                "curve-style": "bezier",
            },
        },

        # SW/control — gray-purple dashed, bidirectional
        {
            "selector": "edge[flow_type = 'control']",
            "style": {
                "line-color": EDGE_COLOR["control"],
                "target-arrow-color": EDGE_COLOR["control"],
                "source-arrow-color": EDGE_COLOR["control"],
                "target-arrow-shape": "vee",
                "source-arrow-shape": "vee",
                "line-style": "dashed",
                "line-dash-pattern": [6, 4],
                "width": 1.5,
                "opacity": 0.75,
            },
        },

        # Risk — red dashed
        {
            "selector": "edge[flow_type = 'risk']",
            "style": {
                "line-color": EDGE_COLOR["risk"],
                "target-arrow-color": EDGE_COLOR["risk"],
                "line-style": "dashed",
                "line-dash-pattern": [8, 3],
                "width": 2,
                "curve-style": "bezier",
            },
        },

        # Edge selected
        {
            "selector": "edge:selected",
            "style": {
                "width": 3.5,
                "overlay-color": "#1D4ED8",
                "overlay-opacity": 0.1,
            },
        },
    ]

    return styles


def _build_html(
    functional_nodes: list[dict],
    all_edges: list[dict],
    visible_layers: list[str],
    visible_edge_types: list[str],
    selected_node_data: dict | None,
    canvas_h: int,
) -> str:
    layout_elems = _build_layout_elements()
    stylesheet = _build_cytoscape_stylesheet()

    # Filter functional nodes by visible layer
    vis_set = set(visible_layers)
    vis_edges = set(visible_edge_types)
    filtered_nodes = [n for n in functional_nodes if n["data"].get("layer") in vis_set]
    filtered_node_ids = {n["data"]["id"] for n in filtered_nodes}

    filtered_edges = [
        e for e in all_edges
        if (
            e["data"].get("flow_type") in vis_edges
            and e["data"]["source"] in filtered_node_ids
            and e["data"]["target"] in filtered_node_ids
        )
    ]

    all_elements = layout_elems + filtered_nodes + filtered_edges

    # Legend HTML
    legend_items_html = "".join(
        f"""<div class="legend-item">
              <svg width="30" height="14">
                <line x1="2" y1="7" x2="28" y2="7"
                  stroke="{EDGE_COLOR[etype]}"
                  stroke-width="{'2.5' if etype == 'vOTF' else '2'}"
                  stroke-dasharray="{'none' if etype in ('OTF','vOTF','M2M') else '6 3'}"/>
                <polygon points="22,4 28,7 22,10" fill="{EDGE_COLOR[etype]}"/>
              </svg>
              <span>{etype}</span>
            </div>"""
        for etype in ALL_EDGE_TYPES
    )

    tooltip_data_json = json.dumps(selected_node_data or {})

    total_h = canvas_h + 48  # legend

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: Inter, system-ui, -apple-system, sans-serif;
    background: #FAF9F7;
    overflow: hidden;
  }}
  #wrapper {{
    position: relative;
    width: 100%;
    height: {canvas_h}px;
    background: #FAFAF8;
    border: 1px solid #E8E4DF;
    border-radius: 12px;
    overflow: hidden;
  }}
  #cy {{
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    background: transparent !important;
  }}
  #tooltip {{
    display: none;
    position: absolute;
    background: white;
    border: 1px solid #E5E7EB;
    border-radius: 10px;
    padding: 12px 14px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.10);
    font-size: 12px;
    max-width: 240px;
    z-index: 100;
    pointer-events: none;
    line-height: 1.6;
  }}
  #tooltip .tt-title {{
    font-size: 13px;
    font-weight: 700;
    color: #111827;
    margin-bottom: 6px;
    border-bottom: 1px solid #F3F4F6;
    padding-bottom: 5px;
  }}
  #tooltip .tt-row {{
    display: flex;
    gap: 8px;
    color: #6B7280;
    font-size: 11px;
  }}
  #tooltip .tt-row span:first-child {{
    min-width: 80px;
    color: #9CA3AF;
  }}
  #tooltip .tt-badge {{
    display: inline-block;
    background: #EEF2FF;
    color: #3730A3;
    border-radius: 4px;
    padding: 1px 6px;
    font-size: 10px;
    font-weight: 600;
    margin: 1px 2px 1px 0;
  }}
  #tooltip .tt-risk {{
    background: #FEE2E2;
    color: #991B1B;
  }}
  #legend {{
    display: flex;
    align-items: center;
    gap: 18px;
    padding: 8px 16px;
    background: #F9FAFB;
    border-top: 1px solid #E8E4DF;
    height: 44px;
    overflow: hidden;
  }}
  .legend-item {{
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    color: #6B7280;
    white-space: nowrap;
  }}
  .legend-label {{
    font-size: 11px;
    font-weight: 600;
    color: #9CA3AF;
    margin-right: 4px;
  }}
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.29.2/cytoscape.min.js"
  integrity="sha512-jFjEU7MHE3LBTy7+n2Q5pQ3X9dKQeX+EFpv5RJajFP0bQIgzJ9M9c2yHhHWG7l3aFbwzVifwxnxNdSNvLGNg=="
  crossorigin="anonymous" referrerpolicy="no-referrer"></script>
</head>
<body>
<div id="wrapper">
  <div id="cy"></div>
  <div id="tooltip"></div>
</div>
<div id="legend">
  <span class="legend-label">Edges:</span>
  {legend_items_html}
</div>

<script>
const elements = {json.dumps(all_elements, ensure_ascii=False)};
const stylesheet = {json.dumps(stylesheet, ensure_ascii=False)};

const cy = cytoscape({{
  container: document.getElementById('cy'),
  elements: elements,
  layout: {{ name: 'preset' }},
  style: stylesheet,
  zoom: 1,
  pan: {{ x: 0, y: 0 }},
  userZoomingEnabled: true,
  userPanningEnabled: true,
  minZoom: 0.5,
  maxZoom: 2.5,
  boxSelectionEnabled: false,
}});

// Fit to canvas on load
cy.ready(function() {{
  cy.fit(cy.elements().not('[type="lane_bg"]').not('[type="lane_label"]').not('[type="stage_header"]').not('[type="stage_divider"]'), 40);
}});

// ── Tooltip on node click ─────────────────────────────────────────────
const tooltip = document.getElementById('tooltip');

function showTooltip(node, renderedPos) {{
  const d = node.data();
  if (['lane_bg','lane_label','stage_header','stage_divider'].includes(d.type)) return;

  let html = `<div class="tt-title">${{d.label}}</div>`;

  if (d.layer && d.layer !== 'meta') {{
    html += `<div class="tt-row"><span>Layer</span><span>${{d.layer}}</span></div>`;
  }}
  if (d.type) {{
    html += `<div class="tt-row"><span>Type</span><span>${{d.type}}</span></div>`;
  }}
  if (d.ip_ref) {{
    html += `<div class="tt-row"><span>IP ref</span><span>${{d.ip_ref}}</span></div>`;
  }}
  if (d.capability_badges && d.capability_badges.length) {{
    const badges = d.capability_badges.map(b => `<span class="tt-badge">${{b}}</span>`).join('');
    html += `<div class="tt-row"><span>Capabilities</span><span>${{badges}}</span></div>`;
  }}
  if (d.active_operations) {{
    const ops = d.active_operations;
    if (ops.scale) {{
      html += `<div class="tt-row"><span>Scale</span><span>${{ops.scale_from || '?'}} → ${{ops.scale_to || '?'}}</span></div>`;
    }}
    if (ops.crop) {{
      const cr = ops.crop_ratio ? `ratio ${{ops.crop_ratio}}` : '';
      html += `<div class="tt-row"><span>Crop</span><span>${{cr}}</span></div>`;
    }}
  }}
  if (d.memory) {{
    const m = d.memory;
    const parts = [m.format, m.width && m.height ? `${{m.width}}x${{m.height}}` : null, m.fps ? `${{m.fps}}fps` : null, m.compression].filter(Boolean);
    if (parts.length) html += `<div class="tt-row"><span>Memory</span><span>${{parts.join(' · ')}}</span></div>`;
  }}
  if (d.placement && d.placement.llc_allocated) {{
    html += `<div class="tt-row"><span>LLC</span><span>${{d.placement.llc_allocation_mb || '?'}} MB (${{d.placement.llc_policy}})</span></div>`;
  }}
  if (d.matched_issues && d.matched_issues.length) {{
    const badges = d.matched_issues.map(i => `<span class="tt-badge tt-risk">${{i}}</span>`).join('');
    html += `<div class="tt-row"><span>Issues</span><span>${{badges}}</span></div>`;
  }}

  tooltip.innerHTML = html;
  tooltip.style.display = 'block';

  const ctr = document.getElementById('wrapper');
  const rect = ctr.getBoundingClientRect();
  const pan = cy.pan();
  const zoom = cy.zoom();
  const pos = node.position();
  const px = pos.x * zoom + pan.x;
  const py = pos.y * zoom + pan.y;

  let left = px + 20;
  let top = py - 20;
  if (left + 250 > rect.width) left = px - 260;
  if (top + 180 > rect.height) top = py - 180;
  tooltip.style.left = left + 'px';
  tooltip.style.top = top + 'px';
}}

cy.on('tap', 'node', function(evt) {{
  showTooltip(evt.target, evt.renderedPosition);
}});

cy.on('tap', function(evt) {{
  if (evt.target === cy) {{
    tooltip.style.display = 'none';
  }}
}});

cy.on('pan zoom', function() {{
  tooltip.style.display = 'none';
}});

// Notify Streamlit parent (node click data)
cy.on('tap', 'node', function(evt) {{
  const d = evt.target.data();
  if (['lane_bg','lane_label','stage_header','stage_divider'].includes(d.type)) return;
  try {{
    window.parent.postMessage({{
      type: 'cytoscape_node_click',
      nodeId: d.id,
      nodeData: d,
    }}, '*');
  }} catch(e) {{}}
}});
</script>
</body>
</html>"""


def render_level0(
    view_response,
    visible_layers: list[str] | None = None,
    visible_edge_types: list[str] | None = None,
    canvas_height: int = 660,
    selected_node: dict | None = None,
) -> None:
    """Render Level 0 Cytoscape diagram into the current Streamlit location."""
    if visible_layers is None:
        visible_layers = ALL_LAYERS
    if visible_edge_types is None:
        visible_edge_types = ALL_EDGE_TYPES

    # Serialize nodes (functional only — layout elements added inside builder)
    functional_nodes = []
    for ne in view_response.nodes:
        d = ne.data.model_dump(exclude_none=False)
        # Flatten nested objects for Cytoscape data (it needs flat dicts)
        d_flat = {}
        for k, v in d.items():
            if v is None:
                continue
            if isinstance(v, dict):
                d_flat[k] = v  # keep as-is (accessed in JS as object)
            elif isinstance(v, bool):
                d_flat[k] = "true" if v else "false"
            else:
                d_flat[k] = v
        # view_hints → flatten lane/stage for style selectors
        if ne.data.view_hints:
            vh = ne.data.view_hints
            if vh.lane:
                d_flat["view_lane"] = vh.lane
            if vh.stage:
                d_flat["view_stage"] = vh.stage
            if vh.emphasis and vh.emphasis != "normal":
                d_flat["emphasis"] = vh.emphasis
        functional_nodes.append({
            "data": d_flat,
            "position": ne.position,
        })

    edges = []
    for ee in view_response.edges:
        d = ee.data.model_dump(exclude_none=True)
        edges.append({"data": d})

    html = _build_html(
        functional_nodes=functional_nodes,
        all_edges=edges,
        visible_layers=visible_layers,
        visible_edge_types=visible_edge_types,
        selected_node_data=selected_node,
        canvas_h=canvas_height,
    )

    total_h = canvas_height + 50
    components.html(html, height=total_h, scrolling=False)
