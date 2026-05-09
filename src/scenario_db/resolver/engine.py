"""Resolver 엔진 — variant.ip_requirements를 ip_catalog.capabilities에 매핑 (RES-01, RES-02, RES-03).

설계 결정:
- D-01: All-matching modes — requirements를 만족하는 모든 모드를 리스트로 반환.
- D-02: Strict unresolved — 대응 필드 없거나 값 불일치 시 unresolved_requirements에 기록.
- D-03: matched_modes 비어있으면 unresolved_requirements에 node_id 추가.

DB 쿼리 없음 — 입력은 CanonicalScenarioGraph DTO (RES-03 비영속).
"""
from __future__ import annotations

from pydantic import ValidationError

from scenario_db.db.repositories.scenario_graph import CanonicalScenarioGraph
from scenario_db.models.capability.hw import IpCapabilities
from scenario_db.resolver.models import IpResolution, ResolverResult, SwResolution

# IP requirements에서 지원하는 체크 키 (나머지는 unresolved로 처리 — D-02 strict)
_KNOWN_IP_REQ_KEYS = frozenset({
    "required_throughput_mpps",
    "required_bitdepth",
    "required_features",
})


def resolve(graph: CanonicalScenarioGraph) -> ResolverResult:
    """variant.ip_requirements를 ip_catalog.capabilities에 매핑 (RES-01, RES-02, RES-03).

    DB 쿼리 없음 — 입력은 CanonicalScenarioGraph DTO.
    D-01: all-matching modes, D-02: strict unresolved, D-03: empty matched → unresolved.
    """
    ip_resolutions: list[IpResolution] = []
    sw_resolutions: list[SwResolution] = []
    unresolved: list[str] = []
    warnings: list[str] = []

    # pipeline node_id → ip_ref 맵 구성
    node_map: dict[str, str] = {}
    for node in (graph.pipeline or {}).get("nodes", []):
        node_id = node.get("id")
        ip_ref = node.get("ip_ref")
        if node_id and ip_ref:
            node_map[node_id] = ip_ref

    # -----------------------------------------------------------------------
    # IP Requirements 처리
    # -----------------------------------------------------------------------
    ip_req = graph.variant.ip_requirements or {}
    for node_id, req_dict in ip_req.items():
        if not isinstance(req_dict, dict):
            warnings.append(
                f"ip_requirements[{node_id!r}]: expected dict, got {type(req_dict).__name__}"
            )
            unresolved.append(node_id)
            continue

        # pipeline 노드 존재 여부 확인
        ip_ref = node_map.get(node_id)
        if not ip_ref:
            warnings.append(f"ip_requirements[{node_id!r}]: no pipeline node with this id")
            unresolved.append(node_id)
            continue

        # ip_catalog 존재 여부 확인
        ip_record = graph.ip_catalog.get(ip_ref)
        if not ip_record:
            warnings.append(
                f"ip_requirements[{node_id!r}]: ip_ref {ip_ref!r} not in ip_catalog"
            )
            unresolved.append(node_id)
            continue

        # IpCapabilities 파싱 (JSONB dict → Pydantic)
        try:
            caps = IpCapabilities.model_validate(ip_record.capabilities or {})
        except ValidationError as exc:
            warnings.append(
                f"ip_requirements[{node_id!r}]: capabilities parse error — {exc}"
            )
            unresolved.append(node_id)
            continue

        # 미지원 키 → unresolved + warning (D-02 strict)
        for key in req_dict:
            if key not in _KNOWN_IP_REQ_KEYS:
                warnings.append(
                    f"ip_requirements[{node_id!r}]: {key!r} has no matching capability field"
                    " — unresolved"
                )
                unresolved.append(f"{node_id}:{key}")

        # capability-level feature 체크 (supported_features)
        sf = caps.supported_features
        cap_reasons: list[str] = []

        req_bitdepth = req_dict.get("required_bitdepth")
        if req_bitdepth is not None and sf:
            if req_bitdepth not in sf.bitdepth:
                cap_reasons.append(
                    f"required_bitdepth={req_bitdepth} not in supported {sf.bitdepth}"
                )

        req_features: list[str] = req_dict.get("required_features", [])
        hdr_formats = sf.hdr_formats if sf else []
        for feat in req_features:
            if feat not in hdr_formats:
                cap_reasons.append(
                    f"required_feature={feat!r} not in supported hdr_formats {hdr_formats}"
                )
                unresolved.append(f"{node_id}:required_features:{feat}")

        # mode-level 체크 (throughput_mpps) — D-01 all-matching
        req_throughput = req_dict.get("required_throughput_mpps")
        matched_modes: list[str] = []
        unmatched_reasons: list[str] = list(cap_reasons)  # capability-level 실패도 포함

        for mode in caps.operating_modes:
            if req_throughput is not None and mode.throughput_mpps is not None:
                if mode.throughput_mpps < req_throughput:
                    unmatched_reasons.append(
                        f"mode={mode.id!r}: throughput {mode.throughput_mpps}"
                        f" < required {req_throughput}"
                    )
                    continue
            # capability-level check 통과한 경우에만 matched_modes에 추가
            if not cap_reasons:
                matched_modes.append(mode.id)

        # D-03: matched_modes 비어있으면 unresolved
        if not matched_modes:
            unresolved.append(node_id)

        ip_resolutions.append(IpResolution(
            node_id=node_id,
            catalog_id=ip_ref,
            matched_modes=matched_modes,
            unmatched_reasons=unmatched_reasons,
        ))

    # -----------------------------------------------------------------------
    # SW Requirements 처리
    # -----------------------------------------------------------------------
    sw_req = graph.variant.sw_requirements or {}
    pc = sw_req.get("profile_constraints") or {}
    min_version_str = pc.get("min_version")
    required_features: list[dict] = sw_req.get("required_features", [])

    for profile_id, sw_record in graph.sw_profiles.items():
        profile_version = (sw_record.metadata_ or {}).get("version")
        compatible = True
        reasons: list[str] = []

        # version >= min_version 체크
        if min_version_str and profile_version:
            if not _version_gte(profile_version, min_version_str):
                compatible = False
                reasons.append(
                    f"version {profile_version!r} < required min_version {min_version_str!r}"
                )
        elif min_version_str and not profile_version:
            compatible = False
            reasons.append("profile has no version field")

        # feature_flags 체크
        profile_flags = (
            sw_record.feature_flags if isinstance(sw_record.feature_flags, dict) else {}
        )
        for flag_entry in required_features:
            if not isinstance(flag_entry, dict):
                continue
            for flag_name, expected_val in flag_entry.items():
                actual_val = profile_flags.get(flag_name)
                if actual_val != expected_val:
                    compatible = False
                    reasons.append(
                        f"feature_flag {flag_name!r}: expected {expected_val!r},"
                        f" got {actual_val!r}"
                    )

        sw_resolutions.append(SwResolution(
            profile_id=profile_id,
            version=profile_version,
            compatible=compatible,
            reasons=reasons,
        ))

    # 미지원 sw_req 키 → warnings (unresolved 아님 — D-02 적용 범위 밖)
    _KNOWN_SW_REQ_KEYS = frozenset({"profile_constraints", "required_features"})
    for key in sw_req:
        if key not in _KNOWN_SW_REQ_KEYS:
            warnings.append(
                f"sw_requirements[{key!r}]: not evaluated in Phase 2 (deferred)"
            )

    return ResolverResult(
        ip_resolutions=ip_resolutions,
        sw_resolutions=sw_resolutions,
        unresolved_requirements=list(dict.fromkeys(unresolved)),  # 순서 유지 + 중복 제거
        warnings=warnings,
    )


def _version_gte(version: str, min_version: str) -> bool:
    """'v' 접두사를 무시하고 major.minor.patch 비교.

    부족한 자릿수는 0으로 패딩하여 비교한다.
    예: "1.2" vs "1.2.0" → (1, 2, 0) vs (1, 2, 0) → True
    """
    def _parse(v: str) -> list[int]:
        stripped = v.lstrip("v")
        parts = stripped.split(".")
        result = []
        for p in parts:
            try:
                result.append(int(p))
            except ValueError:
                result.append(0)
        return result

    a = _parse(version)
    b = _parse(min_version)
    # 길이를 맞춰 zero-padding
    max_len = max(len(a), len(b))
    a += [0] * (max_len - len(a))
    b += [0] * (max_len - len(b))
    return tuple(a) >= tuple(b)
