from __future__ import annotations

import pytest
from pydantic import ValidationError

from scenario_db.db.repositories.scenario_graph import (
    CanonicalScenarioGraph,
    IpRecord,
    ScenarioRecord,
    SwProfileRecord,
    VariantRecord,
)
from scenario_db.resolver.engine import _version_gte, resolve
from scenario_db.resolver.models import IpResolution, ResolverResult, SwResolution


# ---------------------------------------------------------------------------
# Fixtures — minimal CanonicalScenarioGraph 빌더
# ---------------------------------------------------------------------------

def _make_graph(
    ip_requirements: dict | None = None,
    sw_requirements: dict | None = None,
    pipeline_nodes: list[dict] | None = None,
    ip_catalog: dict | None = None,
    sw_profiles: dict | None = None,
) -> CanonicalScenarioGraph:
    """테스트용 최소 CanonicalScenarioGraph 생성."""
    nodes = pipeline_nodes or []
    return CanonicalScenarioGraph(
        scenario_id="uc-test",
        variant_id="v-test",
        scenario=ScenarioRecord(
            id="uc-test",
            schema_version="2.2",
            project_ref="proj-test",
            metadata_={"name": "test"},
            pipeline={"nodes": nodes},
            yaml_sha256="abc",
        ),
        variant=VariantRecord(
            scenario_id="uc-test",
            id="v-test",
            ip_requirements=ip_requirements,
            sw_requirements=sw_requirements,
        ),
        pipeline={"nodes": nodes},
        ip_catalog=ip_catalog or {},
        sw_profiles=sw_profiles or {},
        evidence=[],
        issues=[],
        waivers=[],
        reviews=[],
    )


_ISP_CAPS = {
    "operating_modes": [
        {"id": "normal", "throughput_mpps": 500},
        {"id": "low_power", "throughput_mpps": 250},
        {"id": "high_throughput", "throughput_mpps": 800},
    ],
    "supported_features": {
        "bitdepth": [8, 10, 12],
        "hdr_formats": ["HDR10", "HDR10plus", "DolbyVision"],
        "compression": ["SBWC_v4", "AFBC_v2"],
    },
}

_MFC_CAPS = {
    "operating_modes": [
        {"id": "normal", "throughput_mpps": 120},
        {"id": "high_throughput", "throughput_mpps": 240},
    ],
    "supported_features": {
        "bitdepth": [8, 10],
        "hdr_formats": ["HDR10", "HDR10plus"],
        "compression": ["AFBC_v2"],
    },
}

_ISP_IP_RECORD = IpRecord(
    id="ip-isp-v12", schema_version="2.2", yaml_sha256="abc", capabilities=_ISP_CAPS
)
_MFC_IP_RECORD = IpRecord(
    id="ip-mfc-v14", schema_version="2.2", yaml_sha256="abc", capabilities=_MFC_CAPS
)

_PIPELINE_NODES = [
    {"id": "isp0", "ip_ref": "ip-isp-v12"},
    {"id": "mfc",  "ip_ref": "ip-mfc-v14"},
]
_IP_CATALOG = {
    "ip-isp-v12": _ISP_IP_RECORD,
    "ip-mfc-v14": _MFC_IP_RECORD,
}


# ---------------------------------------------------------------------------
# ResolverResult 모델 테스트
# ---------------------------------------------------------------------------

def test_resolver_result_empty():
    r = ResolverResult()
    assert r.ip_resolutions == []
    assert r.sw_resolutions == []
    assert r.unresolved_requirements == []
    assert r.warnings == []


def test_resolver_result_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        ResolverResult(unexpected="x")


def test_ip_resolution_model():
    r = IpResolution(node_id="isp0", catalog_id="ip-isp-v12", matched_modes=["normal"])
    assert r.node_id == "isp0"
    assert r.matched_modes == ["normal"]
    assert r.unmatched_reasons == []


# ---------------------------------------------------------------------------
# resolve() — 빈 케이스
# ---------------------------------------------------------------------------

def test_resolve_empty_ip_requirements():
    graph = _make_graph(ip_requirements={})
    result = resolve(graph)
    assert result.ip_resolutions == []
    assert result.unresolved_requirements == []


def test_resolve_none_ip_requirements():
    graph = _make_graph(ip_requirements=None)
    result = resolve(graph)
    assert result.ip_resolutions == []


# ---------------------------------------------------------------------------
# resolve() — IP throughput matching (D-01 all-matching)
# ---------------------------------------------------------------------------

