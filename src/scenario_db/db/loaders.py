"""ORM → run_simulation() 입력 Pydantic 변환 레이어 (D-07).

DB/ORM 의존: Scenario, ScenarioVariant, IpCatalogEntry ORM row
출력: run_simulation() 인수로 직접 전달 가능한 Pydantic 객체
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import TYPE_CHECKING

import yaml
from sqlalchemy.orm import Session

from scenario_db.config import DVFS_CONFIG_PATH
from scenario_db.db.models.capability import IpCatalog as IpCatalogEntry
from scenario_db.db.models.definition import Scenario, ScenarioVariant
from scenario_db.models.capability.hw import IpCatalog
from scenario_db.models.definition.usecase import (
    IPPortConfig,
    Pipeline,
    SensorSpec,
    SimGlobalConfig,
)
from scenario_db.sim.models import DVFSLevel, DVFSTable

if TYPE_CHECKING:
    from scenario_db.api.schemas.simulation import SimulateRequest

logger = logging.getLogger(__name__)


def _load_dvfs_tables() -> dict[str, DVFSTable]:
    """DVFS_CONFIG_PATH YAML → {domain: DVFSTable} 딕셔너리 로드.

    hw_config/dvfs-projectA.yaml 구조:
        dvfs_tables:
            CAM:
                - level: 0
                  speed_mhz: 600
                  voltages: {0: 820, 4: 780, 8: 750}
                ...
    """
    with open(DVFS_CONFIG_PATH, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    tables: dict[str, DVFSTable] = {}
    for domain, level_list in raw.get("dvfs_tables", {}).items():
        levels = [
            DVFSLevel(
                level=lv["level"],
                speed_mhz=lv["speed_mhz"],
                voltages={int(k): v for k, v in lv["voltages"].items()},
            )
            for lv in (level_list or [])
        ]
        tables[domain] = DVFSTable(domain=domain, levels=levels)
    return tables


def compute_params_hash(req: "SimulateRequest") -> str:
    """SimulateRequest → SHA256 hex digest (D-02).

    sort_keys=True로 dvfs_overrides 딕셔너리 순서 독립성 보장.
    반환값: 64자 lowercase hex string.
    """
    payload = json.dumps(
        {
            "scenario_id": req.scenario_id,
            "variant_id": req.variant_id,
            "fps": req.fps,
            "dvfs_overrides": req.dvfs_overrides,
            "asv_group": req.asv_group,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def apply_request_overrides(
    sim_config: SimGlobalConfig,
    req: "SimulateRequest",
) -> SimGlobalConfig:
    """request의 dvfs_overrides, asv_group을 DB sim_config에 오버라이드 (D-03).

    나머지 필드(sw_margin, bw_power_coeff, vbat, pmic_eff, h_blank_margin)는 DB 값 유지.
    원본 sim_config는 변경하지 않고 새 SimGlobalConfig 인스턴스 반환.
    """
    overridden = sim_config.model_dump()
    overridden["asv_group"] = req.asv_group
    if req.dvfs_overrides is not None:
        overridden["dvfs_overrides"] = req.dvfs_overrides
    return SimGlobalConfig.model_validate(overridden)


def load_runner_inputs_from_db(
    db: Session,
    scenario_id: str,
    variant_id: str,
) -> (
    tuple[
        Pipeline,
        dict[str, IpCatalog],
        dict[str, DVFSTable],
        dict[str, IPPortConfig],
        SimGlobalConfig,
        SensorSpec | None,
    ]
    | None
):
    """DB ORM row → run_simulation() 인수 변환 (D-07).

    Returns:
        (pipeline, ip_catalog, dvfs_tables, variant_port_config, sim_config, sensor_spec)
        또는 scenario/variant 없음 시 None
    """
    scenario = db.query(Scenario).filter_by(id=scenario_id).one_or_none()
    if scenario is None:
        logger.warning("scenario '%s' not found in DB", scenario_id)
        return None

    variant = (
        db.query(ScenarioVariant)
        .filter_by(scenario_id=scenario_id, id=variant_id)
        .one_or_none()
    )
    if variant is None:
        logger.warning(
            "variant '%s' not found for scenario '%s'", variant_id, scenario_id
        )
        return None

    # Pipeline 변환
    pipeline = Pipeline.model_validate(scenario.pipeline)

    # Sensor spec 변환
    sensor_spec: SensorSpec | None = None
    if scenario.sensor is not None:
        sensor_spec = SensorSpec.model_validate(scenario.sensor)

    # ip_catalog 조회 — pipeline 내 ip_ref 기준 배치 쿼리
    ip_refs = {node.ip_ref for node in pipeline.nodes}
    catalog_rows = (
        db.query(IpCatalogEntry)
        .filter(IpCatalogEntry.id.in_(ip_refs))
        .all()
    )
    ip_catalog: dict[str, IpCatalog] = {
        row.id: IpCatalog.model_validate(row, from_attributes=True)
        for row in catalog_rows
    }

    # DVFS 테이블 로드
    dvfs_tables = _load_dvfs_tables()

    # Variant port config 변환
    variant_port_config: dict[str, IPPortConfig] = {}
    if variant.sim_port_config:
        for node_id, cfg in variant.sim_port_config.items():
            variant_port_config[node_id] = IPPortConfig.model_validate(cfg)

    # SimGlobalConfig 변환
    sim_config = (
        SimGlobalConfig.model_validate(variant.sim_config)
        if variant.sim_config
        else SimGlobalConfig()
    )

    return pipeline, ip_catalog, dvfs_tables, variant_port_config, sim_config, sensor_spec
