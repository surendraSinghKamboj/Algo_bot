"""research and paper execution schema

Revision ID: 20260816_0003
Revises: 20260816_0002
Create Date: 2026-08-16 00:30:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260816_0003"
down_revision = "20260816_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("market_ticks", sa.Column("id", sa.BigInteger(), primary_key=True), sa.Column("instrument_key", sa.String(128), sa.ForeignKey("instruments.instrument_key"), nullable=False), sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("ltp", sa.Numeric(18, 4), nullable=False), sa.Column("volume", sa.BigInteger()), sa.Column("open_interest", sa.BigInteger()), sa.Column("source", sa.String(48), nullable=False), sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.UniqueConstraint("instrument_key", "observed_at", "source", name="uq_market_tick_source_time"))
    op.create_index("ix_market_ticks_instrument_key", "market_ticks", ["instrument_key"])
    op.create_index("ix_market_ticks_observed_at", "market_ticks", ["observed_at"])
    op.create_table("option_chain_snapshots", sa.Column("id", sa.BigInteger(), primary_key=True), sa.Column("underlying_key", sa.String(128), sa.ForeignKey("instruments.instrument_key"), nullable=False), sa.Column("expiry_date", sa.DateTime(timezone=True), nullable=False), sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("source_payload", postgresql.JSONB(), nullable=False))
    op.create_index("ix_option_chain_snapshots_underlying_key", "option_chain_snapshots", ["underlying_key"])
    op.create_index("ix_option_chain_snapshots_expiry_date", "option_chain_snapshots", ["expiry_date"])
    op.create_index("ix_option_chain_snapshots_observed_at", "option_chain_snapshots", ["observed_at"])
    op.create_table("feature_snapshots", sa.Column("id", sa.BigInteger(), primary_key=True), sa.Column("instrument_key", sa.String(128), sa.ForeignKey("instruments.instrument_key"), nullable=False), sa.Column("timeframe", sa.String(8), nullable=False), sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("values", postgresql.JSONB(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.UniqueConstraint("instrument_key", "timeframe", "observed_at", name="uq_feature_snapshot_key_time"))
    op.create_index("ix_feature_snapshots_instrument_key", "feature_snapshots", ["instrument_key"])
    op.create_index("ix_feature_snapshots_observed_at", "feature_snapshots", ["observed_at"])
    op.create_table("regimes", sa.Column("id", sa.BigInteger(), primary_key=True), sa.Column("instrument_key", sa.String(128), sa.ForeignKey("instruments.instrument_key")), sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("regime", sa.String(32), nullable=False), sa.Column("confidence", sa.Numeric(6, 5), nullable=False), sa.Column("reasons", postgresql.JSONB(), nullable=False))
    op.create_index("ix_regimes_instrument_key", "regimes", ["instrument_key"])
    op.create_index("ix_regimes_observed_at", "regimes", ["observed_at"])
    op.create_table("signals", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("strategy", sa.String(64), nullable=False), sa.Column("instrument_key", sa.String(128), sa.ForeignKey("instruments.instrument_key")), sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("action", sa.String(24), nullable=False), sa.Column("score", sa.Numeric(8, 5), nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("explanation", sa.Text(), nullable=False), sa.Column("payload", postgresql.JSONB(), nullable=False))
    op.create_index("ix_signals_instrument_key", "signals", ["instrument_key"])
    op.create_index("ix_signals_observed_at", "signals", ["observed_at"])
    op.create_table("orders", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("client_order_id", sa.String(96), unique=True, nullable=False), sa.Column("trading_mode", sa.String(8), nullable=False), sa.Column("instrument_key", sa.String(128), sa.ForeignKey("instruments.instrument_key"), nullable=False), sa.Column("side", sa.String(8), nullable=False), sa.Column("quantity", sa.Integer(), nullable=False), sa.Column("order_type", sa.String(16), nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("requested_price", sa.Numeric(18, 4)), sa.Column("filled_price", sa.Numeric(18, 4)), sa.Column("filled_quantity", sa.Integer(), nullable=False, server_default="0"), sa.Column("estimated_cost", sa.Numeric(18, 4), nullable=False, server_default="0"), sa.Column("metadata_json", postgresql.JSONB(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_index("ix_orders_instrument_key", "orders", ["instrument_key"])
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_table("positions", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("trading_mode", sa.String(8), nullable=False), sa.Column("instrument_key", sa.String(128), sa.ForeignKey("instruments.instrument_key"), nullable=False), sa.Column("quantity", sa.Integer(), nullable=False), sa.Column("average_price", sa.Numeric(18, 4), nullable=False), sa.Column("realized_pnl", sa.Numeric(18, 4), nullable=False, server_default="0"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.UniqueConstraint("trading_mode", "instrument_key", name="uq_position_mode_instrument"))
    op.create_table("portfolio_snapshots", sa.Column("id", sa.BigInteger(), primary_key=True), sa.Column("trading_mode", sa.String(8), nullable=False), sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("equity", sa.Numeric(18, 4), nullable=False), sa.Column("cash", sa.Numeric(18, 4), nullable=False), sa.Column("used_margin", sa.Numeric(18, 4), nullable=False), sa.Column("realized_pnl", sa.Numeric(18, 4), nullable=False), sa.Column("unrealized_pnl", sa.Numeric(18, 4), nullable=False), sa.Column("details", postgresql.JSONB(), nullable=False))
    op.create_index("ix_portfolio_snapshots_observed_at", "portfolio_snapshots", ["observed_at"])
    op.create_table("risk_events", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("observed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("event_type", sa.String(48), nullable=False), sa.Column("severity", sa.String(16), nullable=False), sa.Column("message", sa.Text(), nullable=False), sa.Column("details", postgresql.JSONB(), nullable=False))
    op.create_index("ix_risk_events_event_type", "risk_events", ["event_type"])
    op.create_table("backtest_runs", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("strategy", sa.String(64), nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("parameters", postgresql.JSONB(), nullable=False), sa.Column("metrics", postgresql.JSONB(), nullable=False))
    op.create_table("backtest_trades", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("backtest_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("backtest_runs.id"), nullable=False), sa.Column("instrument_key", sa.String(128), nullable=False), sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False), sa.Column("closed_at", sa.DateTime(timezone=True)), sa.Column("quantity", sa.Integer(), nullable=False), sa.Column("entry_price", sa.Numeric(18, 4), nullable=False), sa.Column("exit_price", sa.Numeric(18, 4)), sa.Column("realized_pnl", sa.Numeric(18, 4)), sa.Column("details", postgresql.JSONB(), nullable=False))
    op.create_index("ix_backtest_trades_backtest_run_id", "backtest_trades", ["backtest_run_id"])


def downgrade() -> None:
    for table in ("backtest_trades", "backtest_runs", "risk_events", "portfolio_snapshots", "positions", "orders", "signals", "regimes", "feature_snapshots", "option_chain_snapshots", "market_ticks"):
        op.drop_table(table)
