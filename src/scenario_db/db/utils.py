"""DB 공유 유틸리티 함수 모음."""
from __future__ import annotations


def issue_affects_scenario(affects: list[dict] | None, scenario_id: str) -> bool:
    """Issue.affects JSONB에 scenario_id 또는 wildcard '*'가 포함되는지 확인.

    affects 구조: list[{scenario_ref: str, match_rule: dict}]

    Args:
        affects: Issue.affects JSONB 컬럼 값 (None 또는 dict 리스트).
        scenario_id: 대상 시나리오 ID.

    Returns:
        True이면 해당 issue가 scenario_id 또는 전체('*')에 영향을 미침.
    """
    if not affects:
        return False
    return any(
        entry.get("scenario_ref") in ("*", scenario_id)
        for entry in affects
    )
