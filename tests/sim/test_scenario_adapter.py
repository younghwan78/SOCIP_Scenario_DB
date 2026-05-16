from __future__ import annotations

import logging

import pytest

from scenario_db.models.capability.hw import IpCatalog, IPSimParams, IpCapabilities, IpHierarchy
from scenario_db.models.definition.usecase import Pipeline, PipelineNode
from scenario_db.sim.scenario_adapter import build_ip_params, _resolve_ip_name


def _make_ip_catalog(ip_ref: str, sim_params: IPSimParams | None) -> IpCatalog:
    """테스트용 최소 IpCatalog 생성 헬퍼."""
    return IpCatalog(
        id=ip_ref,
        schema_version="2.2",
        kind="ip",
        category="ISP",
        hierarchy=IpHierarchy(type="simple"),
        capabilities=IpCapabilities(),
        sim_params=sim_params,
    )


def test_build_ip_params_success(isp_sim_params: IPSimParams) -> None:
    """sim_params 있는 IP -> node_id: IPSimParams 맵 반환."""
    pipeline = Pipeline(nodes=[PipelineNode(id="isp0", ip_ref="ip-isp-v12")])
    ip_catalog = {"ip-isp-v12": _make_ip_catalog("ip-isp-v12", isp_sim_params)}

    result = build_ip_params(pipeline=pipeline, ip_catalog=ip_catalog)

    assert "isp0" in result
    assert result["isp0"] is isp_sim_params


def test_build_ip_params_skips_missing(isp_sim_params: IPSimParams, caplog: pytest.LogCaptureFixture) -> None:
    """sim_params 없는 IP -> 제외 + logging.warning."""
    pipeline = Pipeline(nodes=[
        PipelineNode(id="isp0", ip_ref="ip-isp-v12"),
        PipelineNode(id="unknown", ip_ref="ip-unknown"),
    ])
    ip_catalog = {
        "ip-isp-v12": _make_ip_catalog("ip-isp-v12", isp_sim_params),
        "ip-unknown": _make_ip_catalog("ip-unknown", None),  # sim_params 없음
    }

    with caplog.at_level(logging.WARNING, logger="scenario_db.sim.scenario_adapter"):
        result = build_ip_params(pipeline=pipeline, ip_catalog=ip_catalog)

    assert "isp0" in result
    assert "unknown" not in result
    assert len(caplog.records) > 0


def test_resolve_ip_name_from_catalog(isp_sim_params: IPSimParams) -> None:
    """sim_params.hw_name_in_sim을 우선 사용."""
    ip_catalog = {"ip-isp-v12": _make_ip_catalog("ip-isp-v12", isp_sim_params)}
    name = _resolve_ip_name("ip-isp-v12", ip_catalog)
    assert name == "ISP"


def test_resolve_ip_name_fallback() -> None:
    """sim_params 없음 -> ip_ref 파싱 fallback ('ip-isp-v12' -> 'ISP')."""
    ip_catalog = {"ip-isp-v12": _make_ip_catalog("ip-isp-v12", None)}
    name = _resolve_ip_name("ip-isp-v12", ip_catalog)
    assert name == "ISP"


def test_resolve_ip_name_fallback_not_in_catalog() -> None:
    """카탈로그에 없는 ip_ref -> ip_ref 파싱 fallback."""
    name = _resolve_ip_name("ip-mfc-v2", {})
    assert name == "MFC"
