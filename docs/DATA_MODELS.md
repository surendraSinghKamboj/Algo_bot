Data Models
===========
This document enumerates the primary data models used across the backend and exposed via API responses.

Model: Instrument
- id: integer (DB primary key)
- exchange: string (e.g., "NSE")
- symbol: string (exchange-specific symbol)
- name: string
- lot_size: integer (nullable)
- tick_size: float
- active: boolean
- Example:
  {
    "exchange": "NSE",
    "symbol": "NIFTY 50",
    "name": "Nifty 50 Index",
    "lot_size": 1,
    "tick_size": 0.05,
    "active": true
  }

Model: MarketTick
- instrument_key: string (unique identifier, e.g., "NSE_INDEX|Nifty 50")
- timestamp: ISO8601 string
- ltp: float (last traded price)
- bid: float | null
- ask: float | null
- volume: integer | null
- Example:
  {
    "instrument_key": "NSE_INDEX|Nifty 50",
    "timestamp": "2026-08-16T09:24:00.123Z",
    "ltp": 22350.25,
    "bid": 22350.0,
    "ask": 22350.5,
    "volume": 12345
  }

Model: OHLCV
- instrument_key: string
- start: ISO8601
- open: float
- high: float
- low: float
- close: float
- volume: integer
- interval: string (e.g., '1m', '5m', '1d')

Model: OptionContract
- instrument_key: string
- strike: float
- expiry: date
- option_type: enum("CE","PE")
- ltp: float
- iv: float (implied vol, decimal e.g., 0.18)
- greeks: {delta: float, gamma: float, theta: float, vega: float}

Model: OptionChainSnapshot
- underlying_key: string
- timestamp: ISO8601
- expiry: date
- strikes: [OptionContract]

Model: Signal
- id: uuid
- created_at: ISO8601
- symbol: string
- signal: enum("BUY","SELL","NO TRADE","HEDGE","EXIT")
- score: float
- regime: string
- explanation: string

Model: Order (paper)
- id: uuid
- instrument_key: string
- qty: integer
- side: enum("BUY","SELL")
- price: float | null
- status: enum("PENDING","EXECUTED","CANCELLED","REJECTED")
- created_at: ISO8601
- executed_at: ISO8601 | null

Model: Position
- instrument_key: string
- qty: integer (positive = long, negative = short)
- entry_price: float
- ltp: float
- unrealized_pnl: float
- realized_pnl: float

Model: Portfolio
- equity: float
- available_cash: float
- used_margin: float
- positions: [Position]
- total_unrealized_pnl: float
- total_realized_pnl: float

Model: RiskSnapshot
- timestamp: ISO8601
- portfolio_value: float
- daily_loss: float
- weekly_loss: float
- max_drawdown: float
- cvar_95: float
- expected_shortfall_95: float
- margin_utilization: float
- correlated_exposure: float

Model: BacktestRun
- id: uuid
- started_at: ISO8601
- completed_at: ISO8601
- equity_curve: [{timestamp, equity}]
- metrics: {cagr, max_drawdown, sharpe, sortino, profit_factor}
- trades: [BacktestTrade]

Notes on numeric units and types
- Prices: quoted in INR for Indian-market instruments (float). Use decimals for accounting-grade persistence if required.
- Quantities: integer number of contracts or units. For indices, the lot size is important (see Instrument.lot_size).
- Greeks: dimensionless (Delta in contract units per 1 unit of underlying; Vega per 1 vol point).
- Timestamps: ISO8601 UTC recommended; use Z suffix.

This document should be kept in sync with Pydantic/SQLAlchemy models in the backend.
