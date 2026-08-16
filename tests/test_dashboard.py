from app.dashboard.state import DashboardState, DashboardStateBuilder


def test_dashboard_builder_reports_paper_mode_and_market_snapshot():
    builder = DashboardStateBuilder()
    dashboard = builder.build(
        trading_mode="PAPER",
        broker_connected=True,
        nift50=22345.0,
        banknifty=48010.0,
        vix=15.2,
        gold=71140.0,
        silver=92500.0,
        crude=6463.0,
        usdinr=83.5,
        regime="BULL_TREND",
        signal="BUY",
        risk=0.018,
        drawdown=0.09,
        margin_utilization=0.24,
        positions=[{"instrument": "NSE_INDEX|Nifty 50", "qty": 25, "pnl": 1200.0}],
        orders=[{"status": "SIMULATED"}],
        kill_switch_state="OK",
        no_trade_reason="",
    )
    assert dashboard.trading_mode == "PAPER"
    assert dashboard.broker_connected is True
    assert dashboard.market["NIFTY"] == 22345.0
    assert dashboard.regime == "BULL_TREND"
    assert dashboard.signal == "BUY"
    assert dashboard.orders[0]["status"] == "SIMULATED"


def test_dashboard_builder_marks_no_trade_reason():
    builder = DashboardStateBuilder()
    dashboard = builder.build(
        trading_mode="PAPER",
        broker_connected=False,
        nift50=22300.0,
        banknifty=47980.0,
        vix=30.0,
        gold=71000.0,
        silver=92000.0,
        crude=6400.0,
        usdinr=83.2,
        regime="VOL_SHOCK",
        signal="NO TRADE",
        risk=0.04,
        drawdown=0.11,
        margin_utilization=0.40,
        positions=[],
        orders=[],
        kill_switch_state="ARMED",
        no_trade_reason="VIX shock and poor expected edge",
    )
    assert dashboard.signal == "NO TRADE"
    assert dashboard.no_trade_reason == "VIX shock and poor expected edge"
