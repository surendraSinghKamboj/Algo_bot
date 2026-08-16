from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrderPlan:
    strategy: str
    action: str
    instrument_key: str
    quantity: int
    entry_price: float
    stop_loss: float
    target: float
    order_type: str
    notes: str


class OrderPlanner:
    """Builds executable orders only when risk and exposure checks pass."""

    def __init__(self, max_open_risk: float = 0.05, max_trade_risk: float = 0.01):
        self.max_open_risk = float(max_open_risk)
        self.max_trade_risk = float(max_trade_risk)

    def plan(
        self,
        *,
        signal_action: str,
        instrument_key: str,
        quantity: int,
        entry_price: float,
        stop_loss: float,
        target: float,
        proposed_risk: float,
        current_portfolio_risk: float,
        daily_loss: float,
        weekly_loss: float,
        drawdown: float,
        correlated_exposure: float,
        strategy: str = "regime_multi_factor",
    ) -> OrderPlan | None:
        if proposed_risk <= 0 or quantity <= 0:
            return None
        if proposed_risk > self.max_trade_risk:
            return None
        if current_portfolio_risk + proposed_risk > self.max_open_risk:
            return None
        if daily_loss <= -0.04:
            return None
        if weekly_loss <= -0.06:
            return None
        if drawdown >= 0.12:
            return None
        if correlated_exposure > 0.20:
            return None

        return OrderPlan(
            strategy=strategy,
            action=signal_action,
            instrument_key=instrument_key,
            quantity=quantity,
            entry_price=float(entry_price),
            stop_loss=float(stop_loss),
            target=float(target),
            order_type="LIMIT",
            notes="risk limits satisfied; order is eligible for paper or explicit live execution",
        )
