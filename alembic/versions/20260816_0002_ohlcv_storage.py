"""ohlcv storage

Revision ID: 20260816_0002
Revises: 20260816_0001
Create Date: 2026-08-16 00:10:00
"""
from alembic import op
import sqlalchemy as sa

revision = "20260816_0002"
down_revision = "20260816_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("ohlcv", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("instrument_key", sa.String(128), sa.ForeignKey("instruments.instrument_key"), nullable=False), sa.Column("timeframe", sa.String(8), nullable=False), sa.Column("start_at", sa.DateTime(timezone=True), nullable=False), sa.Column("open", sa.Numeric(18, 4), nullable=False), sa.Column("high", sa.Numeric(18, 4), nullable=False), sa.Column("low", sa.Numeric(18, 4), nullable=False), sa.Column("close", sa.Numeric(18, 4), nullable=False), sa.Column("volume", sa.Integer(), nullable=False), sa.Column("open_interest", sa.Integer()), sa.Column("source", sa.String(48), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.UniqueConstraint("instrument_key", "timeframe", "start_at", name="uq_ohlcv_instrument_timeframe_start"))
    op.create_index("ix_ohlcv_instrument_key", "ohlcv", ["instrument_key"])
    op.create_index("ix_ohlcv_start_at", "ohlcv", ["start_at"])


def downgrade() -> None:
    op.drop_table("ohlcv")
