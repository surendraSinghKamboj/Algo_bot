from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AlertEvent(str, Enum):
    NEW_TRADE_SIGNAL = "NEW_TRADE_SIGNAL"
    HEDGE_SIGNAL = "HEDGE_SIGNAL"
    EXIT = "EXIT"
    STOP_LOSS = "STOP_LOSS"
    TARGET = "TARGET"
    VIX_ALERT = "VIX_ALERT"
    VOLATILITY_SHOCK = "VOLATILITY_SHOCK"
    CORRELATION_BREAKDOWN = "CORRELATION_BREAKDOWN"
    DATA_FEED_FAILURE = "DATA_FEED_FAILURE"
    BROKER_DISCONNECT = "BROKER_DISCONNECT"
    ORDER_REJECTION = "ORDER_REJECTION"
    RISK_LIMIT_BREACH = "RISK_LIMIT_BREACH"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"
    LIVE_MODE_SWITCH = "LIVE_MODE_SWITCH"


@dataclass(frozen=True)
class Alert:
    event_type: AlertEvent
    message: str


class AlertService:
    """Simple alert interface for internal notifications and future integrations."""

    def create_alert(self, event_type: AlertEvent, message: str) -> Alert:
        return Alert(event_type=event_type, message=message)
