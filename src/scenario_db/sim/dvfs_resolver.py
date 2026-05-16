from __future__ import annotations

import logging

from scenario_db.models.capability.hw import IPSimParams
from scenario_db.models.definition.usecase import (
    EdgeType,
    IPPortConfig,
    Pipeline,
    SensorSpec,
)
from scenario_db.sim.constants import REFERENCE_VOLTAGE_MV
from scenario_db.sim.models import DVFSTable, ResolvedIPConfig

logger = logging.getLogger(__name__)


class DvfsResolver:
    """BW/Power/Timing 계산에 앞서 각 IP의 DVFS 레벨(클럭/전압)을 결정한다.

    핵심 알고리즘 (설계 문서 §2.2, §12.3):
    1. 각 IP별 required_clock 계산 (M2M 기준: pixels*fps/((1-sw_margin)*ppc)/1e6)
    2. OTF 그룹 탐색 (Pipeline.edges[type=OTF]) -> sensor v_valid_time 기반 required_clock 대체
       - OTF 그룹에는 sw_margin 미적용 (Pitfall 2)
    3. 같은 dvfs_group -> max(required_clock) 정렬
    4. DVFSTable.find_min_level(required_clock, asv_group) -> DVFSLevel
       - 없으면 Fallback: set_clock=required, voltage=710mV + logging.warning (D-03)
    5. 같은 vdd 도메인 -> max(set_voltage_mv) 정렬 (Pitfall 3)
    """

    def __init__(
        self,
        dvfs_tables: dict[str, DVFSTable],
        asv_group: int = 4,
    ) -> None:
        self.dvfs_tables = dvfs_tables
        self.asv_group = asv_group

    def _required_clock_m2m_mhz(
        self,
        pixels: int,
        fps: float,
        ppc: float,
        sw_margin: float,
    ) -> float:
        """M2M 포트 기준 required_clock (MHz)."""
        return pixels * fps / ((1.0 - sw_margin) * ppc) / 1e6

    def _required_clock_otf_mhz(
        self,
        frame_pixels: int,
        fps: float,
        v_valid_ratio: float,
        ppc: float,
    ) -> float:
        """센서 v_valid_time 기반 OTF 그룹 required_clock (MHz).
        OTF 그룹에는 sw_margin 미적용 (설계 문서 §12.3).
        """
        v_valid_time = (1.0 / fps) * v_valid_ratio
        required_throughput_pps = frame_pixels / v_valid_time
        return required_throughput_pps / ppc / 1e6

    def resolve(
        self,
        ip_params: dict[str, IPSimParams],
        port_configs: dict[str, IPPortConfig],
        pipeline: Pipeline,
        fps: float,
        sw_margin: float = 0.25,
        sensor_spec: SensorSpec | None = None,
        dvfs_overrides: dict[str, int] | None = None,
    ) -> dict[str, ResolvedIPConfig]:
        """반환: node_id -> ResolvedIPConfig.

        Args:
            ip_params: node_id -> IPSimParams
            port_configs: node_id -> IPPortConfig (sw_margin_override 포함)
            pipeline: OTF 엣지 탐색용
            fps: 목표 FPS
            sw_margin: 기본 SW 마진 (SimGlobalConfig.sw_margin)
            sensor_spec: OTF 그룹 v_valid_time 계산용 (없으면 OTF 제약 비적용)
            dvfs_overrides: node_id -> level 번호 강제 (SimGlobalConfig.dvfs_overrides)
        """
        # ------------------------------------------------------------------
        # Step 1: OTF 그룹 탐색 (Pipeline.edges에서 OTF 타입 추출)
        # ------------------------------------------------------------------
        otf_node_ids: set[str] = set()
        for edge in pipeline.edges:
            if edge.type == EdgeType.OTF:
                otf_node_ids.add(edge.from_)
                otf_node_ids.add(edge.to)

        # ------------------------------------------------------------------
        # Step 2: 각 IP별 required_clock 계산
        # ------------------------------------------------------------------
        required_clocks: dict[str, float] = {}
        for node_id, params in ip_params.items():
            # sw_margin_override 처리
            effective_margin = sw_margin
            pc = port_configs.get(node_id)
            if pc and pc.sw_margin_override is not None:
                effective_margin = pc.sw_margin_override

            # OTF 그룹이고 sensor_spec 있으면 OTF 기준 required_clock 사용
            if node_id in otf_node_ids and sensor_spec is not None:
                frame_pixels = sensor_spec.frame_width * sensor_spec.frame_height
                req = self._required_clock_otf_mhz(
                    frame_pixels=frame_pixels,
                    fps=sensor_spec.fps,
                    v_valid_ratio=sensor_spec.v_valid_ratio,
                    ppc=params.ppc,
                )
            else:
                # M2M 기준: port_configs의 output/input 포트 해상도 사용
                pixels = self._get_pixels_from_port_config(node_id, port_configs)
                req = self._required_clock_m2m_mhz(
                    pixels=pixels,
                    fps=fps,
                    ppc=params.ppc,
                    sw_margin=effective_margin,
                )

            required_clocks[node_id] = req

        # ------------------------------------------------------------------
        # Step 3: 같은 dvfs_group 내에서 max(required_clock) 정렬
        # ------------------------------------------------------------------
        group_max: dict[str, float] = {}
        for node_id, params in ip_params.items():
            group = params.dvfs_group
            req = required_clocks.get(node_id, 0.0)
            group_max[group] = max(group_max.get(group, 0.0), req)

        # ------------------------------------------------------------------
        # Step 4: DVFSTable 룩업 (또는 fallback)
        # ------------------------------------------------------------------
        resolved: dict[str, ResolvedIPConfig] = {}
        for node_id, params in ip_params.items():
            group = params.dvfs_group
            effective_req = group_max.get(group, required_clocks.get(node_id, 0.0))

            # dvfs_overrides 처리 (runner에서 전달)
            override_level: int | None = None
            if dvfs_overrides:
                override_level = dvfs_overrides.get(node_id)

            table = self.dvfs_tables.get(group)
            if table is None:
                logger.warning(
                    "DVFS domain %r not found for IP %r (node %r) — "
                    "fallback: set_clock=%.2f MHz, voltage=%.1f mV",
                    group, params.hw_name_in_sim, node_id,
                    effective_req, REFERENCE_VOLTAGE_MV,
                )
                resolved[node_id] = ResolvedIPConfig(
                    ip_name=params.hw_name_in_sim,
                    required_clock_mhz=effective_req,
                    set_clock_mhz=effective_req,
                    set_voltage_mv=REFERENCE_VOLTAGE_MV,
                    dvfs_group=group,
                    vdd=params.vdd,
                )
                continue

            # override level 처리
            if override_level is not None:
                lv = next((lv for lv in table.levels if lv.level == override_level), None)
                if lv is None:
                    logger.warning(
                        "DVFS override level %d not found in domain %r for node %r — using required clock",
                        override_level, group, node_id,
                    )
                    lv = table.find_min_level(effective_req, self.asv_group)
            else:
                lv = table.find_min_level(effective_req, self.asv_group)

            if lv is None:
                # 모든 레벨이 부족 -> fallback
                logger.warning(
                    "No DVFS level in domain %r covers %.2f MHz for IP %r — fallback",
                    group, effective_req, node_id,
                )
                set_clock = effective_req
                set_voltage = REFERENCE_VOLTAGE_MV
            else:
                set_clock = lv.speed_mhz
                set_voltage = float(lv.voltages.get(self.asv_group, REFERENCE_VOLTAGE_MV))

            resolved[node_id] = ResolvedIPConfig(
                ip_name=params.hw_name_in_sim,
                required_clock_mhz=effective_req,
                set_clock_mhz=set_clock,
                set_voltage_mv=set_voltage,
                dvfs_group=group,
                vdd=params.vdd,
            )

        # ------------------------------------------------------------------
        # Step 5: 같은 vdd 도메인 -> max(set_voltage_mv) 정렬 (Pitfall 3)
        # ------------------------------------------------------------------
        vdd_max_voltage: dict[str, float] = {}
        for r in resolved.values():
            vdd_max_voltage[r.vdd] = max(
                vdd_max_voltage.get(r.vdd, 0.0),
                r.set_voltage_mv,
            )

        final_resolved: dict[str, ResolvedIPConfig] = {}
        for node_id, r in resolved.items():
            vdd = r.vdd
            max_v = vdd_max_voltage.get(vdd, r.set_voltage_mv)
            if r.set_voltage_mv < max_v:
                final_resolved[node_id] = ResolvedIPConfig(
                    ip_name=r.ip_name,
                    required_clock_mhz=r.required_clock_mhz,
                    set_clock_mhz=r.set_clock_mhz,
                    set_voltage_mv=max_v,
                    dvfs_group=r.dvfs_group,
                    vdd=vdd,
                )
            else:
                final_resolved[node_id] = r

        return final_resolved

    def _get_pixels_from_port_config(
        self,
        node_id: str,
        port_configs: dict[str, IPPortConfig],
    ) -> int:
        """port_configs에서 처리 해상도(픽셀) 추출. 없으면 FHD(2073600) 기본값."""
        pc = port_configs.get(node_id)
        if pc:
            # multi-output IP 대응: 최대 해상도 포트 사용 (과소 산정 방지)
            if pc.outputs:
                return max(p.width * p.height for p in pc.outputs)
            if pc.inputs:
                return max(p.width * p.height for p in pc.inputs)
        return 1920 * 1080   # FHD 기본값
