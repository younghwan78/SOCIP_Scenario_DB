"""ETL post-load semantic validation 통합 테스트 — demo fixtures 기반."""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from scenario_db.etl.validate_loaded import validate_loaded

pytestmark = pytest.mark.integration

SCENARIO_ID = "uc-camera-recording"
VARIANT_ID = "UHD60-HDR10-H265"
FHD_VARIANT_ID = "FHD30-SDR-H265"


def test_validate_loaded_no_errors(engine):
    """demo fixtures 로드 후 semantic validation 오류 없음."""
    with Session(engine) as session:
        report = validate_loaded(session)
    assert report.errors == [], f"Validation errors: {report.errors}"


def test_validate_loaded_is_valid(engine):
    """demo fixtures 로드 후 ValidationReport.is_valid == True."""
    with Session(engine) as session:
        report = validate_loaded(session)
    assert report.is_valid is True


def test_validate_loaded_fhd_variant_exists(engine):
    """FHD30-SDR-H265 variant가 DB에 로드되어 있어야 한다."""
    from scenario_db.db.models.definition import ScenarioVariant
    with Session(engine) as session:
        variant = (
            session.query(ScenarioVariant)
            .filter_by(scenario_id=SCENARIO_ID, id=FHD_VARIANT_ID)
            .one_or_none()
        )
    assert variant is not None, (
        f"Variant {FHD_VARIANT_ID} not found under scenario {SCENARIO_ID}"
    )


def test_load_triggers_validation(engine):
    """load_yaml_dir() 완료 후 DB에 데이터가 있고 validate_loaded가 오류 없이 실행된다.

    conftest.py의 engine fixture가 이미 load_yaml_dir를 실행했으므로,
    여기서는 validate_loaded가 정상 동작하는지 간접 검증한다.
    """
    with Session(engine) as session:
        report = validate_loaded(session)
    assert report.errors == [], (
        "load_yaml_dir() 이후 validate_loaded() 오류 없어야 함: "
        f"{report.errors}"
    )
