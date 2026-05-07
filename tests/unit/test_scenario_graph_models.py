from __future__ import annotations

import pytest
from pydantic import ValidationError

from scenario_db.db.repositories.scenario_graph import (
    CanonicalScenarioGraph,
    EvidenceRecord,
    IpRecord,
    IssueRecord,
    ProjectRecord,
    ReviewRecord,
    ScenarioRecord,
    SwProfileRecord,
    VariantRecord,
    WaiverRecord,
)


def _minimal_scenario_record() -> dict:
    return {
        "id": "uc-camera-recording",
        "schema_version": "2.2",
        "project_ref": "projectA",
        "metadata_": {"name": "test"},
        "pipeline": {"nodes": []},
        "yaml_sha256": "abc123",
    }


def _minimal_variant_record() -> dict:
    return {
        "scenario_id": "uc-camera-recording",
        "id": "UHD60-HDR10-H265",
    }


def test_scenario_record_minimal():
    rec = ScenarioRecord.model_validate(_minimal_scenario_record())
    assert rec.id == "uc-camera-recording"
    assert rec.size_profile is None


def test_scenario_record_extra_forbidden():
    data = {**_minimal_scenario_record(), "unexpected": "oops"}
    with pytest.raises(ValidationError):
        ScenarioRecord.model_validate(data)


def test_variant_record_all_optional_none():
    rec = VariantRecord.model_validate(_minimal_variant_record())
    assert rec.severity is None
    assert rec.ip_requirements is None


def test_canonical_graph_construct():
    graph = CanonicalScenarioGraph(
        scenario_id="uc-camera-recording",
        variant_id="UHD60-HDR10-H265",
        scenario=ScenarioRecord.model_validate(_minimal_scenario_record()),
        variant=VariantRecord.model_validate(_minimal_variant_record()),
        project=None,
        pipeline={"nodes": []},
        ip_catalog={},
        sw_profiles={},
        evidence=[],
        issues=[],
        waivers=[],
        reviews=[],
    )
    assert graph.scenario_id == "uc-camera-recording"
    assert graph.variant_id == "UHD60-HDR10-H265"
    assert graph.project is None
    assert graph.evidence == []


def test_canonical_graph_extra_forbidden():
    with pytest.raises(ValidationError):
        CanonicalScenarioGraph(
            scenario_id="x",
            variant_id="y",
            scenario=ScenarioRecord.model_validate(_minimal_scenario_record()),
            variant=VariantRecord.model_validate(_minimal_variant_record()),
            pipeline={},
            ip_catalog={},
            sw_profiles={},
            evidence=[],
            issues=[],
            waivers=[],
            reviews=[],
            unexpected_field="forbidden",
        )
