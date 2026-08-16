from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EmergencyPolicy(str, Enum):
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    FLATTEN = "FLATTEN"


@dataclass(frozen=True)
class KillSwitchState:
    triggered: bool
    reason: str


class KillSwitchController:
    """Hard safety stop that halts new entries when risk limits are breached."""

    def __init__(
        self,
        *,
        max_daily_loss: float = 0.04,
        max_weekly_loss: float = 0.06,
        max_drawdown: float = 0.12,
        emergency_policy: EmergencyPolicy = EmergencyPolicy.HOLD,
    ):
        self.max_daily_loss = float(max_daily_loss)
        self.max_weekly_loss = float(max_weekly_loss)
        self.max_drawdown = float(max_drawdown)
        self.emergency_policy = emergency_policy

    def evaluate(self, *, daily_loss: float, weekly_loss: float, drawdown: float) -> bool:
        if daily_loss <= -self.max_daily_loss:
            return True
        if weekly_loss <= -self.max_weekly_loss:
            return True
        if drawdown >= self.max_drawdown:
            return True
        return False

    def state(self, *, daily_loss: float, weekly_loss: float, drawdown: float) -> KillSwitchState:
        triggered = self.evaluate(daily_loss=daily_loss, weekly_loss=weekly_loss, drawdown=drawdown)
        if not triggered:
            return KillSwitchState(False, "all risk limits are within bounds")
        reason = []
        if daily_loss <= -self.max_daily_loss:
            reason.append("daily loss limit")
        if weekly_loss <= -self.max_weekly_loss:
            reason.append("weekly loss limit")
        if drawdown >= self.max_drawdown:
            reason.append("drawdown limit")
        return KillSwitchState(True, "; ".join(reason))
