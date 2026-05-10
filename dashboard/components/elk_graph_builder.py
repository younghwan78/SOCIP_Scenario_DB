"""Convert ViewResponse into an ELK graph + meta dict for client-side rendering.

ELK graph structure:
  root (layered DOWN, INCLUDE_CHILDREN)
  └── lane_<name> compound nodes (layered RIGHT, one per SW/HW/memory layer)
      └── functional nodes (sw / ip / buffer)
  root.edges — ALL edges (intra-lane and cross-lane)

meta dict is keyed by node/edge id and carries rendering properties
(color, label, badges, tooltip detail) consumed by the JavaScript renderer.
"""
from __future__ import annotations

from collections import defaultdict

from dashboard.components.lane_layout import LANE_COLORS, LANE_LABEL_ORDER
from dashboard.components.viewer_theme import EDGE_COLOR, LANE_BG_RGBA, LAYER_GRADIENT
from scenario_db.api.schemas.view import EdgeData, ViewResponse

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LANE_ORDER = LANE_LABEL_ORDER  # ["app", "framework", "hal", "kernel", "hw", "memory"]

LANE_DISPLAY: dict[str, str] = {
    "app": "App", "framework": "Framework", "hal": "HAL",
    "kernel": "Kernel", "hw": "HW", "memory": "Buffer",
}

NODE_DIMS: dict[str, tuple[int, int]] = {
    "sw":     (130, 36),
    "ip":     (100, 34),
    "buffer": (150, 36),
}

# stage → ELK layerConstraint
STAGE_CONSTRAINT: dict[str, str] = {
    "capture": "FIRST",
    "display": "LAST",
}

EDGE_WIDTH: dict[str, float] = {
    "OTF": 2.5, "vOTF": 2.5, "M2M": 2.0, "control": 1.5, "risk": 2.0,
}

