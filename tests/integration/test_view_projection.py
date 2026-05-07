"""get_view_projection() 통합 테스트 — demo fixtures 기반 (DB-03)."""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from scenario_db.db.repositories.view_projection import get_view_projection

pytestmark = pytest.mark.integration

SCENARIO_ID = "uc-camera-recording"
VARIANT_ID = "UHD60-HDR10-H265"


def test_view_projection_demo_scenario(engine):
    """uc-camera-recording + UHD60-HDR10-H265 Level 0 lane data 조회."""
    with Session(engine) as session:
        result = get_view_projection(session, SCENARIO_ID, VARIANT_ID)

    assert result is not None
    assert result["scenario_id"] == SCENARIO_ID
    assert result["variant_id"] == VARIANT_ID
    assert "pipeline" in result
    assert "lanes" in result
    assert "ip_catalog" in result
    assert isinstance(result["lanes"], list)
    assert isinstance(result["ip_catalog"], list)


def test_view_projection_not_found(engine):
    """존재하지 않는 scenario_id → None 반환."""
    with Session(engine) as session:
        result = get_view_projection(session, "no-such-scenario", "no-variant")

    assert result is None


def test_view_projection_not_found_variant(engine):
    """존재하는 scenario + 존재하지 않는 variant_id → None 반환."""
    with Session(engine) as session:
        result = get_view_projection(session, SCENARIO_ID, "no-such-variant")

    assert result is None


def test_view_projection_has_project_name(engine):
    """project_name 필드가 존재한다 (None 또는 str)."""
    with Session(engine) as session:
        result = get_view_projection(session, SCENARIO_ID, VARIANT_ID)

    assert result is not None
    assert "project_name" in result
