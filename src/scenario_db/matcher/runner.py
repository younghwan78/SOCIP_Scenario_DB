from __future__ import annotations

import re
from typing import Any

from scenario_db.matcher.context import MatcherContext


def evaluate(rule: dict, ctx: MatcherContext) -> bool:
    """
    Evaluate an Issue.affects JSONB rule against a MatcherContext.
    Returns True when the rule matches (i.e. the issue affects this variant).

    Logical combinators:
        {"all": [...]}   — AND (every sub-rule must match)
        {"any": [...]}   — OR  (at least one sub-rule must match)
        {"none": [...]}  — NOT (no sub-rule may match)

    Leaf rule shape:
        {"field": "axis.resolution", "op": "eq", "value": "UHD"}
    """
    if "all" in rule:
        return all(evaluate(sub, ctx) for sub in rule["all"])
    if "any" in rule:
        return any(evaluate(sub, ctx) for sub in rule["any"])
    if "none" in rule:
        return not any(evaluate(sub, ctx) for sub in rule["none"])
    return _eval_leaf(rule, ctx)


def _eval_leaf(rule: dict, ctx: MatcherContext) -> bool:
    field: str = rule["field"]
    op: str = rule["op"]
    value: Any = rule.get("value")
    actual: Any = ctx.get(field)

    match op:
        case "eq":
            return actual == value
        case "ne":
            return actual != value
        case "in":
            return actual in value
        case "not_in":
            return actual not in value
        case "gte":
            return actual is not None and actual >= value
        case "lte":
            return actual is not None and actual <= value
        case "gt":
            return actual is not None and actual > value
        case "lt":
            return actual is not None and actual < value
        case "matches":
            return actual is not None and bool(re.search(value, str(actual)))
        case "exists":
            # value=true → field must exist (not None); value=false → must be absent
            return (actual is not None) is bool(value)
        case "between":
            low, high = value[0], value[1]
            return actual is not None and low <= actual <= high
        case _:
            raise ValueError(
                f"Unknown operator: {op!r}. "
                f"Expected one of: eq, ne, in, not_in, gte, lte, gt, lt, matches, exists, between"
            )
