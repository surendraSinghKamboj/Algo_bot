from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PositionSizing:
    quantity: int
    allocated_risk: float


class PortfolioManager:
    """Capital-aware sizing manager. It deliberately prefers risk control over aggressive leverage."""

    def __init__(self, starting_cash: float, max_portfolio_risk: float, max_trade_risk: float):
        self.starting_cash = float(starting_cash)
        self.max_portfolio_risk = float(max_portfolio_risk)
        self.max_trade_risk = float(max_trade_risk)

    def position_size(self, *, risk_budget: float, stop_loss: float, entry: float) -> int:
        if stop_loss <= 0 or entry <= 0:
            raise ValueError("stop_loss and entry must be positive")
        if risk_budget <= 0:
            raise ValueError("risk_budget must be positive")
        risk_per_unit = abs(entry - stop_loss)
        if risk_per_unit == 0:
            raise ValueError("stop loss cannot equal entry price")
        raw_quantity = risk_budget / risk_per_unit
        return max(0, int(raw_quantity))

    def allowed_trade_risk(self, equity: float) -> float:
        return min(self.max_trade_risk * equity, self.max_portfolio_risk * self.starting_cash)