EDGE_DASH: dict[str, str] = {
    "control": "6,4", "risk": "8,3",
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_elk_graph(
    view: ViewResponse,
    visible_layers: list[str] | None = None,
    visible_edge_types: list[str] | None = None,
    gate_styles: dict[str, str] | None = None,
) -> tuple[dict, dict]:
    """Return (elk_graph, meta) ready for JSON serialisation and template injection.

    gate_styles: {"__global__": "WARN"|"BLOCK"|"PASS"|"WAIVER_REQUIRED"} or None.
    When provided, applies border/warning override to ip-type nodes (D-06).
    """
    vis_layers = set(visible_layers) if visible_layers is not None else set(LANE_ORDER)
    vis_etypes = set(visible_edge_types) if visible_edge_types is not None else set(EDGE_COLOR)

    # Group functional nodes by layer
    by_lane: dict[str, list] = defaultdict(list)
    for ne in view.nodes:
        if ne.data.layer in vis_layers:
            by_lane[ne.data.layer].append(ne)

    visible_node_ids: set[str] = {ne.data.id for nodes in by_lane.values() for ne in nodes}

    # Build compound lane children
    lane_children: list[dict] = []
    for lane in LANE_ORDER:
        if lane not in by_lane:
            continue
        nodes_in_lane = by_lane[lane]
        elk_children = [_build_elk_node(ne) for ne in nodes_in_lane]
        lane_children.append({
            "id": f"lane_{lane}",
            "layoutOptions": {
                "elk.algorithm": "layered",
                "elk.direction": "RIGHT",
                "elk.edgeRouting": "ORTHOGONAL",
                "elk.spacing.nodeNode": "24",
                "elk.layered.spacing.nodeNodeBetweenLayers": "44",
                "elk.padding": "[top=10,left=80,bottom=10,right=16]",
                "elk.considerModelOrder.strategy": "NODES_AND_EDGES",
            },
            "children": elk_children,
            "edges": [],
        })

    # Build edge list (all edges at root level — hierarchyHandling handles routing)
    elk_edges: list[dict] = []
    for ee in view.edges:
        ed = ee.data
        if ed.flow_type not in vis_etypes:
            continue
        if ed.source not in visible_node_ids or ed.target not in visible_node_ids:
            continue
        elk_edges.append(_build_elk_edge(ed))

    elk_graph: dict = {
        "id": "root",
        "layoutOptions": {
            "elk.algorithm": "layered",
            "elk.direction": "DOWN",
            "elk.edgeRouting": "ORTHOGONAL",
            "elk.hierarchyHandling": "INCLUDE_CHILDREN",
            "elk.layered.spacing.nodeNodeBetweenLayers": "0",
            "elk.spacing.nodeNode": "0",
            "elk.separateConnectedComponents": "false",
            "elk.padding": "[top=28,left=0,bottom=4,right=0]",
        },
        "children": lane_children,
        "edges": elk_edges,
    }

    meta = _build_meta(view, visible_node_ids, vis_etypes, vis_layers, gate_styles=gate_styles)
    return elk_graph, meta


# Alias for backward compatibility
def build_view_layout(
    view: ViewResponse,
    visible_layers: list[str] | None = None,
    visible_edge_types: list[str] | None = None,
    gate_styles: dict[str, str] | None = None,
) -> tuple[dict, dict]:
    """Alias for build_elk_graph() — backward-compat name used by elk_viewer.py."""
    return build_elk_graph(
        view,
        visible_layers=visible_layers,
        visible_edge_types=visible_edge_types,
        gate_styles=gate_styles,
    )


# ---------------------------------------------------------------------------
# ELK node / edge builders
# ---------------------------------------------------------------------------

def _build_elk_node(ne) -> dict:
    d = ne.data
    w, h = NODE_DIMS.get(d.type, (120, 36))
    node: dict = {"id": d.id, "width": w, "height": h}

    stage = d.view_hints.stage if d.view_hints else None
    if stage and stage in STAGE_CONSTRAINT:
        node["layoutOptions"] = {
            "elk.layered.layerConstraint": STAGE_CONSTRAINT[stage],
        }
    return node


def _build_elk_edge(ed: EdgeData) -> dict:
    label_text = _build_edge_label(ed)
    edge: dict = {
        "id": ed.id,
        "sources": [ed.source],
        "targets": [ed.target],
    }
    if label_text:
        char_w = 6.5
        edge["labels"] = [{
            "text": label_text,
            "width": len(label_text) * char_w,
            "height": 14,
        }]
    return edge


def _build_edge_label(ed: EdgeData) -> str:
    parts: list[str] = []
    if ed.memory:
        m = ed.memory
        if m.format:
            parts.append(m.format)
        if m.width and m.height:
            parts.append(f"{m.width}×{m.height}")
        if m.bitdepth:
            parts.append(f"{m.bitdepth}bit")
        if m.compression:
            parts.append(m.compression)
    return " | ".join(parts)


# ---------------------------------------------------------------------------
# Meta dict builder
# ---------------------------------------------------------------------------

# Gate status → node border 색상 오버라이드 (D-06)
GATE_BORDER: dict[str, str] = {
    "PASS":             "#D1D5DB",   # 기본 회색 (변화 없음)
    "WARN":             "#F59E0B",   # 노란색 테두리
    "BLOCK":            "#EF4444",   # 빨간색 테두리
    "WAIVER_REQUIRED":  "#8B5CF6",   # 보라색 테두리
}


def _build_meta(
    view: ViewResponse,
    visible_node_ids: set[str],
    vis_etypes: set[str],
    vis_layers: set[str],
    gate_styles: dict[str, str] | None = None,
) -> dict:
    meta: dict = {}

    # Lane compound node meta
    for lane in LANE_ORDER:
        if lane not in vis_layers:
            continue
        meta[f"lane_{lane}"] = {
            "type": "lane",
            "label": LANE_DISPLAY.get(lane, lane),
            "fill": LANE_BG_RGBA.get(lane, "rgba(200,200,200,0.07)"),
            "border": LANE_COLORS[lane]["border"],
            "text_color": LAYER_GRADIENT[lane]["border"],
        }

    # Functional node meta
    for ne in view.nodes:
        d = ne.data
        if d.id not in visible_node_ids:
            continue
        g = LAYER_GRADIENT.get(d.layer, {})
        entry: dict = {
            "type": d.type,
            "layer": d.layer,
            "label": d.label,
            "color": g.get("g1", "#E5E7EB"),
            "color2": g.get("g2", "#E5E7EB"),
            "border": g.get("border", "#D1D5DB"),
            "text_color": g.get("text", "#374151"),
            "warning": d.warning,
        }
        if d.capability_badges:
            entry["badges"] = d.capability_badges

        # Tooltip detail
        detail: dict = {"layer": d.layer, "type": d.type}
        if d.ip_ref:
            detail["ip_ref"] = d.ip_ref
        if d.capability_badges:
            detail["capabilities"] = d.capability_badges
        if d.active_operations:
            ops = d.active_operations
            if ops.scale:
                detail["scale"] = f"{ops.scale_from} → {ops.scale_to}"
            if ops.crop:
                detail["crop"] = f"ratio {ops.crop_ratio}" if ops.crop_ratio else "yes"
        if d.memory:
            m = d.memory
            mem_parts: list[str] = []
            if m.format:
                mem_parts.append(m.format)
            if m.width and m.height:
                mem_parts.append(f"{m.width}×{m.height}")
            if m.fps:
                mem_parts.append(f"{m.fps}fps")
            if m.bitdepth:
                mem_parts.append(f"{m.bitdepth}bit")
            if m.compression:
                mem_parts.append(m.compression)
            if mem_parts:
                detail["memory"] = " · ".join(mem_parts)
        if d.placement and d.placement.llc_allocated:
            pl = d.placement
            detail["llc"] = f"{pl.llc_allocation_mb}MB ({pl.llc_policy})"
        if d.matched_issues:
            detail["issues"] = d.matched_issues
        entry["detail"] = detail
        meta[d.id] = entry

    # Gate status 색상 오버라이드 (D-06)
    # gate_styles = {"__global__": "WARN"|"BLOCK"|"PASS"|"WAIVER_REQUIRED"}
    if gate_styles:
        global_status = gate_styles.get("__global__")
        if global_status and global_status in GATE_BORDER:
            gate_border_color = GATE_BORDER[global_status]
            for nid, entry in meta.items():
                if entry.get("type") == "ip":   # HW IP 노드에만 적용
                    entry["border"] = gate_border_color
                    if global_status in ("WARN", "BLOCK", "WAIVER_REQUIRED"):
                        entry["warning"] = True

    # Edge meta
    for ee in view.edges:
        ed = ee.data
        if ed.flow_type not in vis_etypes:
            continue
        if ed.source not in visible_node_ids or ed.target not in visible_node_ids:
            continue
        meta[ed.id] = {
            "type": ed.flow_type,
            "color": EDGE_COLOR.get(ed.flow_type, "#9CA3AF"),
            "width": EDGE_WIDTH.get(ed.flow_type, 2.0),
            "dash": EDGE_DASH.get(ed.flow_type, ""),
            "label": ed.label or "",
        }

    return meta
