"""View projection service.

build_canonical_graph() → project_level0() → ViewResponse

Sample data matches the "Video Recording — FHD 30fps" scenario from the
design draft. Real DB integration is wired via the FastAPI router; the
dashboard can also call this module directly without an HTTP round-trip.
"""
from __future__ import annotations

from scenario_db.api.schemas.view import (
    EdgeData, EdgeElement, MemoryDescriptor, MemoryPlacement,
    NodeData, NodeElement, OperationSummary, RiskCard,
    ViewHints, ViewResponse, ViewSummary,
)
from scenario_db.view.layout import (
    BG_CENTER_X, BG_WIDTH, CANVAS_H, CANVAS_W,
    LANE_H, LANE_LABEL_W, LANE_Y, LANE_DISPLAY_NAMES,
    NODE_H, NODE_W, STAGE_HEADER_H, STAGE_X,
)


# ---------------------------------------------------------------------------
# Sample scenario — Camera Recording FHD 30fps (matches design image)
# ---------------------------------------------------------------------------

def _n(nid: str, label: str, ntype: str, layer: str,
       x: float, y: float, **kwargs) -> NodeElement:
    data = NodeData(id=nid, label=label, type=ntype, layer=layer, **kwargs)
    return NodeElement(data=data, position={"x": x, "y": y})


def _e(eid: str, src: str, tgt: str, flow_type: str, **kwargs) -> EdgeElement:
    data = EdgeData(id=eid, source=src, target=tgt, flow_type=flow_type, **kwargs)
    return EdgeElement(data=data)


