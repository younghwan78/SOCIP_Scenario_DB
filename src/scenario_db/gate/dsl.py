from __future__ import annotations

from typing import Any

from scenario_db.db.repositories.scenario_graph import VariantRecord


def evaluate_applies_to(match: dict[str, object] | None, variant: VariantRecord) -> bool:
    """applies_to.match DSL을 variant에 평가한다 (D-05).

    paths:
        variant.severity              → variant.severity
        variant.design_conditions.*   → variant.design_conditions[key]

    operators: $in, $eq, $not_empty, $exists

    AND 시맨틱 — 모든 키가 True여야 최종 True.
    알 수 없는 path → True (pass-through, 미래 확장 대비).
    """
    if not match:
        return True  # 빈 match 또는 None → unconditional (D-06)

    for path, op_dict in match.items():
        value = _resolve_path(path, variant)
        if not _eval_op(op_dict, value):
            return False
    return True


def _resolve_path(path: str, variant: VariantRecord) -> Any:
    """dot-separated path를 VariantRecord에서 값으로 해석."""
    parts = path.split(".", 1)
    if parts[0] != "variant" or len(parts) < 2:
        return _UNKNOWN_PATH  # 알 수 없는 namespace → pass-through sentinel

    sub = parts[1]

    if sub == "severity":
        return variant.severity

    if sub.startswith("design_conditions."):
        key = sub[len("design_conditions."):]
        dc = variant.design_conditions or {}
        return dc.get(key)

    # 지원하지 않는 variant 하위 경로 → None
    return None


# Sentinel: 알 수 없는 path prefix (variant 외의 namespace)에서 반환
# _eval_op에서 이 값을 받으면 True (pass-through) 반환
class _UnknownPath:
    pass


_UNKNOWN_PATH = _UnknownPath()


def _eval_op(op_dict: Any, value: Any) -> bool:
    """단일 오퍼레이터 딕셔너리를 평가."""
    if not isinstance(op_dict, dict):
        return True  # 형식 오류 → pass-through

    # 알 수 없는 path prefix sentinel → pass-through (미래 확장 대비, D-05)
    if isinstance(value, _UnknownPath):
        return True

    if "$in" in op_dict:
        return value in (op_dict["$in"] or [])

    if "$eq" in op_dict:
        return value == op_dict["$eq"]

    if "$not_empty" in op_dict:
        expected_not_empty = bool(op_dict["$not_empty"])
        is_not_empty = value is not None and value != "" and value != [] and value != {}
        return is_not_empty == expected_not_empty

    if "$exists" in op_dict:
        exists = value is not None
        return exists == bool(op_dict["$exists"])

    # 알 수 없는 오퍼레이터 → pass-through (미래 확장 대비)
    return True
