from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class OptionGreeks:
    option_type: str
    delta: float
    gamma: float
    theta: float
    vega: float


@dataclass(frozen=True)
class OptionPayoff:
    trade_type: str
    max_loss: float
    max_profit: float
    break_even: float


def calculate_option_greeks(*, option_type: str, spot: float, strike: float, time_to_expiry: float, risk_free_rate: float, volatility: float) -> OptionGreeks:
    if time_to_expiry <= 0:
        raise ValueError("time_to_expiry must be positive")
    moneyness = (spot - strike) / strike
    sign = 1.0 if option_type.upper() == "CALL" else -1.0
    delta = sign * (0.5 + 0.5 * math.tanh(moneyness * 10.0))
    gamma = 0.15 / (spot * math.sqrt(time_to_expiry + 1e-9))
    theta = -0.02 * (1.0 / math.sqrt(time_to_expiry + 1e-9))
    vega = 0.08 * (1.0 + volatility * 10.0)
    return OptionGreeks(option_type=option_type.upper(), delta=delta, gamma=gamma, theta=theta, vega=vega)


def payoff_curve(*, option_type: str, strike: float, premium: float, price_range: list[float]) -> list[dict[str, float]]:
    results = []
    for price in price_range:
        if option_type.upper() == "CALL":
            intrinsic = max(price - strike, 0.0)
        elif option_type.upper() == "PUT":
            intrinsic = max(strike - price, 0.0)
        else:
            raise ValueError("option_type must be CALL or PUT")
        payoff = intrinsic - premium
        results.append({"price": float(price), "payoff": float(payoff), "profit_loss": float(payoff)})
    return results
