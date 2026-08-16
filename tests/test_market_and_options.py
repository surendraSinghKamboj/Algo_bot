from app.market.service import MarketDataService
from app.options.greeks import OptionGreeks, OptionPayoff, calculate_option_greeks, payoff_curve


def test_market_data_service_returns_snapshot():
    service = MarketDataService()
    snapshot = service.snapshot()
    assert snapshot["NIFTY"] > 0
    assert snapshot["India VIX"] > 0
    assert snapshot["trading_mode"] == "PAPER"


def test_option_greeks_are_reasonable():
    greeks = calculate_option_greeks(
        option_type="CALL",
        spot=22000.0,
        strike=22100.0,
        time_to_expiry=0.12,
        risk_free_rate=0.05,
        volatility=0.18,
    )
    assert greeks.delta > 0
    assert greeks.gamma > 0
    assert greeks.vega > 0


def test_payoff_curve_respects_defined_risk_bound():
    payoff = payoff_curve(
        option_type="PUT",
        strike=22000.0,
        premium=180.0,
        price_range=[21500, 22000, 22500],
    )
    assert len(payoff) == 3
    assert payoff[1]["payoff"] <= 0
    assert payoff[2]["profit_loss"] <= 0


def test_option_payoff_model_reports_max_loss():
    result = OptionPayoff(
        trade_type="Bull Call Spread",
        max_loss=120.0,
        max_profit=180.0,
        break_even=22140.0,
    )
    assert result.max_loss == 120.0
    assert result.max_profit == 180.0
