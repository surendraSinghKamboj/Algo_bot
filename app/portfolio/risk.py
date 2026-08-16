from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from app.portfolio.ledger import PositionLedger
from app.engine.hedge import compute_hedge_quantity


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
    """Compute portfolio level risk metrics from a PositionLedger and market prices.

    This implementation uses a conservative, deterministic approach suitable for
    paper trading and testing.
    """

    def assess(self, ledger: PositionLedger, market_prices: Dict[str, float], greeks_map: Optional[Dict[str, float]] = None) -> PortfolioRisk:
        cash = ledger.cash
        unrealized = 0.0
        total_delta = 0.0
        for key, pos in ledger.positions.items():
            mprice = float(market_prices.get(key, pos.average_price))
            unrealized += (mprice - pos.average_price) * pos.quantity
            if greeks_map and key in greeks_map:
                total_delta += pos.quantity * float(greeks_map[key])
        net = ledger.net_pnl()
        realized = net - unrealized
        equity = ledger.starting_cash + realized + unrealized
        used_margin = max(0.0, sum(abs(pos.quantity) * pos.average_price for pos in ledger.positions.values()) * 0.1)
        details = {
            "position_count": len(ledger.positions),
            "market_prices": market_prices,
        }
        return PortfolioRisk(equity=equity, cash=cash, used_margin=used_margin, realized_pnl=realized, unrealized_pnl=unrealized, total_delta=total_delta, details=details)


class AutomatedHedgeJob:
    """Simple job that proposes a hedge order to neutralize a portfolio delta using a hedge instrument.

    It does not place orders; it only returns a suggested hedge quantity.
    """

    def propose_hedge(self, exposure_delta: float, hedge_instrument_delta: float, lot_size: int = 1) -> int:
        return compute_hedge_quantity(exposure_delta, hedge_instrument_delta, lot_size)
