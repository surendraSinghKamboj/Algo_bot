"""phase one foundation schema

Revision ID: 20260816_0001
Revises:
Create Date: 2026-08-16 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260816_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("instruments", sa.Column("instrument_key", sa.String(128), primary_key=True), sa.Column("exchange_token", sa.String(64)), sa.Column("segment", sa.String(32), nullable=False), sa.Column("exchange", sa.String(16), nullable=False), sa.Column("instrument_type", sa.String(16), nullable=False), sa.Column("trading_symbol", sa.String(160), nullable=False), sa.Column("name", sa.String(256)), sa.Column("underlying_key", sa.String(128)), sa.Column("expiry_at", sa.DateTime(timezone=True)), sa.Column("strike_price", sa.Numeric(18, 4)), sa.Column("lot_size", sa.Integer()), sa.Column("minimum_lot", sa.Integer()), sa.Column("tick_size", sa.Numeric(18, 4)), sa.Column("weekly", sa.Boolean()), sa.Column("trading_status", sa.String(24), nullable=False), sa.Column("source_payload", postgresql.JSONB(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    for column in ("segment", "instrument_type", "trading_symbol", "underlying_key", "expiry_at"):
        op.create_index(f"ix_instruments_{column}", "instruments", [column])
    op.create_table("oauth_states", sa.Column("state", sa.String(128), primary_key=True), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("consumed_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_index("ix_oauth_states_expires_at", "oauth_states", ["expires_at"])
    op.create_table("system_events", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("event_type", sa.String(64), nullable=False), sa.Column("severity", sa.String(16), nullable=False), sa.Column("message", sa.Text(), nullable=False), sa.Column("payload", postgresql.JSONB(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_index("ix_system_events_event_type", "system_events", ["event_type"])


def downgrade() -> None:
    op.drop_table("system_events")
    op.drop_table("oauth_states")
    op.drop_table("instruments")
