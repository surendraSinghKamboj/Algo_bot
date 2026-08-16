from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from app.engine.hedge import compute_hedge_quantity
from app.portfolio.ledger import PositionLedger


@dataclass
class PortfolioRisk:
    equity: float
    cash: float
    used_margin: float
    realized_pnl: float
    unrealized_pnl: float
    total_delta: float
    details: dict


class PortfolioRiskAggregator:
    """Compute portfolio level risk metrics from a PositionLedger and market prices."""

    def assess(self, ledger: PositionLedger, market_prices: Dict[str, float], greeks_map: Optional[Dict[str, float]] = None) -> PortfolioRisk:
        cash = ledger.cash
        unrealized = ledger.unrealized_pnl(mark_prices=market_prices)
        total_delta = 0.0
        for key, pos in ledger.positions.items():
            if greeks_map and key in greeks_map:
                total_delta += pos.quantity * float(greeks_map[key])
        net = ledger.net_pnl(mark_prices=market_prices)
        realized = net - unrealized
        equity = cash + sum((float(market_prices.get(key, pos.average_price)) - pos.average_price) * pos.quantity for key, pos in ledger.positions.items()) + realized
        used_margin = max(0.0, sum(abs(pos.quantity) * max(pos.average_price, 0.0) for pos in ledger.positions.values()) * 0.1)
        details = {
            "position_count": len(ledger.positions),
            "market_prices": market_prices,
            "portfolio_value": ledger.portfolio_value(mark_prices=market_prices),
        }
        return PortfolioRisk(equity=equity, cash=cash, used_margin=used_margin, realized_pnl=realized, unrealized_pnl=unrealized, total_delta=total_delta, details=details)


class AutomatedHedgeJob:
    """Simple job that proposes a hedge order to neutralize a portfolio delta using a hedge instrument."""

    def propose_hedge(self, exposure_delta: float, hedge_instrument_delta: float, lot_size: int = 1) -> int:
        return compute_hedge_quantity(exposure_delta, hedge_instrument_delta, lot_size)
