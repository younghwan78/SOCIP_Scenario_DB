from __future__ import annotations

from scenario_db.models.capability.hw import PortType
from scenario_db.models.definition.usecase import PortInputConfig
from scenario_db.models.evidence.simulation import PortBWResult
from scenario_db.sim.constants import BPP_MAP, BW_POWER_COEFF_DEFAULT


def calc_port_bw(
    port: PortInputConfig,
    ip_name: str,
    port_type: PortType,
    fps: float,
    bw_power_coeff: float = BW_POWER_COEFF_DEFAULT,
) -> PortBWResult:
    """DMA 포트 BW(MB/s) + 전력(mW) 계산.

    OTF 포트(OTF_IN/OTF_OUT)는 DRAM 액세스 없으므로 bw_mbs=0 반환.

    BW 공식 (설계 문서 §2.2):
        bw_mbs = comp_ratio * fps * width * height * (bitwidth/8) * BPP / 1e6
        bw_power_mw = bw_mbs * bw_power_coeff / 1000 * llc_weight

    주의사항:
    - compression="disable"이면 port.comp_ratio 무시하고 1.0 사용 (Pitfall 4)
    - llc_enabled=False이면 port.llc_weight 무시하고 1.0 사용
    - PortType enum으로 판별 (문자열 비교 금지 — RESEARCH.md Anti-Patterns)
    """
    # OTF 포트는 DRAM 액세스 없음
    if port_type in (PortType.OTF_IN, PortType.OTF_OUT):
        return PortBWResult(
            ip=ip_name,
            port=port.port,
            direction="read",   # OTF는 방향 무관 — Literal 제약 충족용
            bw_mbs=0.0,
            bw_power_mw=0.0,
        )

    bpp = BPP_MAP.get(port.format, 1.0)
    # compression="disable"이면 comp_ratio 무시 (Pitfall 4)
    comp_ratio = port.comp_ratio if port.compression != "disable" else 1.0
    # llc_enabled=False이면 llc_weight 무시
    llc_weight = port.llc_weight if port.llc_enabled else 1.0

    bw_mbs: float = (
        comp_ratio * fps * port.width * port.height * (port.bitwidth / 8) * bpp / 1e6
    )
    bw_power_mw: float = bw_mbs * bw_power_coeff / 1000.0 * llc_weight

    # worst-case BW (comp_ratio_max 설정 시)
    bw_mbs_worst: float | None = None
    if port.comp_ratio_max is not None and port.compression != "disable":
        bw_mbs_worst = (
            port.comp_ratio_max
            * fps * port.width * port.height * (port.bitwidth / 8) * bpp / 1e6
        )

    direction = "read" if port_type == PortType.DMA_READ else "write"

    return PortBWResult(
        ip=ip_name,
        port=port.port,
        direction=direction,
        bw_mbs=bw_mbs,
        bw_mbs_worst=bw_mbs_worst,
        bw_power_mw=bw_power_mw,
        format=port.format,
        compression=port.compression,
        llc_enabled=port.llc_enabled,
    )
