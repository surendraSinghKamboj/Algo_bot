Trading Engine: Pipeline and Decision Gates
==========================================

Overview
--------
The trading engine is designed as a pipeline of independent stages. Each stage is testable and exposes intermediate results via API or persistence so the system can be inspected at each step.

Pipeline
--------
1. Market Data
   - Ticks and candle ingestion
   - Instrument resolution
2. Feature Engine
   - Computes indicators (moving averages, vol, momentum)
3. Regime Engine
   - Classifies market state (BULL_TREND, BEAR_TREND, RANGE, HIGH_VOL)
4. Signal Engine
   - Strategy-specific scoring and buy/sell/hedge/exit decisions
5. Option Structure
   - Option chain selection, candidate spreads, Greeks, payoff
6. Hedge Engine
   - Calculates hedge quantities (delta, vega neutral suggestions)
7. Portfolio Risk
   - Aggregates exposures and runs risk checks (limits, drawdown, CVaR)
8. Order Plan
   - Constructs executable order(s) for the broker (paper by default)
9. Execution & Reconciliation
   - Tracks lifecycle and reconciles positions & P&L

Decision gates (no-trade reasons)
---------------------------------
A trade is rejected (NO TRADE) if any of the following apply:
- Risk limit breached (e.g., projected margin > allowed)
- Kill switch active
- Regime incompatible with strategy
- Insufficient available capital
- Instrument-specific constraints (lot size, market hours)

Trade types
-----------
- TRADE: Place or schedule a new position following entry rules
- NO TRADE: Do nothing
- REDUCE RISK: Close or reduce size of current exposures
- HEDGE: Place offsetting hedging orders
- EXIT: Close position according to stop/target/exit rule

Safety
------
- system default TRADING_MODE=PAPER
- LIVE mode requires explicit LIVE_TRADING_CONFIRMATION set in environment
- All live order endpoints are behind safety checks

Observability
-------------
- Each pipeline stage persists metadata and inputs/outputs in lightweight tables (snapshots) to allow traceability and reproducibility.
- For debugging the pipeline, recover a step-by-step reconstruction for any trade decision by recomputing the pipeline using persisted snapshots.

Testing
-------
- Unit tests for each stage
- Integration tests for the entire pipeline using deterministic mock providers for market and broker
- Backtests to validate strategy performance using historical data

This document is a reference for implementers. For strategy-specific rules see docs/STRATEGIES.md.
