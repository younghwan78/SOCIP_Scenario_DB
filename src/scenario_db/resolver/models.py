from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class IpResolution(BaseModel):
    """단일 IP 노드의 resolve 결과."""
    model_config = ConfigDict(extra="forbid")

    node_id: str              # pipeline 노드 id (e.g. "isp0")
    catalog_id: str           # ip_catalog key (e.g. "ip-isp-v12")
    matched_modes: list[str]  # 조건 충족 mode.id 리스트 (D-01: all-matching)
    unmatched_reasons: list[str] = Field(default_factory=list)


class SwResolution(BaseModel):
    """단일 SW 프로파일의 resolve 결과."""
    model_config = ConfigDict(extra="forbid")

    profile_id: str
    version: str | None = None
    compatible: bool
    reasons: list[str] = Field(default_factory=list)  # 비호환 사유 또는 경고


class ResolverResult(BaseModel):
    """resolve() 반환 결과 — 비영속 (RES-03)."""
    model_config = ConfigDict(extra="forbid")

    ip_resolutions: list[IpResolution] = Field(default_factory=list)
    sw_resolutions: list[SwResolution] = Field(default_factory=list)
    unresolved_requirements: list[str] = Field(default_factory=list)  # node_id 또는 설명
    warnings: list[str] = Field(default_factory=list)
