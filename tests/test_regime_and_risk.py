from app.regimes.engine import RegimeEngine, RegimeState
from app.risk.controls import RiskController, RiskLimitConfig


def test_regime_engine_identifies_bull_trend():
    engine = RegimeEngine()
    features = {
        "trend_score": 0.06,
        "momentum": 0.035,
        "realized_volatility": 0.12,
        "vix_level": 14.5,
        "vix_zscore": -0.8,
        "vix_change": -0.04,
        "breadth_score": 0.55,
        "cross_asset_score": 0.6,
        "correlation_regime": "stable",
    }
    decision = engine.classify(features)
    assert decision.state is RegimeState.BULL_TREND
    assert decision.confidence > 0.5


def test_regime_engine_flags_volatility_shock():
    engine = RegimeEngine()
    features = {
        "trend_score": -0.02,
        "momentum": -0.07,
        "realized_volatility": 0.35,
        "vix_level": 31.0,
        "vix_zscore": 2.8,
        "vix_change": 0.18,
        "breadth_score": -0.25,
        "cross_asset_score": -0.4,
        "correlation_regime": "unstable",
    }
    decision = engine.classify(features)
    assert decision.state in {RegimeState.VOL_SHOCK, RegimeState.CRISIS}


def test_risk_controller_rejects_out_of_budget_trade():
    controller = RiskController(
        RiskLimitConfig(
            risk_per_trade=0.01,
            portfolio_open_risk=0.03,
            daily_loss_limit=0.05,
            weekly_loss_limit=0.08,
            max_drawdown=0.15,
            max_correlated_exposure=0.20,
        )
    )
    assessment = controller.evaluate(
        proposed_risk=0.015,
        current_portfolio_risk=0.04,
        daily_pnl=-0.03,
        weekly_pnl=-0.06,
        drawdown=0.11,
        correlated_exposure=0.22,
    )
    assert assessment.allowed is False
    assert "risk budget" in assessment.reason.lower()


def test_risk_controller_allows_small_safe_trade():
    controller = RiskController(
        RiskLimitConfig(
            risk_per_trade=0.01,
            portfolio_open_risk=0.03,
            daily_loss_limit=0.05,
            weekly_loss_limit=0.08,
            max_drawdown=0.15,
            max_correlated_exposure=0.20,
        )
    )
    assessment = controller.evaluate(
        proposed_risk=0.008,
        current_portfolio_risk=0.02,
        daily_pnl=-0.01,
        weekly_pnl=-0.03,
        drawdown=0.08,
        correlated_exposure=0.12,
    )
    assert assessment.allowed is True
    assert assessment.adjusted_risk == 0.008
