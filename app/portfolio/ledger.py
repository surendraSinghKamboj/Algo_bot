from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PositionEntry:
    instrument_key: str
    quantity: int = 0
    average_price: float = 0.0
    unrealized_pnl: float = 0.0


class PositionLedger:
    """Local position and P&L tracking for paper trading and reconciliation."""

    def __init__(self, starting_cash: float = 500000.0):
        self.starting_cash = float(starting_cash)
        self.cash = float(starting_cash)
        self.positions: dict[str, PositionEntry] = {}
        self.trade_history: list[dict] = []

    def apply_fill(self, *, instrument_key: str, quantity: int, price: float, side: str) -> None:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        side = side.upper()
        position = self.positions.setdefault(instrument_key, PositionEntry(instrument_key=instrument_key))
        if side == "BUY":
            total_cost = position.average_price * position.quantity + price * quantity
            new_quantity = position.quantity + quantity
            position.average_price = total_cost / new_quantity if new_quantity else 0.0
            position.quantity = new_quantity
            self.cash -= price * quantity
        elif side == "SELL":
            position.quantity = max(0, position.quantity - quantity)
            if position.quantity == 0:
                position.average_price = 0.0
            self.cash += price * quantity
        else:
            raise ValueError("side must be BUY or SELL")

        self.trade_history.append({
            "instrument_key": instrument_key,
            "quantity": quantity,
            "price": price,
            "side": side,
        })

    def portfolio_value(self) -> float:
        total = self.cash
        for position in self.positions.values():
            total += position.quantity * position.average_price
        return total

    def net_pnl(self) -> float:
        return self.portfolio_value() - self.starting_cash
