from app.execution.order_plan import OrderPlan, OrderPlanner
from app.notifications.alerts import AlertEvent, AlertService
from app.risk.kill_switch import EmergencyPolicy, KillSwitchController


def test_order_planner_rejects_trade_when_risk_limits_fail():
    planner = OrderPlanner(max_open_risk=0.03, max_trade_risk=0.01)
    plan = planner.plan(
        signal_action="BUY",
        instrument_key="NSE_INDEX|Nifty 50",
        quantity=100,
        entry_price=22000.0,
        stop_loss=21800.0,
        target=22400.0,
        proposed_risk=0.03,
        current_portfolio_risk=0.02,
        daily_loss=0.04,
        weekly_loss=0.06,
        drawdown=0.12,
        correlated_exposure=0.18,
    )
    assert plan is None


def test_order_planner_accepts_safe_trade():
    planner = OrderPlanner(max_open_risk=0.05, max_trade_risk=0.01)
    plan = planner.plan(
        signal_action="BUY",
        instrument_key="NSE_INDEX|Nifty 50",
        quantity=25,
        entry_price=22100.0,
        stop_loss=21980.0,
        target=22450.0,
        proposed_risk=0.006,
        current_portfolio_risk=0.015,
        daily_loss=0.01,
        weekly_loss=0.02,
        drawdown=0.08,
        correlated_exposure=0.10,
    )
    assert plan is not None
    assert plan.action == "BUY"
    assert plan.order_type == "LIMIT"


def test_kill_switch_and_alert_service_trigger_expected_events():
    switch = KillSwitchController(
        max_daily_loss=0.04,
        max_weekly_loss=0.06,
        max_drawdown=0.12,
        emergency_policy=EmergencyPolicy.HOLD,
    )
    alert_service = AlertService()
    assert switch.evaluate(daily_loss=-0.05, weekly_loss=-0.03, drawdown=0.11) is True
    alert = alert_service.create_alert(AlertEvent.RISK_LIMIT_BREACH, "daily loss limit reached")
    assert alert.event_type == AlertEvent.RISK_LIMIT_BREACH
    assert "daily loss" in alert.message.lower()
