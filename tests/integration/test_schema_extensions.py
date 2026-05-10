"""Phase 5 Schema Extensions — Alembic 0002 migration + ETL 통합 테스트.

테스트 범위:
  - migration 0002 적용 후 DB 스키마에 신규 컬럼 6개 존재 확인
  - 기존 fixture(sim_params 없음)가 ETL 통과 후 DB에 NULL로 저장됨 (backward compat)
  - 신규 fixture(sim_params 있음)가 ETL 통과 후 DB에 데이터 저장됨
  - downgrade → upgrade 사이클이 오류 없이 완료됨 (마지막에 실행, schema 재복원)

주의:
  - engine fixture는 session scope — 모든 테스트가 같은 DB를 공유
  - downgrade 테스트는 스키마를 변경하므로 반드시 session scope 기준 마지막에 실행
  - T-05-05: downgrade는 testcontainers 환경에서만 실행; 프로덕션 downgrade 금지
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from scenario_db.db.models.capability import IpCatalog as OrmIpCatalog
from scenario_db.db.models.definition import Scenario as OrmScenario
from scenario_db.db.models.definition import ScenarioVariant as OrmScenarioVariant
from scenario_db.db.models.evidence import Evidence as OrmEvidence
from scenario_db.etl.mappers.capability import upsert_ip
from scenario_db.etl.mappers.definition import upsert_usecase
from scenario_db.etl.mappers.evidence import upsert_simulation

pytestmark = pytest.mark.integration

FIXTURES_UNIT = Path(__file__).parent.parent / "unit" / "fixtures"
ALEMBIC_INI = Path(__file__).parent.parent.parent / "alembic.ini"


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# SCH-05: migration 0002 스키마 확인
# ---------------------------------------------------------------------------

def test_new_columns_exist_after_migration(engine):
    """alembic upgrade head 후 신규 컬럼 6개가 DB 스키마에 존재한다."""
    insp = inspect(engine)

    ip_cols = {c["name"] for c in insp.get_columns("ip_catalog")}
    assert "sim_params" in ip_cols, f"sim_params missing from ip_catalog: {ip_cols}"

    sc_cols = {c["name"] for c in insp.get_columns("scenarios")}
    assert "sensor" in sc_cols, f"sensor missing from scenarios: {sc_cols}"

    sv_cols = {c["name"] for c in insp.get_columns("scenario_variants")}
    assert "sim_port_config" in sv_cols, f"sim_port_config missing from scenario_variants: {sv_cols}"
    assert "sim_config" in sv_cols, f"sim_config missing from scenario_variants: {sv_cols}"

    ev_cols = {c["name"] for c in insp.get_columns("evidence")}
    assert "dma_breakdown" in ev_cols, f"dma_breakdown missing from evidence: {ev_cols}"
    assert "timing_breakdown" in ev_cols, f"timing_breakdown missing from evidence: {ev_cols}"


# ---------------------------------------------------------------------------
# SCH-01: sim_params ETL backward compat
# ---------------------------------------------------------------------------

def test_sim_params_etl_null_backward_compat(engine):
    """기존 ip-isp-v12.yaml (sim_params 없음) ETL 후 ip_catalog.sim_params = NULL."""
    raw = load_yaml(FIXTURES_UNIT / "hw" / "ip-isp-v12.yaml")
    # sim_params 필드가 없는지 확인
    raw_copy = dict(raw)
    raw_copy.pop("sim_params", None)  # 혹시 있으면 제거
    sha = "test-sha-no-sim-params-compat"
    # id 중복 방지를 위해 별도 id 사용
    raw_copy["id"] = "ip-isp-v12-no-sim-test"
    with Session(engine) as session:
        upsert_ip(raw_copy, sha, session)
        session.commit()
        row = session.get(OrmIpCatalog, "ip-isp-v12-no-sim-test")
    assert row is not None
    assert row.sim_params is None, f"Expected sim_params=None, got: {row.sim_params}"


def test_sim_params_etl_populated(engine):
    """ip-isp-v12-with-sim.yaml ETL 후 ip_catalog.sim_params에 데이터가 저장된다."""
    raw = load_yaml(FIXTURES_UNIT / "hw" / "ip-isp-v12-with-sim.yaml")
    # id 충돌 방지를 위해 id 변경 후 로드
    raw["id"] = "ip-isp-v12-with-sim-integ-test"
    sha = "test-sha-with-sim-params"
    with Session(engine) as session:
        upsert_ip(raw, sha, session)
        session.commit()
        row = session.get(OrmIpCatalog, "ip-isp-v12-with-sim-integ-test")
    assert row is not None
    assert row.sim_params is not None, "sim_params should be populated"
    assert row.sim_params["hw_name_in_sim"] == "ISP"
    assert len(row.sim_params["ports"]) == 4


# ---------------------------------------------------------------------------
# SCH-03: sensor ETL
# ---------------------------------------------------------------------------

def test_sensor_etl_null_backward_compat(engine):
    """기존 uc-camera-recording.yaml (sensor 없음) ETL 후 scenarios.sensor = NULL."""
    raw = load_yaml(FIXTURES_UNIT / "definition" / "uc-camera-recording.yaml")
    # sensor 필드가 없는지 확인
    raw.pop("sensor", None)
    sha = "test-sha-no-sensor-compat"
    with Session(engine) as session:
        upsert_usecase(raw, sha, session)
        session.commit()
        row = session.get(OrmScenario, raw["id"])
    assert row is not None
    assert row.sensor is None, f"Expected sensor=None, got: {row.sensor}"


# ---------------------------------------------------------------------------
# SCH-02: sim_port_config + sim_config ETL
# ---------------------------------------------------------------------------

def test_variant_sim_config_etl_null_backward_compat(engine):
    """기존 uc-camera-recording.yaml variants에 sim_port_config 없으면 NULL로 저장된다."""
    raw = load_yaml(FIXTURES_UNIT / "definition" / "uc-camera-recording.yaml")
    raw.pop("sensor", None)
    sha = "test-sha-no-sim-config-compat"
    with Session(engine) as session:
        upsert_usecase(raw, sha, session)
        session.commit()
        rows = (
            session.query(OrmScenarioVariant)
            .filter_by(scenario_id=raw["id"])
            .all()
        )
    assert len(rows) > 0, "Variant rows should exist"
    for vrow in rows:
        assert vrow.sim_port_config is None, (
            f"Expected sim_port_config=None for variant {vrow.id}, got: {vrow.sim_port_config}"
        )
        assert vrow.sim_config is None, (
            f"Expected sim_config=None for variant {vrow.id}, got: {vrow.sim_config}"
        )


# ---------------------------------------------------------------------------
# SCH-04: dma_breakdown + timing_breakdown ETL
# ---------------------------------------------------------------------------

def test_dma_breakdown_etl_empty_default(engine):
    """기존 sim-*.yaml (breakdown 없음) ETL 후 evidence 컬럼에 빈 리스트 또는 NULL."""
    fixture_path = FIXTURES_UNIT / "evidence" / "sim-camera-recording-UHD60-A0-sw123.yaml"
    if not fixture_path.exists():
        pytest.skip("기존 sim evidence fixture 없음")
    raw = load_yaml(fixture_path)
    # dma_breakdown / timing_breakdown 없는 기존 fixture임을 확인
    raw.pop("dma_breakdown", None)
    raw.pop("timing_breakdown", None)
    sha = "test-sha-no-breakdown-compat"
    # id 중복 방지
    raw["id"] = "sim-evidence-no-breakdown-test"
    with Session(engine) as session:
        upsert_simulation(raw, sha, session)
        session.commit()
        row = session.get(OrmEvidence, "sim-evidence-no-breakdown-test")
    assert row is not None
    # dma_breakdown은 빈 list 또는 NULL (backward compat)
    assert row.dma_breakdown in (None, []), f"Unexpected dma_breakdown: {row.dma_breakdown}"
    assert row.timing_breakdown in (None, []), f"Unexpected timing_breakdown: {row.timing_breakdown}"


def test_dma_breakdown_etl_populated(engine):
    """sim-FHD30-with-breakdown.yaml ETL 후 evidence.dma_breakdown에 데이터 저장된다."""
    fixture_path = FIXTURES_UNIT / "evidence" / "sim-FHD30-with-breakdown.yaml"
    if not fixture_path.exists():
        pytest.skip("sim-FHD30-with-breakdown.yaml fixture 없음")
    raw = load_yaml(fixture_path)
    # id 충돌 방지
    raw["id"] = "sim-FHD30-breakdown-integ-test"
    sha = "test-sha-with-breakdown"
    with Session(engine) as session:
        upsert_simulation(raw, sha, session)
        session.commit()
        row = session.get(OrmEvidence, "sim-FHD30-breakdown-integ-test")
    assert row is not None
    assert row.dma_breakdown is not None and len(row.dma_breakdown) >= 1, (
        f"dma_breakdown should have at least 1 entry, got: {row.dma_breakdown}"
    )
    assert row.dma_breakdown[0]["ip"] == "isp0"
    assert row.timing_breakdown is not None and len(row.timing_breakdown) >= 1, (
        f"timing_breakdown should have at least 1 entry, got: {row.timing_breakdown}"
    )
    assert row.timing_breakdown[0]["feasible"] is True


# ---------------------------------------------------------------------------
# SCH-05: downgrade → upgrade 사이클
# (CAUTION T-05-05: testcontainers 환경에서만 실행 — 프로덕션 downgrade 금지)
# 이 테스트는 공유 session scope DB 스키마를 변경하므로 반드시 마지막에 실행된다.
# upgrade head로 복원하므로 다른 테스트에 영향 없음.
# ---------------------------------------------------------------------------

def test_migration_downgrade_upgrade_cycle(engine, pg):
    """alembic downgrade 0001 → upgrade head 사이클이 오류 없이 완료된다.

    T-05-05: downgrade 실행은 testcontainers DB 환경에서만 유효.
    downgrade 후 upgrade로 복원하므로 다른 통합 테스트와 충돌 없음.
    """
    if not ALEMBIC_INI.exists():
        pytest.skip("alembic.ini not found")

    from alembic import command
    from alembic.config import Config

    url = pg.get_connection_url()
    if "postgresql+psycopg2" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", url)

    # downgrade to 0001 — 신규 컬럼 6개 삭제
    command.downgrade(cfg, "0001")

    # 신규 컬럼이 사라졌는지 확인 (캐시 무효화 위해 새 connection 사용)
    with engine.connect() as conn:
        insp = inspect(conn)
        ip_cols = {c["name"] for c in insp.get_columns("ip_catalog")}
    assert "sim_params" not in ip_cols, (
        f"sim_params should be dropped after downgrade to 0001, but found in: {ip_cols}"
    )

    # upgrade back to head — 신규 컬럼 6개 복원
    command.upgrade(cfg, "head")

    # 신규 컬럼이 돌아왔는지 확인
    with engine.connect() as conn:
        insp2 = inspect(conn)
        ip_cols2 = {c["name"] for c in insp2.get_columns("ip_catalog")}
    assert "sim_params" in ip_cols2, (
        f"sim_params should be restored after upgrade to head, but missing from: {ip_cols2}"
    )