def test_resolve_isp_throughput_498():
    """ISP required_throughput_mpps=498: normal(500✓), high_throughput(800✓), low_power(250✗)."""
    graph = _make_graph(
        ip_requirements={"isp0": {"required_throughput_mpps": 498}},
        pipeline_nodes=_PIPELINE_NODES,
        ip_catalog=_IP_CATALOG,
    )
    result = resolve(graph)
    assert len(result.ip_resolutions) == 1
    res = result.ip_resolutions[0]
    assert res.node_id == "isp0"
    assert "normal" in res.matched_modes
    assert "high_throughput" in res.matched_modes
    assert "low_power" not in res.matched_modes
    assert "isp0" not in result.unresolved_requirements


def test_resolve_isp_throughput_3981():
    """ISP required_throughput_mpps=3981 (8K): 모든 모드 불일치 → unresolved (D-03)."""
    graph = _make_graph(
        ip_requirements={"isp0": {"required_throughput_mpps": 3981}},
        pipeline_nodes=_PIPELINE_NODES,
        ip_catalog=_IP_CATALOG,
    )
    result = resolve(graph)
    assert len(result.ip_resolutions) == 1
    res = result.ip_resolutions[0]
    assert res.matched_modes == []
    assert "isp0" in result.unresolved_requirements


# ---------------------------------------------------------------------------
# resolve() — capability-level feature 체크
# ---------------------------------------------------------------------------

def test_resolve_isp_bitdepth_10():
    """required_bitdepth=10 → bitdepth [8,10,12]에 포함 → matched."""
    graph = _make_graph(
        ip_requirements={"isp0": {"required_bitdepth": 10}},
        pipeline_nodes=_PIPELINE_NODES,
        ip_catalog=_IP_CATALOG,
    )
    result = resolve(graph)
    res = result.ip_resolutions[0]
    assert len(res.matched_modes) == 3  # 모든 모드 통과 (throughput 조건 없음)
    assert "isp0" not in result.unresolved_requirements


def test_resolve_isp_bitdepth_16_unsupported():
    """required_bitdepth=16 → bitdepth [8,10,12]에 없음 → matched_modes=[] → unresolved."""
    graph = _make_graph(
        ip_requirements={"isp0": {"required_bitdepth": 16}},
        pipeline_nodes=_PIPELINE_NODES,
        ip_catalog=_IP_CATALOG,
    )
    result = resolve(graph)
    res = result.ip_resolutions[0]
    assert res.matched_modes == []
    assert "isp0" in result.unresolved_requirements


def test_resolve_isp_hdr_feature_hdr10():
    """required_features=['HDR10'] → hdr_formats에 포함 → pass."""
    graph = _make_graph(
        ip_requirements={"isp0": {"required_features": ["HDR10"]}},
        pipeline_nodes=_PIPELINE_NODES,
        ip_catalog=_IP_CATALOG,
    )
    result = resolve(graph)
    res = result.ip_resolutions[0]
    assert len(res.matched_modes) == 3
    assert not any("required_features:HDR10" in u for u in result.unresolved_requirements)


def test_resolve_isp_hdr_feature_av2_unsupported():
    """required_features=['AV2'] → hdr_formats에 없음 → unresolved."""
    graph = _make_graph(
        ip_requirements={"isp0": {"required_features": ["AV2"]}},
        pipeline_nodes=_PIPELINE_NODES,
        ip_catalog=_IP_CATALOG,
    )
    result = resolve(graph)
    assert any("AV2" in u for u in result.unresolved_requirements)


# ---------------------------------------------------------------------------
# resolve() — 미지원 키 (D-02 strict)
# ---------------------------------------------------------------------------

def test_resolve_mfc_required_codec_unresolved():
    """MFC required_codec — IpCapabilities에 대응 필드 없음 → unresolved (D-02)."""
    graph = _make_graph(
        ip_requirements={"mfc": {"required_codec": "H.265"}},
        pipeline_nodes=_PIPELINE_NODES,
        ip_catalog=_IP_CATALOG,
    )
    result = resolve(graph)
    assert any("required_codec" in u for u in result.unresolved_requirements)
    assert any("required_codec" in w for w in result.warnings)


