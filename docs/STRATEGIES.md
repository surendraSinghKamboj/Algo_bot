Implemented strategies
======================

Only strategies that are actually implemented are documented here. Do not assume any strategy is validated or production-ready unless explicitly tested and marked.

NIFTY Strategy (implemented)
-----------------------------
- Objective: Defined-risk options strategy targeted at NIFTY index to capture directional edge while limiting max loss.
- Inputs:
  - Market ticks and intra-day candles for NIFTY
  - Volatility (IV) surface (option chain)
  - Regime signal
  - Portfolio risk budget
- Entry conditions:
  - Regime is BULL_TREND and signal score > threshold
  - Sufficient IV skew/structure to sell premium (if defined by strategy)
- Exit conditions:
  - Target reached (percent or absolute)
  - Stop-loss triggered
  - Regime change to incompatible state (e.g., BEAR_TREND)
- Hedge rules:
  - Hedge delta exposure with index futures or options as computed by the Hedge Engine
- Position sizing:
  - Uses portfolio sizing module (risk-based sizing). Respect lot_size.
- Risk parameters:
  - max_loss per trade (absolute or percentage)
  - max_exposure (per underlying)
- Validation:
  - Marked as PAPER-tested (see unit tests). Backtesting and walk-forward testing not yet validated for live performance.

Notes
-----
- Transaction costs, slippage and brokerage are included as configurable parameters in strategy settings. These are used in backtests and sizing calculations.
- Strategies must be accompanied by unit tests that validate decision boundaries and a backtest harness for historical evaluation.

Not implemented
---------------
- Cross-asset macro strategies (TODO)
- Multi-leg dynamic allocation strategies (TODO)

The frontend and operators should treat strategy outputs as advisory until the strategy is verified in backtest and paper trading environments.
