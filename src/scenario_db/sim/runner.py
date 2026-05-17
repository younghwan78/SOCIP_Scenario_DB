from __future__ import annotations

"""sim/ 패키지 최상위 오케스트레이터.

DB/ORM 의존 없음 (D-05) — Phase 7 라우터가 ORM row -> Pydantic 변환 후 호출.
"""

from scenario_db.models.capability.hw import IpCatalog, PortType
from scenario_db.models.definition.usecase import (
    IPPortConfig,
    Pipeline,
    SensorSpec,
    SimGlobalConfig,
)
from scenario_db.models.evidence.simulation import IPTimingResult, PortBWResult
from scenario_db.sim.bw_calc import calc_port_bw
from scenario_db.sim.dvfs_resolver import DvfsResolver
from scenario_db.sim.models import DVFSTable, ResolvedIPConfig, SimRunResult
from scenario_db.sim.perf_calc import calc_processing_time
from scenario_db.sim.power_calc import calc_active_power
from scenario_db.sim.scenario_adapter import _resolve_ip_name, build_ip_params


def run_simulation(
    scenario_id: str,
    variant_id: str,
    pipeline: Pipeline,
    ip_catalog: dict[str, IpCatalog],
    dvfs_tables: dict[str, DVFSTable],
    variant_port_config: dict[str, IPPortConfig],
    sim_config: SimGlobalConfig,
    sensor_spec: SensorSpec | None = None,
    fps: float = 30.0,
) -> SimRunResult:
    """전체 BW/Power/DVFS/Timing 계산 파이프라인 (D-05: 순수 Pydantic 함수).

    실행 순서:
    1. ip_params 구성 (sim_params 없는 IP 제외)
    2. DvfsResolver.resolve() -> node_id -> ResolvedIPConfig
    3. 각 IP별 DMA 포트 BW 계산 -> dma_breakdown
    4. 각 IP별 처리시간 계산 -> timing_breakdown
    5. 각 IP별 Active Power 계산 -> VDD 도메인 집계
    6. SimRunResult 조립

    Args:
        fps: 목표 FPS — sensor_spec.fps가 있으면 그것을 우선 사용
    """
    # sensor_spec.fps 우선 적용
    effective_fps: float = sensor_spec.fps if sensor_spec is not None else fps

    # ------------------------------------------------------------------
    # Step 1: ip_params 구성
    # ------------------------------------------------------------------
    ip_params = build_ip_params(pipeline=pipeline, ip_catalog=ip_catalog)

    # ------------------------------------------------------------------
    # Step 2: DVFS resolve
    # ------------------------------------------------------------------
    resolver = DvfsResolver(dvfs_tables=dvfs_tables, asv_group=sim_config.asv_group)
    resolved: dict[str, ResolvedIPConfig] = resolver.resolve(
        ip_params=ip_params,
        port_configs=variant_port_config,
        pipeline=pipeline,
        fps=effective_fps,
        sw_margin=sim_config.sw_margin,
        sensor_spec=sensor_spec,
        dvfs_overrides=sim_config.dvfs_overrides or None,
    )

    # ------------------------------------------------------------------
    # Step 3: DMA 포트 BW 계산
    # ------------------------------------------------------------------
    dma_breakdown: list[PortBWResult] = []

    for node in pipeline.nodes:
        node_id = node.id
        if node_id not in ip_params:
            continue  # sim_params 없는 IP 건너뜀

        params = ip_params[node_id]
        ip_name = _resolve_ip_name(node.ip_ref, ip_catalog)
        port_cfg = variant_port_config.get(node_id)
        if port_cfg is None:
            continue

        # IPSimParams.ports에서 각 포트의 PortType 조회
        port_type_map: dict[str, PortType] = {ps.name: ps.type for ps in params.ports}

        # inputs 포트 처리 (DMA_READ 기본값)
        for port_input in port_cfg.inputs:
            port_type = port_type_map.get(port_input.port, PortType.DMA_READ)
            bw_result = calc_port_bw(
                port=port_input,
                ip_name=ip_name,
                port_type=port_type,
                fps=effective_fps,
                bw_power_coeff=sim_config.bw_power_coeff,
            )
            dma_breakdown.append(bw_result)

        # outputs 포트 처리 (DMA_WRITE 기본값)
        for port_output in port_cfg.outputs:
            port_type = port_type_map.get(port_output.port, PortType.DMA_WRITE)
            bw_result = calc_port_bw(
                port=port_output,
                ip_name=ip_name,
                port_type=port_type,
                fps=effective_fps,
                bw_power_coeff=sim_config.bw_power_coeff,
            )
            dma_breakdown.append(bw_result)

    # ------------------------------------------------------------------
    # Step 4: 처리시간 계산
    # ------------------------------------------------------------------
    timing_breakdown: list[IPTimingResult] = []
    frame_interval_ms = 1000.0 / effective_fps

    for node in pipeline.nodes:
        node_id = node.id
        if node_id not in resolved:
            continue

        params = ip_params.get(node_id)
        if params is None:
            continue

        ip_name = _resolve_ip_name(node.ip_ref, ip_catalog)
        r = resolved[node_id]

        # 처리 해상도: multi-output IP 대응을 위해 최대 해상도 포트 사용
        port_cfg = variant_port_config.get(node_id)
        pixels: int = 1920 * 1080  # 기본값 FHD
        if port_cfg:
            if port_cfg.outputs:
                pixels = max(p.width * p.height for p in port_cfg.outputs)
            elif port_cfg.inputs:
                pixels = max(p.width * p.height for p in port_cfg.inputs)

        hw_time_ms = calc_processing_time(
            pixels=pixels,
            set_clock_mhz=r.set_clock_mhz,
            ppc=params.ppc,
            h_blank_margin=sim_config.h_blank_margin,
        )
        feasible = hw_time_ms <= frame_interval_ms

        timing_breakdown.append(IPTimingResult(
            ip=ip_name,
            hw_time_ms=hw_time_ms,
            required_clock_mhz=r.required_clock_mhz,
            set_clock_mhz=r.set_clock_mhz,
            set_voltage_mv=r.set_voltage_mv,
            feasible=feasible,
        ))

    # ------------------------------------------------------------------
    # Step 5: Active Power 계산 + VDD 집계
    # ------------------------------------------------------------------
    vdd_power: dict[str, float] = {}
    ip_power: dict[str, float] = {}          # Phase 7 추가 (D-06)
    total_power_mw: float = 0.0

    for node in pipeline.nodes:
        node_id = node.id
        if node_id not in resolved:
            continue

        params = ip_params.get(node_id)
        if params is None:
            continue

        r = resolved[node_id]
        port_cfg = variant_port_config.get(node_id)
        width, height = 1920, 1080
        if port_cfg:
            # multi-output IP 대응: 최대 해상도 포트 기준
            if port_cfg.outputs:
                max_port = max(port_cfg.outputs, key=lambda p: p.width * p.height)
                width, height = max_port.width, max_port.height
            elif port_cfg.inputs:
                max_port = max(port_cfg.inputs, key=lambda p: p.width * p.height)
                width, height = max_port.width, max_port.height

        power_mw = calc_active_power(
            unit_power_mw_mp=params.unit_power_mw_mp,
            width=width,
            height=height,
            set_voltage_mv=r.set_voltage_mv,
            fps=effective_fps,
        )
        # idc (idle/static current) 는 의도적으로 미적용 — 현재 scope는 active power만 계산.
        # params.idc 기본값=0.0이므로 IP 정지 전류(leakage) 포함 시 여기에 추가할 것.
        total_power_mw += power_mw
        vdd_power[r.vdd] = vdd_power.get(r.vdd, 0.0) + power_mw
        ip_name = _resolve_ip_name(node.ip_ref, ip_catalog)
        ip_power[ip_name] = ip_power.get(ip_name, 0.0) + power_mw  # D-06

    # BW 전력 합산
    bw_total_mbs = sum(r.bw_mbs for r in dma_breakdown)
    bw_power_total = sum(r.bw_power_mw for r in dma_breakdown)
    total_power_mw += bw_power_total

    # total_power_ma = total_power_mw [mW] / (vbat_V [V] * pmic_eff) [mA]
    # 단위: mW / V = mA (pmic_eff는 무차원)
    total_power_ma = (
        total_power_mw / (sim_config.vbat * sim_config.pmic_eff)
        if sim_config.vbat > 0 and sim_config.pmic_eff > 0
        else 0.0
    )

    # timing_breakdown이 비어있으면 sim_params 있는 IP가 없음 → 계산 미수행으로 feasible=False 처리
    if not timing_breakdown:
        return SimRunResult(
            scenario_id=scenario_id,
            variant_id=variant_id,
            total_power_mw=total_power_mw,
            total_power_ma=total_power_ma,
            bw_total_mbs=bw_total_mbs,
            hw_time_max_ms=0.0,
            feasible=False,
            infeasible_reason="No IP with sim_params found in pipeline — calculation not performed",
            resolved=resolved,
            dma_breakdown=dma_breakdown,
            timing_breakdown=[],
            vdd_power=vdd_power,
            ip_power=ip_power,
        )

    hw_time_max_ms = max((t.hw_time_ms for t in timing_breakdown), default=0.0)
    all_feasible = all(t.feasible for t in timing_breakdown)
    infeasible_reason: str | None = None
    if not all_feasible and timing_breakdown:
        worst = max(timing_breakdown, key=lambda t: t.hw_time_ms)
        infeasible_reason = (
            f"{worst.ip} hw_time={worst.hw_time_ms:.3f}ms > frame_interval={frame_interval_ms:.3f}ms"
        )

    return SimRunResult(
        scenario_id=scenario_id,
        variant_id=variant_id,
        total_power_mw=total_power_mw,
        total_power_ma=total_power_ma,
        bw_total_mbs=bw_total_mbs,
        hw_time_max_ms=hw_time_max_ms,
        feasible=all_feasible,
        infeasible_reason=infeasible_reason,
        resolved=resolved,
        dma_breakdown=dma_breakdown,
        timing_breakdown=timing_breakdown,
        vdd_power=vdd_power,
        ip_power=ip_power,
    )
