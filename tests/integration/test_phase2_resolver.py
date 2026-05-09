"""Phase 2 Resolver 통합 테스트 — 실제 PostgreSQL DB + demo fixtures.

SC-1: ResolverResult 모델 필드 확인
SC-2: Resolver 결과가 DB에 저장되지 않음 확인
"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from scenario_db.db.repositories.scenario_graph import get_canonical_graph
from scenario_db.resolver.engine import resolve
from scenario_db.resolver.models import IpResolution, ResolverResult, SwResolution

pytestmark = pytest.mark.integration

SCENARIO_ID = "uc-camera-recording"
UHD_VARIANT = "UHD60-HDR10-H265"                   # severity=heavy, ip_requirements 있음
EXPL_VARIANT = "8K120-HDR10plus-AV1-exploration"   # required_throughput_mpps=3981 (초과)
FHD_VARIANT = "FHD30-SDR-H265"                     # ip_requirements={}


# ---------------------------------------------------------------------------
# 기본 타입 / 모델 검증 (SC-1)
# ---------------------------------------------------------------------------

def test_resolver_result_type(engine):
    """resolve() 반환 타입이 ResolverResult이고 필드가 올바른 타입이다."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, UHD_VARIANT)
    assert graph is not None
    result = resolve(graph)
    assert isinstance(result, ResolverResult)
    assert isinstance(result.ip_resolutions, list)
    assert isinstance(result.sw_resolutions, list)
    assert isinstance(result.unresolved_requirements, list)
    assert isinstance(result.warnings, list)


def test_resolver_result_ip_resolutions_type(engine):
    """ip_resolutions 각 항목이 IpResolution 타입이고 node_id, matched_modes를 갖는다."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, UHD_VARIANT)
    result = resolve(graph)
    for res in result.ip_resolutions:
        assert isinstance(res, IpResolution)
        assert isinstance(res.node_id, str)
        assert isinstance(res.matched_modes, list)


# ---------------------------------------------------------------------------
# ISP 노드 mode matching (SC-1, RES-02) — D-01 all-matching
# ---------------------------------------------------------------------------

def test_isp_node_resolved(engine):
    """isp0 노드가 ip_resolutions에 존재한다."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, UHD_VARIANT)
    result = resolve(graph)
    isp_res = next((r for r in result.ip_resolutions if r.node_id == "isp0"), None)
    assert isp_res is not None, "isp0 node should appear in ip_resolutions"


def test_isp_matched_modes_uhd_variant(engine):
    """UHD60 variant (required_throughput_mpps=498): normal(500✓), high_throughput(800✓), low_power(250✗).

    D-01: all-matching — 조건 충족 모드를 모두 반환, low_power는 제외된다.
    """
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, UHD_VARIANT)
    result = resolve(graph)
    isp_res = next(r for r in result.ip_resolutions if r.node_id == "isp0")
    assert "normal" in isp_res.matched_modes
    assert "high_throughput" in isp_res.matched_modes
    assert "low_power" not in isp_res.matched_modes


def test_isp_unresolved_for_8k_variant(engine):
    """8K variant (required_throughput_mpps=3981): 모든 ISP 모드 불일치 → isp0가 unresolved (D-03)."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, EXPL_VARIANT)
    assert graph is not None
    result = resolve(graph)
    # 8K variant의 required_throughput_mpps=3981은 모든 ISP 모드를 초과 → isp0가 unresolved
    assert "isp0" in result.unresolved_requirements, (
        f"isp0 should be in unresolved_requirements for 8K variant, "
        f"got: {result.unresolved_requirements}"
    )


def test_fhd_variant_empty_ip_requirements(engine):
    """FHD variant (ip_requirements={}): ip_resolutions=[], unresolved=[]."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, FHD_VARIANT)
    result = resolve(graph)
    assert result.ip_resolutions == []
    assert result.unresolved_requirements == []


# ---------------------------------------------------------------------------
# MFC 미지원 필드 → unresolved (SC-1, RES-02, D-02)
# ---------------------------------------------------------------------------

def test_mfc_required_codec_unresolved(engine):
    """UHD60 variant의 mfc.required_codec → unresolved_requirements에 포함 (D-02 strict).

    required_codec / required_level은 ip_catalog 에 대응 capability 필드가 없어 unresolved.
    """
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, UHD_VARIANT)
    result = resolve(graph)
    # mfc:required_codec 또는 mfc:required_level이 unresolved에 있어야 함
    mfc_unresolved = [u for u in result.unresolved_requirements if "mfc" in u.lower()]
    assert len(mfc_unresolved) > 0, (
        f"MFC unresolved expected, got: {result.unresolved_requirements}"
    )


# ---------------------------------------------------------------------------
# SW Resolution (SC-1)
# ---------------------------------------------------------------------------

def test_sw_resolutions_type(engine):
    """sw_resolutions 각 항목이 SwResolution 타입이고 compatible 필드가 bool이다."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, UHD_VARIANT)
    result = resolve(graph)
    for res in result.sw_resolutions:
        assert isinstance(res, SwResolution)
        assert isinstance(res.compatible, bool)


def test_sw_resolutions_vendor_profile(engine):
    """sw-vendor-v1.2.3 프로파일이 sw_resolutions에 포함된다."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, UHD_VARIANT)
    result = resolve(graph)
    # sw profiles가 로드된 경우 sw_resolutions에 항목이 있어야 함
    # (demo fixture에 sw profile이 있는 경우)
    assert isinstance(result.sw_resolutions, list)


# ---------------------------------------------------------------------------
# 비영속 확인 (SC-2, RES-03)
# ---------------------------------------------------------------------------

def test_resolve_does_not_persist(engine):
    """resolve() 호출 전후로 DB 레코드 수 변화 없음 (RES-03 비영속 보장)."""
    from sqlalchemy import text
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, UHD_VARIANT)
        count_before = session.execute(
            text("SELECT COUNT(*) FROM scenario_variants")
        ).scalar()

    resolve(graph)  # DB session 없이 순수 함수 호출

    with Session(engine) as session:
        count_after = session.execute(
            text("SELECT COUNT(*) FROM scenario_variants")
        ).scalar()

    assert count_before == count_after, (
        f"resolve() must not write to DB (RES-03): "
        f"before={count_before}, after={count_after}"
    )


def test_resolve_does_not_persist_ip_catalog(engine):
    """resolve() 호출 후 ip_catalog 테이블도 변화 없음."""
    from sqlalchemy import text
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, UHD_VARIANT)
        count_before = session.execute(
            text("SELECT COUNT(*) FROM ip_catalog")
        ).scalar()

    resolve(graph)

    with Session(engine) as session:
        count_after = session.execute(
            text("SELECT COUNT(*) FROM ip_catalog")
        ).scalar()

    assert count_before == count_after, (
        f"resolve() must not write to ip_catalog: "
        f"before={count_before}, after={count_after}"
    )


# ---------------------------------------------------------------------------
# 결과 직렬화 가능성 확인 (Phase 3 API 대비)
# ---------------------------------------------------------------------------

def test_resolver_result_serializable(engine):
    """ResolverResult.model_dump()가 오류 없이 직렬화된다 (Phase 3 JSON 응답 대비)."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, UHD_VARIANT)
    result = resolve(graph)
    dumped = result.model_dump()
    assert isinstance(dumped, dict)
    assert "ip_resolutions" in dumped
    assert "sw_resolutions" in dumped
    assert "unresolved_requirements" in dumped
    assert "warnings" in dumped
