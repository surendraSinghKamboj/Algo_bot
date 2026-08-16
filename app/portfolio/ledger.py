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
            if position.quantity >= 0:
                total_cost = position.average_price * max(position.quantity, 0) + price * quantity
                new_quantity = position.quantity + quantity
                position.quantity = new_quantity
                position.average_price = total_cost / max(new_quantity, 1) if new_quantity else 0.0
                self.cash -= price * quantity
            else:
                short_qty = abs(position.quantity)
                close_qty = min(short_qty, quantity)
                remaining_short = short_qty - close_qty
                if remaining_short > 0:
                    position.quantity = -remaining_short
                    position.average_price = max(0.0, position.average_price)
                else:
                    position.quantity = quantity - close_qty
                    position.average_price = price if position.quantity > 0 else 0.0
                self.cash -= price * (quantity - close_qty)
        elif side == "SELL":
            if position.quantity <= 0:
                short_qty = abs(position.quantity)
                total_cost = position.average_price * max(short_qty, 0) + price * quantity
                new_quantity = position.quantity - quantity
                position.quantity = new_quantity
                position.average_price = total_cost / max(abs(new_quantity), 1) if new_quantity else 0.0
                self.cash += price * quantity
            else:
                long_qty = position.quantity
                close_qty = min(long_qty, quantity)
                remaining_long = long_qty - close_qty
                if remaining_long > 0:
                    position.quantity = remaining_long
                    position.average_price = max(0.0, position.average_price)
                else:
                    position.quantity = -(quantity - close_qty)
                    position.average_price = price if position.quantity < 0 else 0.0
                self.cash += price * quantity
        else:
            raise ValueError("side must be BUY or SELL")

        self.trade_history.append({
            "instrument_key": instrument_key,
            "quantity": quantity,
            "price": price,
            "side": side,
        })

    def portfolio_value(self, mark_prices: dict[str, float] | None = None) -> float:
        total = self.cash
        for position in self.positions.values():
            mark = float(mark_prices.get(position.instrument_key, position.average_price)) if mark_prices else position.average_price
            total += position.quantity * mark
        return total

    def unrealized_pnl(self, mark_prices: dict[str, float] | None = None) -> float:
        total = 0.0
        for position in self.positions.values():
            mark = float(mark_prices.get(position.instrument_key, position.average_price)) if mark_prices else position.average_price
            total += (mark - position.average_price) * position.quantity
        return total

    def net_pnl(self, mark_prices: dict[str, float] | None = None) -> float:
        return self.portfolio_value(mark_prices=mark_prices) - self.starting_cash
