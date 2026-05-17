"""Add params_hash column to evidence table

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-17

D-02: params_hash TEXT — SHA256(scenario_id+variant_id+fps+dvfs_overrides+asv_group)
      캐싱 캐시 히트 여부 판별에 사용. nullable=True (기존 evidence 행 보호).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "evidence",
        sa.Column("params_hash", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("evidence", "params_hash")
