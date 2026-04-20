from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict


class GateRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    schema_version: str
    metadata_: dict = {}
    trigger: dict = {}
    applies_to: dict | None = None
    condition: dict = {}
    action: dict = {}


class IssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    schema_version: str
    metadata_: dict = {}
    affects: dict | None = None
    affects_ip: list | None = None
    pmu_signature: dict | None = None
    resolution: dict | None = None


class WaiverResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    issue_ref: str | None = None
    scope: dict = {}
    justification: str | None = None
    status: str
    approver_claim: str
    claim_at: datetime.date | None = None
    approved_at: datetime.date | None = None
    expires_on: datetime.date | None = None


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    scenario_ref: str
    variant_ref: str
    evidence_refs: list | None = None
    gate_result: str | None = None
    auto_checks: dict | None = None
    decision: str | None = None
    waiver_ref: str | None = None
    rationale: str | None = None
    status: str
    approver_claim: str
