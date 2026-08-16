from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Instrument(Base, Timestamped):
    __tablename__ = "instruments"
    instrument_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    exchange_token: Mapped[str | None] = mapped_column(String(64))
    segment: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    exchange: Mapped[str] = mapped_column(String(16), nullable=False)
    instrument_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    trading_symbol: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(256))
    underlying_key: Mapped[str | None] = mapped_column(String(128), index=True)
    expiry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    strike_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    lot_size: Mapped[int | None] = mapped_column(Integer)
    minimum_lot: Mapped[int | None] = mapped_column(Integer)
    tick_size: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    weekly: Mapped[bool | None] = mapped_column(Boolean)
    trading_status: Mapped[str] = mapped_column(String(24), default="ACTIVE", nullable=False)
    source_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)


class OAuthState(Base):
    __tablename__ = "oauth_states"
    state: Mapped[str] = mapped_column(String(128), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OHLCV(Base, Timestamped):
    __tablename__ = "ohlcv"
    __table_args__ = (UniqueConstraint("instrument_key", "timeframe", "start_at", name="uq_ohlcv_instrument_timeframe_start"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_key: Mapped[str] = mapped_column(ForeignKey("instruments.instrument_key"), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    open_interest: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(48), nullable=False)


class MarketTickRecord(Base):
    __tablename__ = "market_ticks"
    __table_args__ = (UniqueConstraint("instrument_key", "observed_at", "source", name="uq_market_tick_source_time"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    instrument_key: Mapped[str] = mapped_column(ForeignKey("instruments.instrument_key"), nullable=False, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ltp: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[int | None] = mapped_column(BigInteger)
    open_interest: Mapped[int | None] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(String(48), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OptionChainSnapshot(Base):
    __tablename__ = "option_chain_snapshots"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    underlying_key: Mapped[str] = mapped_column(ForeignKey("instruments.instrument_key"), nullable=False, index=True)
    expiry_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)


class FeatureSnapshot(Base):
    __tablename__ = "feature_snapshots"
    __table_args__ = (UniqueConstraint("instrument_key", "timeframe", "observed_at", name="uq_feature_snapshot_key_time"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    instrument_key: Mapped[str] = mapped_column(ForeignKey("instruments.instrument_key"), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    values: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RegimeRecord(Base):
    __tablename__ = "regimes"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    instrument_key: Mapped[str | None] = mapped_column(ForeignKey("instruments.instrument_key"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    regime: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    reasons: Mapped[dict] = mapped_column(JSONB, nullable=False)


class SignalRecord(Base):
    __tablename__ = "signals"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    strategy: Mapped[str] = mapped_column(String(64), nullable=False)
    instrument_key: Mapped[str | None] = mapped_column(ForeignKey("instruments.instrument_key"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(8, 5), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)


class OrderRecord(Base, Timestamped):
    __tablename__ = "orders"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    client_order_id: Mapped[str] = mapped_column(String(96), unique=True, nullable=False)
    trading_mode: Mapped[str] = mapped_column(String(8), nullable=False)
    instrument_key: Mapped[str] = mapped_column(ForeignKey("instruments.instrument_key"), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    requested_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    filled_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    filled_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class PositionRecord(Base, Timestamped):
    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("trading_mode", "instrument_key", name="uq_position_mode_instrument"),)
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    trading_mode: Mapped[str] = mapped_column(String(8), nullable=False)
    instrument_key: Mapped[str] = mapped_column(ForeignKey("instruments.instrument_key"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    average_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    trading_mode: Mapped[str] = mapped_column(String(8), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    equity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    cash: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    used_margin: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False)


class RiskEvent(Base):
    __tablename__ = "risk_events"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False)


class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    strategy: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    backtest_run_id: Mapped[UUID] = mapped_column(ForeignKey("backtest_runs.id"), nullable=False, index=True)
    instrument_key: Mapped[str] = mapped_column(String(128), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    details: Mapped[dict] = mapped_column(JSONB, nullable=False)


class SystemEvent(Base):
    __tablename__ = "system_events"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
