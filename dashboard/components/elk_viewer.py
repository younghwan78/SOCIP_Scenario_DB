"""ELK/SVG Level 0 pipeline viewer — Streamlit component.

Replaces cytoscape_viewer.py. Uses elkjs@0.9.3 (CDN) for client-side
layout and vanilla-JS SVG rendering. Pattern mirrors the reference
implementation at E:\\10_Codes\\23_MMIP_Scenario_simulation2\\src\\view\\html_view.py.

Template substitution points (/* */ comments so JSON stays valid):
  /*__GRAPH__*/    → JSON-serialised ELK graph
  /*__META__*/     → JSON-serialised meta dict
  /*__CANVAS_H__*/ → canvas height in pixels (integer)
"""
from __future__ import annotations

import json

import streamlit.components.v1 as components

from dashboard.components.elk_graph_builder import LANE_ORDER, build_elk_graph
from scenario_db.api.schemas.view import ViewResponse

ALL_LAYERS = LANE_ORDER
ALL_EDGE_TYPES = ["OTF", "vOTF", "M2M", "control", "risk"]

# ---------------------------------------------------------------------------
# HTML template (elkjs CDN + vanilla-JS SVG renderer)
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  html,body{
    width:100%;height:/*__CANVAS_H__*/px;
    background:#FAF9F7;
    font-family:Inter,system-ui,-apple-system,sans-serif;
    overflow:hidden;
  }
  #wrapper{
    position:relative;width:100%;height:/*__CANVAS_H__*/px;
    background:#FAFAF8;border:1px solid #E8E4DF;border-radius:8px;overflow:hidden;
  }
  svg{
    display:block;outline:none;cursor:grab;
    user-select:none;-webkit-user-select:none;
  }
  svg:active{cursor:grabbing;}
  #tooltip{
    display:none;position:fixed;
    background:#fff;border:1px solid #E5E7EB;border-radius:10px;
    padding:10px 13px;box-shadow:0 4px 20px rgba(0,0,0,.13);
    font-size:12px;max-width:280px;z-index:200;
    pointer-events:none;line-height:1.55;
  }
  .tt-title{font-size:13px;font-weight:700;color:#111827;
    margin-bottom:5px;border-bottom:1px solid #F3F4F6;padding-bottom:4px;}
  .tt-row{display:flex;gap:8px;font-size:11px;color:#6B7280;margin-top:2px;}
  .tt-row .k{min-width:80px;color:#9CA3AF;}
  .tt-badge{display:inline-block;background:#EEF2FF;color:#3730A3;
    border-radius:4px;padding:1px 5px;font-size:10px;font-weight:600;margin:0 2px 1px 0;}
  .tt-risk{background:#FEE2E2!important;color:#991B1B!important;}
  #debug{
    display:none;position:fixed;bottom:0;left:0;right:0;
    background:#1e1e1e;color:#4ec9b0;font-family:monospace;
    font-size:11px;padding:3px 8px;z-index:999;
  }
</style>
<script src="https://cdn.jsdelivr.net/npm/elkjs@0.9.3/lib/elk.bundled.js"></script>
</head>
<body>
<div id="wrapper">
  <svg id="main-svg" tabindex="0"><defs id="defs"></defs><g id="g-main"></g></svg>
</div>
<div id="tooltip"></div>
<div id="debug"></div>

<script>
(function(){
'use strict';

// ── Injected data ────────────────────────────────────────────────────────
const GRAPH = /*__GRAPH__*/;
const META  = /*__META__*/;
const CANVAS_H = /*__CANVAS_H__*/;

// ── Constants ────────────────────────────────────────────────────────────
const NS = 'http://www.w3.org/2000/svg';
const EDGE_COLORS = {
  OTF:'#4A6CF7', vOTF:'#2BB3AA', M2M:'#F97316',
  control:'#9B8EC4', risk:'#EF4444'
};
const EDGE_WIDTHS = {OTF:2.5, vOTF:2.5, M2M:2, control:1.5, risk:2};
const EDGE_DASH   = {control:'6,4', risk:'8,3'};

// ── Zoom / pan state ─────────────────────────────────────────────────────
let tx=0, ty=0, sc=1;
const PAD = 32;

// ── SVG helpers ──────────────────────────────────────────────────────────
function ce(tag, attrs){
  const el = document.createElementNS(NS, tag);
  for(const [k,v] of Object.entries(attrs||{})) el.setAttribute(k, v);
  return el;
}
function ceh(tag, attrs){
  const el = document.createElement(tag);
  for(const [k,v] of Object.entries(attrs||{})) el.setAttribute(k, v);
  return el;
}

// ── Arrowhead markers ─────────────────────────────────────────────────────
function buildMarkers(){
  const defs = document.getElementById('defs');
  const types = Object.keys(EDGE_COLORS);
  types.forEach(function(t){
    const c = EDGE_COLORS[t];
    const m = ce('marker',{
      id:'arr-'+t, markerWidth:'8', markerHeight:'6',
      refX:'7', refY:'3', orient:'auto'
    });
    const poly = ce('polygon',{
      points:'0 0, 8 3, 0 6',
      fill: c
    });
    m.appendChild(poly);
    defs.appendChild(m);
  });
  // vOTF: also a "back" marker for bidirectional visual (source end)
  const c2 = EDGE_COLORS['vOTF'];
  const mb = ce('marker',{
    id:'arr-vOTF-src', markerWidth:'8', markerHeight:'6',
    refX:'1', refY:'3', orient:'auto-start-reverse'
  });
  mb.appendChild(ce('polygon',{points:'0 0, 8 3, 0 6', fill:c2}));
  defs.appendChild(mb);
}

// ── Lane background + label ───────────────────────────────────────────────
function drawLane(g, node, ox, oy, m){
  const x=ox, y=oy, w=node.width||0, h=node.height||0;
  // Background rect
  const r = ce('rect',{
    x:x+0.5, y:y+0.5,
    width:Math.max(0,w-1), height:Math.max(0,h-1),
    rx:'6', ry:'6',
    fill: m.fill||'rgba(200,200,200,0.07)',
    stroke: m.border||'#ccc',
    'stroke-width':'1',
    'stroke-opacity':'0.45',
  });
  g.appendChild(r);

  // Left label zone (80px wide)
  const lw=80, lpad=6;
  const lbl = m.label||'';
  const lt = ce('text',{
    x: x+lw/2, y: y+h/2,
    'text-anchor':'middle',
    'dominant-baseline':'middle',
    'font-size':'11',
    'font-weight':'700',
    'font-family':'Inter,system-ui,sans-serif',
    fill: m.text_color||m.border||'#6B7280',
    'pointer-events':'none',
  });
  lt.textContent = lbl;
  g.appendChild(lt);

  // Vertical separator between label zone and content
  const sep = ce('line',{
    x1:x+lw, y1:y+4, x2:x+lw, y2:y+h-4,
    stroke: m.border||'#ccc',
    'stroke-width':'0.8',
    'stroke-opacity':'0.35',
  });
  g.appendChild(sep);
}

// ── Functional node (sw / ip / buffer) ───────────────────────────────────
function drawFunc(g, node, ox, oy, m){
  const x=ox, y=oy, w=node.width||0, h=node.height||0;
  const rx=6;

  // Gradient simulation via two rects (top-left lighter, slight overlay)
  const r = ce('rect',{
    x:x, y:y, width:w, height:h, rx:rx,
    fill: m.color||'#E5E7EB',
    stroke: m.warning ? '#EF4444' : (m.border||'#D1D5DB'),
    'stroke-width': m.warning ? '2.5' : '1.5',
    'stroke-dasharray': m.warning ? '5,3' : 'none',
  });
  g.appendChild(r);

  // Gradient overlay (lighter top portion)
  const ov = ce('rect',{
    x:x, y:y, width:w, height:h*0.5, rx:rx,
    fill: m.color2||m.color||'#E5E7EB',
    opacity:'0.45',
    'pointer-events':'none',
  });
  g.appendChild(ov);

  // Label text
  const label = m.label||node.id||'';
  const lines = label.split('\n');
  const lineH = 14;
  const startY = y + h/2 - (lines.length-1)*lineH/2;
  lines.forEach(function(line, i){
    const t = ce('text',{
      x: x+w/2, y: startY + i*lineH,
      'text-anchor':'middle',
      'dominant-baseline':'middle',
      'font-size': m.type==='ip' ? '12' : '11',
      'font-weight':'600',
      'font-family':'Inter,system-ui,sans-serif',
      fill: m.text_color||'#374151',
      'pointer-events':'none',
    });
    t.textContent = line;
    g.appendChild(t);
  });

  // Capability badges (top-right pills)
  const badges = m.badges||[];
  badges.slice(0,3).forEach(function(b, i){
    const bx = x+w - 4 - (badges.length-i)*28;
    const by = y+3;
    const bw = 26, bh = 13;
    const bg = ce('rect',{x:bx,y:by,width:bw,height:bh,rx:3,
      fill:'rgba(255,255,255,0.75)',stroke:m.border||'#ccc','stroke-width':'0.5'});
    g.appendChild(bg);
    const bt = ce('text',{
      x:bx+bw/2, y:by+bh/2,
      'text-anchor':'middle','dominant-baseline':'middle',
      'font-size':'8','font-weight':'700',
      fill:m.border||'#6B7280','pointer-events':'none',
    });
    bt.textContent = b;
    g.appendChild(bt);
  });

  // Click target for tooltip
  const hit = ce('rect',{
    x:x, y:y, width:w, height:h, rx:rx,
    fill:'transparent', cursor:'pointer',
  });
  hit.addEventListener('click', function(ev){
    ev.stopPropagation();
    showTip(ev, node.id, m);
  });
  g.appendChild(hit);
}

// ── Edge drawing ──────────────────────────────────────────────────────────
function drawEdge(g, edge, ox, oy){
  const m = META[edge.id]||{};
  const color = m.color || EDGE_COLORS[m.type] || '#9CA3AF';
  const sw = m.width||2;
  const dashArr = m.dash||EDGE_DASH[m.type]||'';
  const etype = m.type||'';

  const sec = edge.sections && edge.sections[0];
  if(!sec) return;

  // Collect path points
  const pts = [{x:sec.startPoint.x+ox, y:sec.startPoint.y+oy}];
  (sec.bendPoints||[]).forEach(function(p){ pts.push({x:p.x+ox, y:p.y+oy}); });
  pts.push({x:sec.endPoint.x+ox, y:sec.endPoint.y+oy});

  if(pts.length < 2) return;

  const d = 'M ' + pts.map(function(p){ return p.x.toFixed(1)+','+p.y.toFixed(1); }).join(' L ');

  const attrs = {
    d: d,
    stroke: color,
    'stroke-width': sw,
    fill: 'none',
    'marker-end': 'url(#arr-'+etype+')',
  };
  if(dashArr) attrs['stroke-dasharray'] = dashArr;
  if(etype==='vOTF') attrs['marker-start'] = 'url(#arr-vOTF-src)';

  const path = ce('path', attrs);
  g.appendChild(path);

  // Edge label
  if(edge.labels && edge.labels.length){
    const lb = edge.labels[0];
    if(lb.x !== undefined){
      const lx = lb.x+ox, ly = lb.y+oy;
      // White background
      const bg = ce('rect',{
        x:lx-2, y:ly,
        width:(lb.width||0)+4, height:(lb.height||14)+2,
        rx:'3', fill:'white','fill-opacity':'0.88',
        stroke:color,'stroke-width':'0.5',
      });
      g.appendChild(bg);
      const lt = ce('text',{
        x:lx+(lb.width||0)/2, y:ly+(lb.height||14)/2+1,
        'text-anchor':'middle',
        'dominant-baseline':'middle',
        'font-size':'9','font-weight':'500',
        'font-family':'Inter,system-ui,sans-serif',
        fill:color,'pointer-events':'none',
      });
      lt.textContent = lb.text||'';
      g.appendChild(lt);
    }
  }
}

// ── Recursive node renderer ───────────────────────────────────────────────
function drawNode(g, node, ox, oy){
  const nx = (node.x||0)+ox;
  const ny = (node.y||0)+oy;
  const m = META[node.id]||{};

  if(m.type === 'lane'){
    drawLane(g, node, nx, ny, m);
  } else if(node.id !== 'root' && node.width){
    drawFunc(g, node, nx, ny, m);
  }

  (node.children||[]).forEach(function(c){ drawNode(g, c, nx, ny); });
  (node.edges||[]).forEach(function(e){ drawEdge(g, e, nx, ny); });
}

// Stage header labels (above the canvas, drawn statically in SVG coords)
function drawStageHeaders(g, layout){
  // Collect x-ranges from lane_hw children (most representative)
  const hwLane = (layout.children||[]).find(function(c){ return c.id==='lane_hw'; });
  if(!hwLane) return;

  // Stage header bar — light gray row at top
  const hdrH = 24;
  const bg = ce('rect',{x:0,y:0,width:layout.width||1100,height:hdrH,
    fill:'#F9FAFB',stroke:'none'});
  g.insertBefore(bg, g.firstChild);

  // Stage column dividers: collect x-positions from lane nodes
  const stageMap = {};
  (hwLane.children||[]).forEach(function(n){
    const lco = n.layoutOptions && n.layoutOptions['elk.layered.layerConstraint'];
    if(lco==='FIRST') stageMap['Capture'] = (n.x||0) + (hwLane.x||0);
    if(lco==='LAST')  stageMap['Display'] = (n.x||0) + (hwLane.x||0);
  });

  // Just draw a thin divider line at top
  const divL = ce('line',{x1:0,y1:hdrH,x2:layout.width||1100,y2:hdrH,
    stroke:'#E8E4DF','stroke-width':'1'});
  g.insertBefore(divL, g.firstChild);
}

// ── Tooltip ───────────────────────────────────────────────────────────────
const tip = document.getElementById('tooltip');

// Build a tooltip row using textContent (XSS-safe) for all user data values.
function _ttRow(key, val){
  const row = document.createElement('div'); row.className='tt-row';
  const k = document.createElement('span'); k.className='k'; k.textContent=key;
  const v = document.createElement('span'); v.textContent=val;
  row.appendChild(k); row.appendChild(v);
  return row;
}

function showTip(ev, nodeId, m){
  const d = m.detail||{};
  // Clear previous content safely
  while(tip.firstChild) tip.removeChild(tip.firstChild);

  // Title (textContent — no raw HTML)
  const title = document.createElement('div'); title.className='tt-title';
  title.textContent = m.label||nodeId;
  tip.appendChild(title);

  if(d.layer) tip.appendChild(_ttRow('Layer', d.layer));
  if(d.type)  tip.appendChild(_ttRow('Type',  d.type));
  if(d.ip_ref) tip.appendChild(_ttRow('IP ref', d.ip_ref));
  if(d.scale) tip.appendChild(_ttRow('Scale', d.scale));
  if(d.crop)  tip.appendChild(_ttRow('Crop',  d.crop));
  if(d.capabilities && d.capabilities.length){
    const row = document.createElement('div'); row.className='tt-row';
    const k = document.createElement('span'); k.className='k'; k.textContent='Capabilities';
    const v = document.createElement('span');
    d.capabilities.forEach(function(b){
      const badge = document.createElement('span'); badge.className='tt-badge';
      badge.textContent=b; v.appendChild(badge);
    });
    row.appendChild(k); row.appendChild(v); tip.appendChild(row);
  }
  if(d.memory) tip.appendChild(_ttRow('Memory', d.memory));
  if(d.llc)    tip.appendChild(_ttRow('LLC',    d.llc));
  if(d.issues && d.issues.length){
    const row = document.createElement('div'); row.className='tt-row';
    const k = document.createElement('span'); k.className='k'; k.textContent='Issues';
    const v = document.createElement('span');
    d.issues.forEach(function(i){
      const badge = document.createElement('span'); badge.className='tt-badge tt-risk';
      badge.textContent=i; v.appendChild(badge);
    });
    row.appendChild(k); row.appendChild(v); tip.appendChild(row);
  }
  tip.style.display = 'block';
  const tw = tip.offsetWidth||220, th2 = tip.offsetHeight||120;
  const mx = ev.clientX+14, my = ev.clientY+14;
  tip.style.left = Math.min(mx, window.innerWidth-tw-16)+'px';
  tip.style.top  = Math.min(my, window.innerHeight-th2-16)+'px';
}

function hideTip(){ tip.style.display='none'; }
document.addEventListener('click', function(e){
  if(!tip.contains(e.target)) hideTip();
});

// ── Zoom / pan ────────────────────────────────────────────────────────────
function applyTx(){
  document.getElementById('g-main').setAttribute(
    'transform','translate('+tx+','+ty+') scale('+sc+')');
}

function fitView(W, H){
  const wrap = document.getElementById('wrapper');
  const vw = wrap.clientWidth||1100;
  const vh = wrap.clientHeight||CANVAS_H;
  const fitSc = Math.min((vw-PAD*2)/W, (vh-PAD*2)/H, 1.0);
  sc = fitSc;
  tx = (vw - W*sc)/2;
  ty = (vh - H*sc)/2;
  applyTx();
}

function setupZoomPan(){
  const svg = document.getElementById('main-svg');
  let drag=false, sx=0, sy=0, dd=0;

  svg.addEventListener('wheel', function(e){
    e.preventDefault();
    const factor = e.deltaY>0 ? 0.9 : 1.1;
    const ns = Math.max(0.15, Math.min(6, sc*factor));
    const r = ns/sc;
    const rect = svg.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    tx = mx - (mx-tx)*r;
    ty = my - (my-ty)*r;
    sc = ns;
    applyTx();
  }, {passive:false});

  svg.addEventListener('mousedown', function(e){
    drag=true; dd=0;
    sx = e.clientX-tx; sy = e.clientY-ty;
  });
  svg.addEventListener('mousemove', function(e){
    if(!drag) return;
    dd++;
    tx = e.clientX-sx; ty = e.clientY-sy;
    applyTx();
  });
  svg.addEventListener('mouseup',   function(){ drag=false; });
  svg.addEventListener('mouseleave', function(){ drag=false; });

  const STEP=60;
  svg.addEventListener('keydown', function(e){
    if(e.key==='ArrowLeft'){ tx+=STEP; e.preventDefault(); }
    else if(e.key==='ArrowRight'){ tx-=STEP; e.preventDefault(); }
    else if(e.key==='ArrowUp'){   ty+=STEP; e.preventDefault(); }
    else if(e.key==='ArrowDown'){ ty-=STEP; e.preventDefault(); }
    else return;
    applyTx();
  });
}

// ── Main ──────────────────────────────────────────────────────────────────
if(typeof ELK === 'undefined'){
  document.getElementById('debug').textContent='ERROR: elkjs failed to load';
  document.getElementById('debug').style.display='block';
} else {
  const elk = new ELK();
  elk.layout(GRAPH).then(function(layout){
    const svg = document.getElementById('main-svg');
    const W = layout.width||1100, H = layout.height||680;
    svg.setAttribute('width', W);
    svg.setAttribute('height', H);
    svg.setAttribute('viewBox', '0 0 '+W+' '+H);

    buildMarkers();

    const g = document.getElementById('g-main');
    drawNode(g, layout, 0, 0);

    console.log('[ELK] layout done W='+W+' H='+H+
      ' nodes='+(layout.children||[]).length+
      ' edges='+(layout.edges||[]).length);

    fitView(W, H);
    setupZoomPan();
  }).catch(function(err){
    const dbg = document.getElementById('debug');
    dbg.textContent = 'ELK error: '+err;
    dbg.style.display = 'block';
    console.error('[ELK]', err);
  });
}

})();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Render helpers
# ---------------------------------------------------------------------------

def _render_html(elk_graph: dict, meta: dict, canvas_h: int) -> str:
    html = _HTML_TEMPLATE
    html = html.replace("/*__GRAPH__*/", json.dumps(elk_graph, ensure_ascii=False))
    html = html.replace("/*__META__*/",  json.dumps(meta,      ensure_ascii=False))
    # Replace all occurrences (appears in CSS height and JS constant)
    html = html.replace("/*__CANVAS_H__*/", str(canvas_h))
    return html


# ---------------------------------------------------------------------------
# Public render function
# ---------------------------------------------------------------------------

def render_level0(
    view_response: ViewResponse,
    visible_layers: list[str] | None = None,
    visible_edge_types: list[str] | None = None,
    canvas_height: int = 640,
    selected_node: dict | None = None,
    gate_styles: dict[str, str] | None = None,
) -> None:
    """Render Level 0 ELK/SVG pipeline diagram into the current Streamlit location.

    gate_styles: {"__global__": "WARN"|"BLOCK"|"PASS"|"WAIVER_REQUIRED"} or None.
    When provided, applies border/warning override to ip-type nodes (D-06, VIEW-04).
    """
    elk_graph, meta = build_elk_graph(
        view_response,
        visible_layers=visible_layers,
        visible_edge_types=visible_edge_types,
        gate_styles=gate_styles,
    )
    html = _render_html(elk_graph, meta, canvas_height)
    components.html(html, height=canvas_height + 4, scrolling=False)
