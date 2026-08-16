from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SpreadType(str, Enum):
    BULL_CALL = "BULL_CALL"
    BEAR_PUT = "BEAR_PUT"
    CALL_DEBIT = "CALL_DEBIT"
    PUT_DEBIT = "PUT_DEBIT"
    PROTECTIVE_PUT = "PROTECTIVE_PUT"
    COLLAR = "COLLAR"


class OptionType(str, Enum):
    CALL = "CALL"
    PUT = "PUT"


@dataclass(frozen=True)
class SpreadDefinition:
    spread_type: SpreadType
    entry_price: float
    max_loss: float
    max_profit: float
    break_even: float
    risk_reward_ratio: float
    delta: float
    gamma: float
    theta: float
    vega: float
    iv: float
    expected_move: float
    distance_to_expiry: int
    bid_ask_spread: float
    liquidity: str
    margin_requirement: float
    risk_budget: float

    def is_acceptable(self) -> bool:
        if self.max_loss > self.risk_budget:
            return False
        if self.max_loss <= 0 or self.max_profit <= 0:
            return False
        if self.risk_reward_ratio < 1.0:
            return False
        if self.bid_ask_spread > 0.35:
            return False
        if self.liquidity.lower() not in {"good", "fair"}:
            return False
        if self.margin_requirement <= 0:
            return False
        if self.distance_to_expiry <= 0:
            return False
        return True
