from __future__ import annotations

"""scenario_adapter.py — ip_ref resolve + runner 입력 조립 (D-05: DB import 없음).

Phase 7 라우터가 ORM row -> Pydantic 변환 후 호출하므로 이 모듈에는 sqlalchemy/DB import 없음.
"""

import logging

from scenario_db.models.capability.hw import IpCatalog, IPSimParams
from scenario_db.models.definition.usecase import Pipeline

logger = logging.getLogger(__name__)


def _resolve_ip_name(ip_ref: str, ip_catalog: dict[str, IpCatalog]) -> str:
    """ip_ref -> hw_name_in_sim 변환 (설계 문서 §12.6).

    우선순위: sim_params.hw_name_in_sim -> ip_ref 파싱 fallback
    예: "ip-isp-v12" -> "ISP"
    """
    catalog = ip_catalog.get(ip_ref)
    if catalog and catalog.sim_params:
        return catalog.sim_params.hw_name_in_sim
    # Fallback: "ip-isp-v12" -> parts[1].upper() = "ISP"
    # "ip-<name>-<ver>" 패턴을 요구; 불일치 시 warning 로그 출력
    parts = ip_ref.split("-")
    if len(parts) >= 3 and parts[0] == "ip":
        return parts[1].upper()
    logger.warning(
        "ip_ref %r does not match 'ip-<name>-<ver>' pattern — using ip_ref as-is",
        ip_ref,
    )
    return ip_ref.upper()


def build_ip_params(
    pipeline: Pipeline,
    ip_catalog: dict[str, IpCatalog],
) -> dict[str, IPSimParams]:
    """node_id -> IPSimParams 맵 구성.

    sim_params가 없는 IP는 계산에서 제외하고 logging.warning 출력 (D-04).
    """
    result: dict[str, IPSimParams] = {}
    for node in pipeline.nodes:
        catalog = ip_catalog.get(node.ip_ref)
        if catalog is None:
            logger.warning(
                "IP node %r: ip_ref %r not found in ip_catalog — 계산에서 제외",
                node.id, node.ip_ref,
            )
            continue
        if catalog.sim_params is None:
            logger.warning(
                "IP node %r (ip_ref=%r): sim_params 없음 — 계산에서 제외",
                node.id, node.ip_ref,
            )
            continue
        result[node.id] = catalog.sim_params
    return result
