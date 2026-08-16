from __future__ import annotations

from fastapi import APIRouter

from app.dashboard.state import DashboardStateBuilder

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/state")
def dashboard_state() -> dict:
    builder = DashboardStateBuilder()
    dashboard = builder.build(
        trading_mode="PAPER",
        broker_connected=False,
        nift50=22350.0,
        banknifty=48000.0,
        vix=15.4,
        gold=71120.0,
        silver=92100.0,
        crude=6456.0,
        usdinr=83.4,
        regime="BULL_TREND",
        signal="NO TRADE",
        risk=0.018,
        drawdown=0.09,
        margin_utilization=0.23,
        positions=[{"instrument": "NSE_INDEX|Nifty 50", "qty": 0, "pnl": 0.0}],
        orders=[{"status": "SIMULATED", "qty": 0}],
        kill_switch_state="OK",
        no_trade_reason="No trade; awaiting a risk-adjusted setup.",
    )
    return {
        "trading_mode": dashboard.trading_mode,
        "broker_connected": dashboard.broker_connected,
        "market": dashboard.market,
        "regime": dashboard.regime,
        "signal": dashboard.signal,
        "risk": dashboard.risk,
        "drawdown": dashboard.drawdown,
        "margin_utilization": dashboard.margin_utilization,
        "positions": dashboard.positions,
        "orders": dashboard.orders,
        "kill_switch_state": dashboard.kill_switch_state,
        "no_trade_reason": dashboard.no_trade_reason,
    }
