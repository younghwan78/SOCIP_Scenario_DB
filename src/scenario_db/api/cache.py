from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from scenario_db.api.schemas.decision import GateRuleResponse, IssueResponse
from scenario_db.db.models.decision import GateRule, Issue

logger = logging.getLogger(__name__)


@dataclass
class RuleCache:
    issues: list[IssueResponse] = field(default_factory=list)
    gate_rules: list[GateRuleResponse] = field(default_factory=list)
    loaded: bool = False
    load_error: str | None = None

    @classmethod
    def load(cls, session: Session) -> "RuleCache":
        """Load all Issue + GateRule rows and convert to Pydantic models (avoids DetachedInstanceError)."""
        issues = [IssueResponse.model_validate(r) for r in session.query(Issue).all()]
        gate_rules = [GateRuleResponse.model_validate(r) for r in session.query(GateRule).all()]
        return cls(issues=issues, gate_rules=gate_rules, loaded=True)

    @classmethod
    def load_with_retry(cls, session_factory, max_retries: int = 3) -> "RuleCache":
        """3회 재시도 (exponential backoff: 1s, 2s, 4s). 실패해도 빈 캐시로 서버 시작."""
        for attempt in range(max_retries):
            try:
                session = session_factory()
                try:
                    cache = cls.load(session)
                    logger.info(
                        "RuleCache loaded: %d issues, %d gate_rules",
                        len(cache.issues), len(cache.gate_rules),
                    )
                    return cache
                finally:
                    session.close()
            except Exception as exc:
                wait = 2 ** attempt
                logger.warning(
                    "RuleCache load attempt %d/%d failed: %s — retry in %ds",
                    attempt + 1, max_retries, exc, wait,
                )
                if attempt < max_retries - 1:
                    time.sleep(wait)
                else:
                    logger.error(
                        "RuleCache load failed after %d attempts — starting with empty cache",
                        max_retries,
                    )
                    return cls(loaded=False, load_error=str(exc))
        return cls(loaded=False)  # unreachable, but satisfies type checker

    def invalidate_issues(self, session: Session) -> None:
        self.issues = [IssueResponse.model_validate(r) for r in session.query(Issue).all()]
        self.loaded = True

    def invalidate_gate_rules(self, session: Session) -> None:
        self.gate_rules = [GateRuleResponse.model_validate(r) for r in session.query(GateRule).all()]
        self.loaded = True


# ---------------------------------------------------------------------------
# Variant matching helpers (Week 4: @lru_cache 추가 예정)
# ---------------------------------------------------------------------------

def variant_hash(
    design_conditions: dict | None,
    ip_requirements: dict | None,
    sw_requirements: dict | None,
) -> str:
    """결정론적 SHA256 해시 — Week 4 lru_cache 키로 사용."""
    payload = {
        "dc": design_conditions,
        "ip": ip_requirements,
        "sw": sw_requirements,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()


# TODO Week 4: @lru_cache(maxsize=512) 추가
def match_issues_for_variant(
    ctx: "MatcherContext",  # type: ignore[name-defined]
    issues: list[IssueResponse],
) -> list[IssueResponse]:
    """Issue.affects 룰과 variant context를 매칭. 현재 캐싱 없음."""
    from scenario_db.matcher.runner import evaluate
    return [iss for iss in issues if iss.affects and evaluate(iss.affects, ctx)]
