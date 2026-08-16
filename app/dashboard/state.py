from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DashboardState:
    trading_mode: str
    broker_connected: bool
    market: dict[str, float]
    regime: str
    signal: str
    risk: float
    drawdown: float
    margin_utilization: float
    positions: list[dict[str, Any]]
    orders: list[dict[str, Any]]
    kill_switch_state: str
    no_trade_reason: str = ""


class DashboardStateBuilder:
    """Builds a readable paper-trading dashboard snapshot for local monitoring."""

    def build(
        self,
        *,
        trading_mode: str,
        broker_connected: bool,
        nift50: float,
        banknifty: float,
        vix: float,
        gold: float,
        silver: float,
        crude: float,
        usdinr: float,
        regime: str,
        signal: str,
        risk: float,
        drawdown: float,
        margin_utilization: float,
        positions: list[dict[str, Any]],
        orders: list[dict[str, Any]],
        kill_switch_state: str,
        no_trade_reason: str = "",
    ) -> DashboardState:
        return DashboardState(
            trading_mode=trading_mode,
            broker_connected=broker_connected,
            market={
                "NIFTY": float(nift50),
                "BANKNIFTY": float(banknifty),
                "India VIX": float(vix),
                "Gold": float(gold),
                "Silver": float(silver),
                "Crude": float(crude),
                "USDINR": float(usdinr),
            },
            regime=regime,
            signal=signal,
            risk=float(risk),
            drawdown=float(drawdown),
            margin_utilization=float(margin_utilization),
            positions=positions,
            orders=orders,
            kill_switch_state=kill_switch_state,
            no_trade_reason=no_trade_reason,
        )