def build_sample_level0() -> ViewResponse:
    """Return a hardcoded Level 0 ViewResponse for the FHD30 demo scenario."""
    ly = LANE_Y

    # ── Functional nodes ──────────────────────────────────────────────────
    nodes: list[NodeElement] = [
        # App lane
        _n("app-camera",   "Camera App",    "sw", "app",       210, ly["app"],
           view_hints=ViewHints(lane="app", stage="capture", order=0)),
        _n("app-recorder", "Recorder App",  "sw", "app",       510, ly["app"],
           view_hints=ViewHints(lane="app", stage="processing", order=0)),

        # Framework lane
        _n("fw-cam-svc",   "CameraService",  "sw", "framework", 210, ly["framework"],
           view_hints=ViewHints(lane="framework", stage="capture", order=0)),
        _n("fw-media-rec", "MediaRecorder",  "sw", "framework", 510, ly["framework"],
           view_hints=ViewHints(lane="framework", stage="processing", order=0)),
        _n("fw-codec-fw",  "MediaCodec FW",  "sw", "framework", 790, ly["framework"],
           view_hints=ViewHints(lane="framework", stage="encode", order=0)),

        # HAL lane
        _n("hal-camera",  "Camera HAL",  "sw", "hal", 210, ly["hal"],
           view_hints=ViewHints(lane="hal", stage="capture", order=0)),
        _n("hal-codec2",  "Codec2 HAL",  "sw", "hal", 510, ly["hal"],
           view_hints=ViewHints(lane="hal", stage="processing", order=0)),

        # Kernel lane
        _n("ker-v4l2",   "V4L2 Camera Driver", "sw", "kernel", 210, ly["kernel"],
           view_hints=ViewHints(lane="kernel", stage="capture", order=0)),
        _n("ker-mfc-drv","MFC Driver",         "sw", "kernel", 510, ly["kernel"],
           view_hints=ViewHints(lane="kernel", stage="processing", order=0)),
        _n("ker-ion",    "ION / DMA-BUF",      "sw", "kernel", 790, ly["kernel"],
           view_hints=ViewHints(lane="kernel", stage="encode", order=0)),
        _n("ker-drm",    "DRM / KMS",          "sw", "kernel", 1010, ly["kernel"],
           view_hints=ViewHints(lane="kernel", stage="display", order=0),
           warning=False),

        # HW lane — ISP active scale 4000x3000→1920x1080
        _n("hw-sensor",  "Sensor",  "ip", "hw", 120, ly["hw"],
           view_hints=ViewHints(lane="hw", stage="capture", order=0, emphasis="primary")),
        _n("hw-csis",    "CSIS",    "ip", "hw", 240, ly["hw"],
           view_hints=ViewHints(lane="hw", stage="capture", order=1)),
        _n("hw-isp",     "ISP",     "ip", "hw", 410, ly["hw"],
           ip_ref="ip-isp-v12",
           capability_badges=["CROP", "SCALE", "HDR10"],
           active_operations=OperationSummary(
               scale=True, scale_from="4000x3000", scale_to="1920x1080",
               crop=True, crop_ratio=0.9,
           ),
           view_hints=ViewHints(lane="hw", stage="processing", order=0, emphasis="primary")),
        _n("hw-mlsc",    "MLSC",    "ip", "hw", 530, ly["hw"],
           view_hints=ViewHints(lane="hw", stage="processing", order=1)),
        _n("hw-mcsc",    "MCSC",    "ip", "hw", 645, ly["hw"],
           view_hints=ViewHints(lane="hw", stage="processing", order=2)),
        _n("hw-mfc",     "MFC",     "ip", "hw", 810, ly["hw"],
           ip_ref="ip-mfc-v14",
           capability_badges=["H.265", "AV1"],
           matched_issues=["iss-LLC-thrashing-0221"],
           warning=True,
           view_hints=ViewHints(lane="hw", stage="encode", order=0, emphasis="risk")),
        _n("hw-dpu",     "DPU",     "ip", "hw", 1010, ly["hw"],
           ip_ref="ip-dpu-v9",
           view_hints=ViewHints(lane="hw", stage="display", order=0)),

        # Buffer (memory) lane
        _n("buf-raw",     "RAW Buffer",           "buffer", "memory", 195, ly["memory"],
           memory=MemoryDescriptor(format="RAW10", bitdepth=10, planes=1,
                                   width=4000, height=3000, fps=30),
           view_hints=ViewHints(lane="memory", stage="capture", order=0)),
        _n("buf-yuv",     "YUV Preview Buffer",   "buffer", "memory", 415, ly["memory"],
           memory=MemoryDescriptor(format="NV12", bitdepth=8, planes=2,
                                   width=1920, height=1080, fps=30),
           view_hints=ViewHints(lane="memory", stage="processing", order=0)),
        _n("buf-enc-in",  "Encoder Input Buffer", "buffer", "memory", 605, ly["memory"],
           memory=MemoryDescriptor(format="NV12", compression="SBWC_v4",
                                   width=1920, height=1080, fps=30),
           placement=MemoryPlacement(llc_allocated=True, llc_allocation_mb=1.0,
                                      llc_policy="dedicated", allocation_owner="MFC"),
           view_hints=ViewHints(lane="memory", stage="processing", order=1)),
        _n("buf-enc-out", "Encoded Bitstream",    "buffer", "memory", 815, ly["memory"],
           memory=MemoryDescriptor(format="H.265", fps=30),
           view_hints=ViewHints(lane="memory", stage="encode", order=0)),
        _n("buf-disp",    "Display Buffer",       "buffer", "memory", 1010, ly["memory"],
           memory=MemoryDescriptor(format="ARGB8888", width=1920, height=1080, fps=30),
           view_hints=ViewHints(lane="memory", stage="display", order=0)),
    ]

    # ── Edges ─────────────────────────────────────────────────────────────
    edges: list[EdgeElement] = [
        # App horizontal (SW/control)
        _e("e-app-h", "app-camera", "app-recorder", "control"),

        # Capture column — vertical SW/control (bidirectional)
        _e("e-cap-app-fw",  "app-camera",   "fw-cam-svc",  "control"),
        _e("e-cap-fw-hal",  "fw-cam-svc",   "hal-camera",  "control"),
        _e("e-cap-hal-ker", "hal-camera",   "ker-v4l2",    "control"),
        _e("e-cap-ker-hw",  "ker-v4l2",     "hw-csis",     "control"),

        # Processing column — vertical SW/control
        _e("e-proc-app-fw",  "app-recorder", "fw-media-rec", "control"),
        _e("e-proc-fw-hal",  "fw-media-rec", "hal-codec2",   "control"),
        _e("e-proc-hal-ker", "hal-codec2",   "ker-mfc-drv",  "control"),
        _e("e-proc-ker-hw",  "ker-mfc-drv",  "hw-mlsc",      "control"),

        # HAL horizontal — vOTF (bidirectional, Camera HAL ↔ Codec2 HAL)
        _e("e-hal-votf",  "hal-camera", "hal-codec2", "vOTF"),
        _e("e-hal-votf-r","hal-codec2", "hal-camera", "vOTF"),

        # Kernel horizontal
        _e("e-ker-otf",  "ker-v4l2",    "ker-mfc-drv", "OTF"),
        _e("e-ker-m2m",  "ker-mfc-drv", "ker-ion",     "M2M"),
        _e("e-ker-sw",   "ker-ion",     "ker-drm",     "control"),

        # HW lane — OTF chain
        _e("e-hw-sen-csis",  "hw-sensor", "hw-csis",  "OTF"),
        _e("e-hw-csis-isp",  "hw-csis",   "hw-isp",   "OTF"),
        _e("e-hw-isp-mlsc",  "hw-isp",    "hw-mlsc",  "OTF"),
        _e("e-hw-mlsc-mcsc", "hw-mlsc",   "hw-mcsc",  "OTF"),
        _e("e-hw-mcsc-mfc",  "hw-mcsc",   "hw-mfc",   "M2M"),
        _e("e-hw-mfc-dpu",   "hw-mfc",    "hw-dpu",   "M2M"),

        # HW → Buffer writes (M2M vertical)
        _e("e-isp-buf-yuv",   "hw-isp",  "buf-yuv",    "M2M"),
        _e("e-mfc-buf-out",   "hw-mfc",  "buf-enc-out", "M2M"),
        _e("e-dpu-buf-disp",  "hw-dpu",  "buf-disp",   "M2M"),

        # Buffer lane — vOTF chain (left to right)
        _e("e-buf-raw-yuv",  "buf-raw",    "buf-yuv",    "vOTF"),
        _e("e-buf-yuv-ein",  "buf-yuv",    "buf-enc-in", "vOTF"),
        _e("e-buf-ein-eout", "buf-enc-in", "buf-enc-out","vOTF"),

        # Risk edge — MFC latency (HW → Kernel crossing)
        _e("e-risk-mfc", "hw-mfc", "ker-mfc-drv", "risk",
           label="Latency > budget"),
    ]

    # ── Summary & risks ───────────────────────────────────────────────────
    summary = ViewSummary(
        scenario_id="uc-camera-recording",
        variant_id="FHD30-SDR-H265",
        name="Video Recording",
        subtitle="FHD 30fps, 1920x1080",
        period_ms=33.3,
        budget_ms=30.0,
        resolution="1920 x 1080",
        fps=30,
        variant_label="Samsung Exynos",
        notes=(
            "Scenario captured on Exynos reference board. "
            "Measurements via SurfaceFlinger and systrace."
        ),
        captured_at="May 16, 2025 10:42 AM",
    )

    risks: list[RiskCard] = [
        RiskCard(
            id="R1",
            title="MFC Encode Latency High",
            component="MFC",
            description="Encode latency 28.6 ms exceeds budget 30.0 ms (95th percentile)",
            severity="High",
            impact="Budget Overrun",
        ),
        RiskCard(
            id="R2",
            title="DRAM Bandwidth High",
            component="MFC / Memory",
            description="Peak bandwidth 18.2 GB/s near sustained limit 20.0 GB/s",
            severity="Medium",
            impact="Throughput Risk",
        ),
    ]

    return ViewResponse(
        level=0,
        mode="architecture",
        scenario_id="uc-camera-recording",
        variant_id="FHD30-SDR-H265",
        nodes=nodes,
        edges=edges,
        risks=risks,
        summary=summary,
        metadata={"canvas_w": CANVAS_W, "canvas_h": CANVAS_H},
        overlays_available=["issues", "memory-path", "llc-allocation", "compression"],
    )


