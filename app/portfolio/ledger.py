from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PositionEntry:
    instrument_key: str
    quantity: int = 0
    average_price: float = 0.0
    unrealized_pnl: float = 0.0
    last_market_price: float = 0.0


class PositionLedger:
    """Local position and P&L tracking for paper trading and reconciliation."""

    def __init__(self, starting_cash: float = 500000.0):
        self.starting_cash = float(starting_cash)
        self.cash = float(starting_cash)
        self.positions: dict[str, PositionEntry] = {}
        self.trade_history: list[dict] = []
        self.realized_pnl_total: float = 0.0

    def apply_fill(self, *, instrument_key: str, quantity: int, price: float, side: str) -> None:
        if quantity == 0:
            return
        side = side.upper()
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")

        qty = int(quantity)
        signed_qty = qty if side == "BUY" else -qty
        position = self.positions.setdefault(instrument_key, PositionEntry(instrument_key=instrument_key))
        current_qty = int(position.quantity)
        current_avg = float(position.average_price)

        if signed_qty > 0:
            if current_qty >= 0:
                new_qty = current_qty + signed_qty
                total_cost = current_avg * max(current_qty, 0) + price * signed_qty
                position.quantity = new_qty
                position.average_price = total_cost / new_qty if new_qty else 0.0
            else:
                close_qty = min(abs(current_qty), signed_qty)
                self.realized_pnl_total += (abs(current_avg) - price) * close_qty if current_avg > 0 else 0.0
                remaining_short = abs(current_qty) - close_qty
                if remaining_short > 0:
                    position.quantity = -remaining_short
                    position.average_price = current_avg
                else:
                    position.quantity = signed_qty - close_qty
                    position.average_price = price if position.quantity > 0 else 0.0
                if signed_qty > close_qty:
                    extra = signed_qty - close_qty
                    if extra > 0:
                        position.quantity += extra
                        position.average_price = price
            self.cash -= price * signed_qty
        else:
            sell_qty = abs(signed_qty)
            if current_qty <= 0:
                total_cost = abs(current_qty) * current_avg + price * sell_qty if current_avg > 0 else price * sell_qty
                new_qty = current_qty - sell_qty
                position.quantity = new_qty
                position.average_price = total_cost / max(abs(new_qty), 1) if new_qty else 0.0
            else:
                close_qty = min(current_qty, sell_qty)
                self.realized_pnl_total += (price - current_avg) * close_qty if current_avg > 0 else 0.0
                remaining_long = current_qty - close_qty
                if remaining_long > 0:
                    position.quantity = remaining_long
                    position.average_price = current_avg
                else:
                    position.quantity = -(sell_qty - close_qty)
                    position.average_price = price if position.quantity < 0 else 0.0
                if sell_qty > close_qty:
                    extra = sell_qty - close_qty
                    position.quantity -= extra
                    position.average_price = price
            self.cash += price * sell_qty

        position.last_market_price = price
        if position.quantity == 0:
            position.average_price = 0.0
        self.positions[instrument_key] = position

        self.trade_history.append({
            "instrument_key": instrument_key,
            "quantity": qty,
            "price": price,
            "side": side,
            "realized_pnl": self.realized_pnl_total,
        })

    def portfolio_value(self, mark_prices: dict[str, float] | None = None) -> float:
        total = self.cash
        for position in self.positions.values():
            if position.quantity == 0:
                continue
            mark = float(mark_prices.get(position.instrument_key, position.last_market_price or position.average_price)) if mark_prices else position.last_market_price or position.average_price
            total += position.quantity * mark
        return total

    def unrealized_pnl(self, mark_prices: dict[str, float] | None = None) -> float:
        total = 0.0
        for position in self.positions.values():
            if position.quantity == 0:
                continue
            mark = float(mark_prices.get(position.instrument_key, position.last_market_price or position.average_price)) if mark_prices else position.last_market_price or position.average_price
            total += (mark - position.average_price) * position.quantity if position.average_price else 0.0
        return total

    def realized_pnl(self) -> float:
        return float(self.realized_pnl_total)

    def mark_to_market_pnl(self, mark_prices: dict[str, float] | None = None) -> float:
        return self.unrealized_pnl(mark_prices=mark_prices) + self.realized_pnl()

    def net_pnl(self, mark_prices: dict[str, float] | None = None) -> float:
        return self.portfolio_value(mark_prices=mark_prices) - self.starting_cash
