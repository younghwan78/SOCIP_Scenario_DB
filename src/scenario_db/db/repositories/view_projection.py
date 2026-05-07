"""Level 0 lane data 조회 Repository (DB-03).

Phase 3 view router (mode=architecture|topology 파라미터)가 소비하는
Level 0 lane data를 조회한다. Phase 4에서 Streamlit viewer에 연동된다.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from scenario_db.db.models.capability import IpCatalog
from scenario_db.db.models.definition import Project, Scenario, ScenarioVariant


def get_view_projection(
    db: Session,
    scenario_id: str,
    variant_id: str,
) -> dict | None:
    """Level 0 lane data 조회 — Phase 3 view router가 소비.

    반환 구조:
    {
        "scenario_id": str,
        "variant_id": str,
        "project_name": str | None,
        "pipeline": dict,          # scenario.pipeline JSONB 그대로
        "ip_catalog": list[dict],  # pipeline 노드가 참조하는 IpCatalog 목록
        "lanes": list[dict],       # pipeline.nodes에서 lane_id 기준으로 그룹화
    }
    존재하지 않는 scenario_id 또는 variant_id → None 반환.
    """
    # Scenario 조회
    scenario = db.query(Scenario).filter_by(id=scenario_id).one_or_none()
    if scenario is None:
        return None

    # Variant 조회 (복합 PK: scenario_id + id)
    variant = (
        db.query(ScenarioVariant)
        .filter_by(scenario_id=scenario_id, id=variant_id)
        .one_or_none()
    )
    if variant is None:
        return None

    # Project name 조회 (optional)
    project = db.query(Project).filter_by(id=scenario.project_ref).one_or_none()
    project_name = (project.metadata_ or {}).get("name") if project else None

    # Pipeline nodes에서 ip_ref 수집 → IpCatalog 조회
    pipeline = scenario.pipeline or {}
    nodes = pipeline.get("nodes", [])
    ip_refs = {node["ip_ref"] for node in nodes if "ip_ref" in node}
    if ip_refs:
        ip_rows = db.query(IpCatalog).filter(IpCatalog.id.in_(ip_refs)).all()
    else:
        ip_rows = []
    ip_catalog = [
        {
            "id": ip.id,
            "category": ip.category,
            "hierarchy": ip.hierarchy,
            "capabilities": ip.capabilities,
        }
        for ip in ip_rows
    ]

    # Lane 그룹화: pipeline.nodes를 lane_id 기준으로 그룹화
    # lane_id가 없는 노드는 "default" lane에 배치
    lanes_map: dict[str, list[dict]] = {}
    for node in nodes:
        lane_id = node.get("lane_id", "default")
        lanes_map.setdefault(lane_id, []).append(node)
    lanes = [
        {"lane_id": lid, "nodes": lane_nodes}
        for lid, lane_nodes in lanes_map.items()
    ]

    return {
        "scenario_id": scenario_id,
        "variant_id": variant_id,
        "project_name": project_name,
        "pipeline": pipeline,
        "ip_catalog": ip_catalog,
        "lanes": lanes,
    }
