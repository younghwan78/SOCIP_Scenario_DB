"""ValidationReport Pydantic 모델 단위 테스트 — DB 불필요."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from scenario_db.etl.validate_loaded import ValidationReport


def test_validation_report_empty_is_valid():
    """기본 생성 시 is_valid=True, errors/warnings 모두 빈 리스트."""
    report = ValidationReport()
    assert report.is_valid is True
    assert report.errors == []
    assert report.warnings == []


def test_validation_report_with_errors_is_invalid():
    """errors가 있으면 is_valid=False."""
    report = ValidationReport(errors=["some error"])
    assert report.is_valid is False


def test_validation_report_extra_fields_forbidden():
    """extra='forbid' 설정 — 예상치 못한 필드는 ValidationError 발생."""
    with pytest.raises(ValidationError):
        ValidationReport(errors=[], unexpected="x")


def test_validation_report_warnings_do_not_affect_validity():
    """warnings만 있으면 is_valid=True (경고는 유효성에 영향 없음)."""
    report = ValidationReport(warnings=["some warning"])
    assert report.is_valid is True
    assert report.errors == []
