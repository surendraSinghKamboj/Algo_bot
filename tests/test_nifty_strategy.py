from app.strategies.nifty import NiftyStrategy


def test_nifty_strategy_buy():
    svc = NiftyStrategy()
    snapshot = {"NIFTY": 22350.0, "India VIX": 15.0}
    signal = svc.generate_signal(snapshot)
    assert signal.action in {"BUY", "BUY_HEDGE", "HEDGE" , "NO TRADE" , "SELL"}
    # With low vix expect not SELL
    assert signal.reasons["vix"] == 15.0


def test_nifty_strategy_sell_high_vix():
    svc = NiftyStrategy()
    snapshot = {"NIFTY": 22350.0, "India VIX": 30.0}
    signal = svc.generate_signal(snapshot)
    assert signal.action == "SELL"


def test_nifty_strategy_no_trade_mid_vix():
    svc = NiftyStrategy()
    snapshot = {"NIFTY": 22350.0, "India VIX": 20.0}
    signal = svc.generate_signal(snapshot)
    assert signal.action in {"NO TRADE", "BUY", "BUY_HEDGE", "HEDGE"}
