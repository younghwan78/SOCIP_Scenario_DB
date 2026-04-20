from __future__ import annotations

import time as _time

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text

from scenario_db.api.cache import RuleCache

# /health 는 prefix="/api/v1" 없이 마운트
health_router = APIRouter(tags=["admin"])
# /api/v1/admin/* 용
router = APIRouter(tags=["admin"])


# ---------------------------------------------------------------------------
# /health  (prefix 없음)
# ---------------------------------------------------------------------------

@health_router.get("/health", summary="서버 헬스체크 + 캐시 상태")
def health(request: Request):
    cache: RuleCache = request.app.state.rule_cache
    uptime = _time.time() - request.app.state.start_time

    db_ok = False
    try:
        with request.app.state.session_factory() as s:
            s.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    return {
        "status": "ok" if db_ok else "degraded",
        "version": "0.1.0",
        "uptime_s": round(uptime, 1),
        "db": "connected" if db_ok else "unreachable",
        "rule_cache": {
            "loaded": cache.loaded,
            "issues": len(cache.issues),
            "gate_rules": len(cache.gate_rules),
            "error": cache.load_error,
        },
    }


# ---------------------------------------------------------------------------
# /api/v1/admin/cache/refresh  (P3)
# ---------------------------------------------------------------------------

@router.post("/admin/cache/refresh", summary="Issue/GateRule 캐시 강제 재로드")
def refresh_cache(request: Request):
    cache: RuleCache = request.app.state.rule_cache
    session = request.app.state.session_factory()
    try:
        cache.invalidate_issues(session)
        cache.invalidate_gate_rules(session)
    finally:
        session.close()
    return {
        "refreshed": True,
        "issues": len(cache.issues),
        "gate_rules": len(cache.gate_rules),
    }


# ---------------------------------------------------------------------------
# P3 — Week 4/5 예약 501 Stubs
# ---------------------------------------------------------------------------

_NOT_IMPL = HTTPException(
    status_code=501,
    detail="Not implemented — scheduled for Week 4/5",
)


@router.post("/variants/generate-yaml", summary="[Week 4] Variant → YAML export")
def generate_yaml_stub():
    raise _NOT_IMPL


@router.post(
    "/scenarios/{scenario_id}/variants",
    summary="[Week 4] Variant 생성",
)
def create_variant_stub(scenario_id: str):
    raise _NOT_IMPL


@router.post(
    "/scenarios/{scenario_id}/variants/{variant_id}/review",
    summary="[Week 5] Review gate 제출",
)
def submit_review_stub(scenario_id: str, variant_id: str):
    raise _NOT_IMPL


@router.post("/admin/etl/trigger", summary="[Week 4] ETL 수동 트리거")
def etl_trigger_stub():
    raise _NOT_IMPL
