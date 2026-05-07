"""get_canonical_graph() 통합 테스트 — demo fixtures 기반 (DB-02)."""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from scenario_db.db.repositories.scenario_graph import get_canonical_graph

pytestmark = pytest.mark.integration

SCENARIO_ID = "uc-camera-recording"
VARIANT_ID = "UHD60-HDR10-H265"
FHD_VARIANT_ID = "FHD30-SDR-H265"


def test_canonical_graph_demo_scenario(engine):
    """uc-camera-recording + UHD60-HDR10-H265 canonical graph 로드."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, VARIANT_ID)

    assert graph is not None
    assert graph.scenario_id == SCENARIO_ID
    assert graph.variant_id == VARIANT_ID
    assert graph.project is not None
    assert graph.pipeline is not None
    assert isinstance(graph.ip_catalog, dict)
    assert isinstance(graph.evidence, list)
    assert isinstance(graph.issues, list)
    assert isinstance(graph.waivers, list)
    assert isinstance(graph.reviews, list)


def test_canonical_graph_fhd_variant(engine):
    """FHD30-SDR-H265 variant canonical graph 로드 (Plan 01에서 fixture 추가됨)."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, FHD_VARIANT_ID)

    assert graph is not None
    assert graph.scenario_id == SCENARIO_ID
    assert graph.variant_id == FHD_VARIANT_ID


def test_canonical_graph_not_found_scenario(engine):
    """존재하지 않는 scenario_id → None 반환."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, "no-such-scenario", "no-variant")

    assert graph is None


def test_canonical_graph_not_found_variant(engine):
    """존재하는 scenario + 존재하지 않는 variant_id → None 반환."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, "no-such-variant")

    assert graph is None


def test_canonical_graph_scenario_fields(engine):
    """반환된 graph의 scenario 필드가 ScenarioRecord 구조를 갖춘다."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, VARIANT_ID)

    assert graph is not None
    assert graph.scenario.id == SCENARIO_ID
    assert graph.scenario.project_ref is not None
    assert isinstance(graph.scenario.pipeline, dict)


def test_canonical_graph_no_sa_instance_state(engine):
    """CanonicalScenarioGraph에 _sa_instance_state 필드가 없다 (ORM 오염 없음)."""
    with Session(engine) as session:
        graph = get_canonical_graph(session, SCENARIO_ID, VARIANT_ID)

    assert graph is not None
    # model_dump()에 _sa_instance_state가 포함되면 from_attributes=True 미적용 증거
    dumped = graph.model_dump()
    assert "_sa_instance_state" not in dumped
    assert "_sa_instance_state" not in dumped.get("scenario", {})
