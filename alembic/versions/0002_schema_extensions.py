"""schema extensions for sim/ package

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-10

SCH-01: ip_catalog.sim_params (JSONB nullable)
SCH-02: scenario_variants.sim_port_config, sim_config (JSONB nullable)
SCH-03: scenarios.sensor (JSONB nullable)
SCH-04: evidence.dma_breakdown, timing_breakdown (JSONB nullable)
SCH-05: 이 파일이 alembic upgrade head 대상
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SCH-01: IpCatalog — sim_params
    op.add_column(
        "ip_catalog",
        sa.Column("sim_params", JSONB, nullable=True),
    )

    # SCH-03: Scenario — sensor
    op.add_column(
        "scenarios",
        sa.Column("sensor", JSONB, nullable=True),
    )

    # SCH-02: ScenarioVariant — sim_port_config, sim_config
    op.add_column(
        "scenario_variants",
        sa.Column("sim_port_config", JSONB, nullable=True),
    )
    op.add_column(
        "scenario_variants",
        sa.Column("sim_config", JSONB, nullable=True),
    )

    # SCH-04: Evidence — dma_breakdown, timing_breakdown
    op.add_column(
        "evidence",
        sa.Column("dma_breakdown", JSONB, nullable=True),
    )
    op.add_column(
        "evidence",
        sa.Column("timing_breakdown", JSONB, nullable=True),
    )


def downgrade() -> None:
    # upgrade()의 역순으로 삭제
    op.drop_column("evidence", "timing_breakdown")
    op.drop_column("evidence", "dma_breakdown")
    op.drop_column("scenario_variants", "sim_config")
    op.drop_column("scenario_variants", "sim_port_config")
    op.drop_column("scenarios", "sensor")
    op.drop_column("ip_catalog", "sim_params")