def test_resolve_unknown_key_level_warning():
    """required_allocations — 미지원 키 → unresolved + warnings."""
    graph = _make_graph(
        ip_requirements={"isp0": {"required_allocations": {"ISP.TNR": "2MB"}}},
        pipeline_nodes=_PIPELINE_NODES,
        ip_catalog=_IP_CATALOG,
    )
    result = resolve(graph)
    assert any("required_allocations" in u for u in result.unresolved_requirements)
    assert any("required_allocations" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# resolve() — 노드 미존재 / ip_catalog 미존재
# ---------------------------------------------------------------------------

def test_resolve_node_not_in_pipeline():
    """ip_requirements에 있지만 pipeline에 없는 노드 → unresolved."""
    graph = _make_graph(
        ip_requirements={"ghost_node": {"required_throughput_mpps": 100}},
        pipeline_nodes=_PIPELINE_NODES,
        ip_catalog=_IP_CATALOG,
    )
    result = resolve(graph)
    assert "ghost_node" in result.unresolved_requirements
    assert any("ghost_node" in w for w in result.warnings)


def test_resolve_ip_ref_not_in_catalog():
    """pipeline 노드 ip_ref가 ip_catalog에 없을 때 → unresolved."""
    graph = _make_graph(
        ip_requirements={"missing_ip": {"required_throughput_mpps": 100}},
        pipeline_nodes=[{"id": "missing_ip", "ip_ref": "ip-unknown"}],
        ip_catalog=_IP_CATALOG,
    )
    result = resolve(graph)
    assert "missing_ip" in result.unresolved_requirements


# ---------------------------------------------------------------------------
# resolve() — SW resolution
# ---------------------------------------------------------------------------

_SW_RECORD_V123 = SwProfileRecord(
    id="sw-vendor-v1.2.3",
    schema_version="2.2",
    metadata_={"version": "1.2.3", "baseline_family": "vendor"},
    components={},
    feature_flags={"LLC_dynamic_allocation": "enabled", "TNR_early_abort": "enabled"},
    yaml_sha256="abc",
)

def test_resolve_sw_version_compatible():
    """profile version 1.2.3 >= min_version v1.2.0 → compatible=True."""
    graph = _make_graph(
        sw_requirements={"profile_constraints": {"min_version": "v1.2.0"}},
        sw_profiles={"sw-vendor-v1.2.3": _SW_RECORD_V123},
    )
    result = resolve(graph)
    assert len(result.sw_resolutions) == 1
    sw_res = result.sw_resolutions[0]
    assert sw_res.compatible is True
    assert sw_res.profile_id == "sw-vendor-v1.2.3"


def test_resolve_sw_version_incompatible():
    """profile version 1.2.3 < min_version v1.3.0 → compatible=False."""
    graph = _make_graph(
        sw_requirements={"profile_constraints": {"min_version": "v1.3.0"}},
        sw_profiles={"sw-vendor-v1.2.3": _SW_RECORD_V123},
    )
    result = resolve(graph)
    sw_res = result.sw_resolutions[0]
    assert sw_res.compatible is False
    assert any("min_version" in r for r in sw_res.reasons)


def test_resolve_sw_feature_flag_match():
    """required_features flag 모두 일치 → compatible=True."""
    graph = _make_graph(
        sw_requirements={
            "profile_constraints": {"min_version": "v1.2.0"},
            "required_features": [
                {"LLC_dynamic_allocation": "enabled"},
                {"TNR_early_abort": "enabled"},
            ],
        },
        sw_profiles={"sw-vendor-v1.2.3": _SW_RECORD_V123},
    )
    result = resolve(graph)
    assert result.sw_resolutions[0].compatible is True


def test_resolve_sw_feature_flag_mismatch():
    """required_features flag 불일치 → compatible=False."""
    graph = _make_graph(
        sw_requirements={
            "required_features": [{"LLC_dynamic_allocation": "disabled"}],
        },
        sw_profiles={"sw-vendor-v1.2.3": _SW_RECORD_V123},
    )
    result = resolve(graph)
    sw_res = result.sw_resolutions[0]
    assert sw_res.compatible is False
    assert any("LLC_dynamic_allocation" in r for r in sw_res.reasons)


def test_resolve_sw_required_hal_becomes_warning():
    """required_hal → warnings에 기록, unresolved_requirements에 추가 안 함."""
    graph = _make_graph(
        sw_requirements={"required_hal": {"camera": {"min_version": "4.5"}}},
        sw_profiles={},
    )
    result = resolve(graph)
    assert any("required_hal" in w for w in result.warnings)
    assert not any("required_hal" in u for u in result.unresolved_requirements)


def test_resolve_no_sw_profiles():
    """sw_profiles 없을 때 sw_resolutions=[]."""
    graph = _make_graph(sw_requirements={"profile_constraints": {"min_version": "v1.0.0"}})
    result = resolve(graph)
    assert result.sw_resolutions == []


# ---------------------------------------------------------------------------
# _version_gte 유닛 테스트
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("version,min_ver,expected", [
    ("1.2.3", "v1.2.0", True),
    ("1.3.0", "v1.2.3", True),
    ("1.2.0", "v1.2.0", True),
    ("1.1.9", "v1.2.0", False),
    ("2.0.0", "v1.9.9", True),
    ("1.2.3", "1.2.3",  True),
    ("1.2",   "1.2.0",  True),
])
def test_version_gte(version, min_ver, expected):
    assert _version_gte(version, min_ver) == expected