# ---------------------------------------------------------------------------
# Architecture mode — DB projection → 실좌표 ViewResponse (Phase 4 VIEW-01/02)
# ---------------------------------------------------------------------------

import graphlib

# ip_catalog.category → lane 매핑 (RESEARCH.md Pattern 1 — fixture 직접 검증)
CATEGORY_TO_LANE: dict[str, str] = {
    "camera":  "hw",   # CSIS, ISP (ip-csis-v8, ip-isp-v12)
    "codec":   "hw",   # MFC (ip-mfc-v14)
    "display": "hw",   # DPU (ip-dpu-v9)
    "memory":  "hw",   # LLC (ip-llc-v2)
}

STAGE_STEP: int = 310  # px per stage level (capture→processing 간격 기반)


def _projection_to_view_response(projection: dict) -> ViewResponse:
    """get_view_projection() dict → 실좌표 ViewResponse (architecture mode).

    1. ip_catalog lookup: ip_ref → category → lane
    2. graphlib.TopologicalSorter로 stage_index 계산
    3. LANE_Y[lane] for y, LANE_LABEL_W + stage_idx * STAGE_STEP + offset for x
    4. pipeline edges → EdgeElement 변환
    """
    pipeline = projection.get("pipeline", {})
    nodes_raw = pipeline.get("nodes", [])
    edges_raw = pipeline.get("edges", [])

    # ip_catalog lookup dict: {ip_id: ip_dict}
    ip_catalog: dict[str, dict] = {
        ip["id"]: ip for ip in projection.get("ip_catalog", [])
    }

    # --- topological sort (graphlib) ---
    ts = graphlib.TopologicalSorter()
    node_ids = {n["id"] for n in nodes_raw}
    for n in nodes_raw:
        ts.add(n["id"])
    for e in edges_raw:
        src, tgt = e.get("from"), e.get("to")
        # self-loop 및 미등록 노드 방지
        if src and tgt and src != tgt and src in node_ids and tgt in node_ids:
            ts.add(tgt, src)  # tgt depends on src

    ts.prepare()
    stage_map: dict[str, int] = {}
    stage_idx = 0
    while ts.is_active():
        batch = list(ts.get_ready())
        for nid in batch:
            stage_map[nid] = stage_idx
        ts.done(*batch)
        stage_idx += 1

    # --- 노드 좌표 계산 ---
    nodes: list[NodeElement] = []
    for node in nodes_raw:
        nid = node.get("id")
        if not nid:
            continue
        ip_ref = node.get("ip_ref", "")
        ip_info = ip_catalog.get(ip_ref, {})
        category = ip_info.get("category", "")
        lane = CATEGORY_TO_LANE.get(category, "hw")
        s_idx = stage_map.get(nid, 0)
        x = float(LANE_LABEL_W + s_idx * STAGE_STEP + STAGE_STEP // 2)
        y = LANE_Y[lane]
        nodes.append(NodeElement(
            data=NodeData(
                id=nid,
                label=node.get("label", nid),
                type="ip",
                layer=lane,
            ),
            position={"x": x, "y": y},
        ))

    # --- 엣지 변환 ---
    _valid_flow_types = {"OTF", "vOTF", "M2M", "control", "risk"}
    edges: list[EdgeElement] = []
    for e in edges_raw:
        src = e.get("from")
        tgt = e.get("to")
        if not src or not tgt:
            continue
        etype = e.get("type", "M2M")
        flow_type = etype if etype in _valid_flow_types else "M2M"
        edge_id = f"e-{src}-{tgt}"
        edges.append(EdgeElement(data=EdgeData(
            id=edge_id, source=src, target=tgt, flow_type=flow_type,
        )))

    # --- ViewSummary (placeholder — Wave 2에서 보완) ---
    summary = ViewSummary(
        scenario_id=projection.get("scenario_id", ""),
        variant_id=projection.get("variant_id", ""),
        name=projection.get("project_name") or projection.get("scenario_id", ""),
        subtitle="",
        period_ms=0.0,
        budget_ms=0.0,
        resolution="",
        fps=0,
        variant_label="",
    )

    return ViewResponse(
        level=0,
        mode="architecture",
        scenario_id=projection.get("scenario_id", ""),
        variant_id=projection.get("variant_id", ""),
        nodes=nodes,
        edges=edges,
        risks=[],
        summary=summary,
    )


def _sw_stack_to_view_response(projection: dict) -> ViewResponse:
    """topology mode: sw_stack 섹션 → SW 노드 + SW→HW control edges + HW 노드.

    VIEW-03: SW task/thread 레이어 중심 레이아웃.
    - projection["pipeline"]["sw_stack"] → SW 노드 (layer in app/framework/hal/kernel)
    - ip_ref 있는 SW 노드 → HW 노드로 control 엣지 생성
    - HW 노드는 _projection_to_view_response()에서 재사용 (architecture mode 동일 좌표)
    """
    pipeline = projection.get("pipeline", {})
    sw_stack_raw = pipeline.get("sw_stack", [])

    # 레이어별 X 시작좌표 (같은 레이어 내 노드들을 X_STEP 간격으로 배치)
    X_START = LANE_LABEL_W + STAGE_STEP // 2  # 235px
    X_STEP = 180  # 같은 레이어 내 노드 간 간격

    layer_x_counter: dict[str, int] = {}  # 레이어별 노드 누적 인덱스

    sw_nodes: list[NodeElement] = []
    sw_node_ids: set[str] = set()

    for sw in sw_stack_raw:
        layer = sw.get("layer", "app")
        nid = sw.get("id", "")
        label = sw.get("label", nid)
        if not nid:
            continue
        idx = layer_x_counter.get(layer, 0)
        x = float(X_START + idx * X_STEP)
        y = LANE_Y[layer]
        layer_x_counter[layer] = idx + 1
        sw_node_ids.add(nid)
        sw_nodes.append(NodeElement(
            data=NodeData(id=nid, label=label, type="sw", layer=layer),
            position={"x": x, "y": y},
        ))

    # HW 노드 (architecture mode와 동일한 좌표) — topology에서도 표시
    hw_view = _projection_to_view_response(projection)
    hw_node_ids = {n.data.id for n in hw_view.nodes}

    # SW→HW control edges (ip_ref 있는 sw_stack 노드만)
    sw_hw_edges: list[EdgeElement] = []
    for sw in sw_stack_raw:
        nid = sw.get("id", "")
        ip_ref = sw.get("ip_ref")  # pipeline node id (e.g., "csis0", "mfc")
        if ip_ref and ip_ref in hw_node_ids:
            edge_id = f"e-sw-{nid}-{ip_ref}"
            sw_hw_edges.append(EdgeElement(data=EdgeData(
                id=edge_id,
                source=nid,
                target=ip_ref,
                flow_type="control",  # Literal 제약: "OTF"/"vOTF"/"M2M"/"control"/"risk"
            )))

    # 노드/엣지 합산: SW + HW, SW→HW + HW→HW
    all_nodes = sw_nodes + hw_view.nodes
    all_edges = sw_hw_edges + hw_view.edges

    summary = ViewSummary(
        scenario_id=projection.get("scenario_id", ""),
        variant_id=projection.get("variant_id", ""),
        name=projection.get("project_name") or projection.get("scenario_id", ""),
        subtitle="topology mode",
        period_ms=0.0,
        budget_ms=0.0,
        resolution="",
        fps=0,
        variant_label="",
    )

    return ViewResponse(
        level=0,
        mode="topology",
        scenario_id=projection.get("scenario_id", ""),
        variant_id=projection.get("variant_id", ""),
        nodes=all_nodes,
        edges=all_edges,
        risks=[],
        summary=summary,
    )


def project_level0(scenario_id: str, variant_id: str, *, mode: str = "architecture", db=None) -> ViewResponse:
    """Level 0 view — DB projection 기반 (Phase 4 D-01).

    mode='architecture': get_view_projection() 결과를 실좌표 NodeElement 리스트로 변환.
    mode='topology': sw_stack 기반 SW 노드 + SW→HW control edge 생성 (VIEW-03).
    db=None: dashboard demo 모드 — sample data fallback.
    """
    if mode not in ("architecture", "topology"):
        raise NotImplementedError(f"mode '{mode}' is not supported")

    if db is None:
        return build_sample_level0()

    from scenario_db.db.repositories.view_projection import get_view_projection
    from fastapi import HTTPException
    projection = get_view_projection(db, scenario_id, variant_id)
    if projection is None:
        raise HTTPException(
            status_code=404,
            detail=f"scenario '{scenario_id}' / variant '{variant_id}' not found",
        )

    if mode == "architecture":
        return _projection_to_view_response(projection)
    else:  # topology
        return _sw_stack_to_view_response(projection)


def project_level1(scenario_id: str, variant_id: str, db=None) -> ViewResponse:
    raise NotImplementedError("Level 1 IP DAG projection is Phase C work")


def project_level2(scenario_id: str, variant_id: str, expand: str, db=None) -> ViewResponse:
    raise NotImplementedError("Level 2 composite-IP drill-down is Phase C work")
