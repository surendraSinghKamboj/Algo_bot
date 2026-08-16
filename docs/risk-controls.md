# Risk-control design

These constraints are design requirements and are not yet a completed execution engine.

| Gate | Default intended policy |
|---|---|
| Mode | PAPER only; live requires explicit two-part configuration and separate review |
| Per-trade risk | Configurable, initial range 0.5–1.0% of equity |
| Portfolio open risk | Configurable, initial cap 3–5% |
| Trade eligibility | Defined maximum loss, liquid quotes, viable edge after fees/slippage, compatible regime |
| Data quality | No new entry when ticks stale, feed disconnected, or duplicate/out-of-order processing detected |
| Volatility | Reduce/no trade during high VIX, volatility shock, unstable spreads, or liquidity collapse |
| Operational | Client order IDs, idempotency, reconciliation after restart, partial/rejected-order handling |
| Kill switches | Daily/weekly loss, drawdown, margin, broker disconnect, stale data, abnormal spread, rejection count, mismatch, manual stop |

Every accepted or rejected plan must persist inputs, regime, expected edge, cost estimate, max loss/profit, hedge ratio, decision, and human-readable reason. No LLM is permitted to directly execute orders.
