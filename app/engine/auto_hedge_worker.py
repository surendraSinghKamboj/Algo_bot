from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from app.portfolio.risk import PortfolioRiskAggregator, AutomatedHedgeJob


@dataclass
class HedgeProposal:
    instrument_key: str
    hedge_quantity: int
    reason: str


class AutoHedgeWorker:
    """Compute hedge proposals based on ledger exposure and available hedge instruments.

    The worker is deliberately side-effect free: it returns proposals, callers may
    choose to persist them or submit orders to a broker.
    """

    def __init__(self, ledger, hedge_candidates: Dict[str, float]):
        """hedge_candidates: mapping hedge_instrument_key -> per-unit delta"""
        self.ledger = ledger
        self.hedge_candidates = dict(hedge_candidates)
        self.aggregator = PortfolioRiskAggregator()
        self.hedger = AutomatedHedgeJob()

    def run_once(self, market_prices: Dict[str, float], greeks_map: Dict[str, float]) -> List[HedgeProposal]:
        summary = self.aggregator.assess(self.ledger, market_prices, greeks_map)
        exposure = summary.total_delta
        proposals: List[HedgeProposal] = []
        if abs(exposure) < 1e-6:
            return proposals
        # pick the candidate with the largest absolute hedge delta magnitude to minimize quantity
        best = max(self.hedge_candidates.items(), key=lambda kv: abs(kv[1]))
        hedge_key, hedge_delta = best
        qty = self.hedger.propose_hedge(exposure, hedge_delta, lot_size=1)
        proposals.append(HedgeProposal(instrument_key=hedge_key, hedge_quantity=qty, reason=f"neutralize exposure {exposure}"))
        return proposals
