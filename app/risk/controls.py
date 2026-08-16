from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskLimitConfig:
    risk_per_trade: float = 0.01
    portfolio_open_risk: float = 0.03
    daily_loss_limit: float = 0.05
    weekly_loss_limit: float = 0.08
    max_drawdown: float = 0.15
    max_correlated_exposure: float = 0.20
    max_sector_concentration: float = 0.30
    max_simultaneous_trades: int = 4


@dataclass(frozen=True)
class RiskAssessment:
    allowed: bool
    adjusted_risk: float
    reason: str


class RiskController:
    """Reject-by-default portfolio risk gate for candidates that violate configured limits."""

    def __init__(self, config: RiskLimitConfig | None = None):
        self.config = config or RiskLimitConfig()

    def evaluate(
        self,
        *,
        proposed_risk: float,
        current_portfolio_risk: float,
        daily_pnl: float,
        weekly_pnl: float,
        drawdown: float,
        correlated_exposure: float,
        sector_concentration: float | None = None,
        simultaneous_trades: int | None = None,
    ) -> RiskAssessment:
        if proposed_risk <= 0:
            return RiskAssessment(False, 0.0, "proposed risk must be positive")

        if proposed_risk > self.config.risk_per_trade:
            return RiskAssessment(False, 0.0, "risk budget exceeded for a single trade")

        if current_portfolio_risk + proposed_risk > self.config.portfolio_open_risk:
            return RiskAssessment(False, 0.0, "risk budget exceeded for portfolio open risk")

        if daily_pnl <= -self.config.daily_loss_limit:
            return RiskAssessment(False, 0.0, "daily loss limit reached")

        if weekly_pnl <= -self.config.weekly_loss_limit:
            return RiskAssessment(False, 0.0, "weekly loss limit reached")

        if drawdown >= self.config.max_drawdown:
            return RiskAssessment(False, 0.0, "drawdown limit reached")

        if correlated_exposure > self.config.max_correlated_exposure:
            return RiskAssessment(False, 0.0, "correlated exposure exceeds configured threshold")

        if sector_concentration is not None and sector_concentration > self.config.max_sector_concentration:
            return RiskAssessment(False, 0.0, "sector concentration exceeds limit")

        if simultaneous_trades is not None and simultaneous_trades > self.config.max_simultaneous_trades:
            return RiskAssessment(False, 0.0, "maximum simultaneous trades exceeded")

        return RiskAssessment(True, proposed_risk, "within configured portfolio and risk limits")
