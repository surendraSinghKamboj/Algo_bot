from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class PaperTradeDecision:
    strategy: str
    action: str
    instrument_key: str
    quantity: int
    entry_price: float
    stop_loss: float
    target: float


@dataclass
class PaperOrder:
    strategy: str
    action: str
    instrument_key: str
    quantity: int
    entry_price: float
    stop_loss: float
    target: float
    status: str = "SIMULATED"
    filled_quantity: int = 0
    average_fill_price: float | None = None

    def mark_filled(self) -> None:
        self.filled_quantity = self.quantity
        self.average_fill_price = self.entry_price


@dataclass
class PaperLeg:
    leg_id: str
    instrument_key: str
    side: str
    quantity: int
    entry_price: float
    filled_quantity: int = 0
    average_fill_price: float | None = None

    def mark_filled(self) -> None:
        self.filled_quantity = self.quantity
        self.average_fill_price = self.entry_price

    @property
    def signed_quantity(self) -> int:
        qty = int(self.quantity)
        if qty == 0:
            return 0
        return qty if self.side.upper() == "BUY" else -abs(qty)


@dataclass
class MultiLegPaperOrder:
    strategy: str
    trade_id: str
    legs: List[PaperLeg]
    strategy_id: str | None = None

    def mark_all_filled(self) -> None:
        for leg in self.legs:
            leg.mark_filled()

    def net_premium(self) -> float:
        net = 0.0
        for leg in self.legs:
            side = leg.side.upper()
            if side == "BUY":
                net += float(leg.entry_price) * abs(int(leg.filled_quantity or leg.quantity))
            elif side == "SELL":
                net -= float(leg.entry_price) * abs(int(leg.filled_quantity or leg.quantity))
        return net


@dataclass
class PaperPosition:
    instrument_key: str
    quantity: int = 0
    average_price: float = 0.0
    unrealized_pnl: float = 0.0

    def apply_trade(self, order: PaperOrder) -> None:
        action = str(getattr(order, 'action', '')).upper()
        qty = int(getattr(order, 'filled_quantity', getattr(order, 'quantity', 0)) or 0)
        if qty == 0:
            return
        if qty < 0:
            signed_qty = qty
        else:
            signed_qty = qty if action in {"BUY", "LONG"} else -qty

        if signed_qty > 0:
            if self.quantity >= 0:
                total_cost = self.average_price * max(self.quantity, 0) + order.entry_price * signed_qty
                new_qty = self.quantity + signed_qty
                self.quantity = new_qty
                self.average_price = total_cost / max(new_qty, 1) if new_qty else 0.0
            else:
                short_qty = abs(self.quantity)
                close_qty = min(short_qty, signed_qty)
                remaining_short = short_qty - close_qty
                if remaining_short > 0:
                    self.quantity = -remaining_short
                    self.average_price = max(0.0, self.average_price)
                else:
                    self.quantity = signed_qty - close_qty
                    self.average_price = order.entry_price if self.quantity > 0 else 0.0
        elif signed_qty < 0:
            if self.quantity <= 0:
                short_qty = abs(self.quantity)
                total_cost = self.average_price * max(short_qty, 0) + order.entry_price * abs(signed_qty)
                new_qty = self.quantity + signed_qty
                self.quantity = new_qty
                self.average_price = total_cost / max(abs(new_qty), 1) if new_qty else 0.0
            else:
                long_qty = self.quantity
                close_qty = min(long_qty, abs(signed_qty))
                remaining_long = long_qty - close_qty
                if remaining_long > 0:
                    self.quantity = remaining_long
                    self.average_price = max(0.0, self.average_price)
                else:
                    self.quantity = -(abs(signed_qty) - close_qty)
                    self.average_price = order.entry_price if self.quantity < 0 else 0.0


class PaperExecutionEngine:
    """Virtual execution engine that simulates fills without sending broker orders.

    Supports multi-leg orders (spreads) and records legs as linked to a single trade id.
    """

    def __init__(self, trading_mode: str = "PAPER", ledger=None):
        self.trading_mode = trading_mode.upper()
        self.orders: List[PaperOrder] = []
        self.multi_orders: List[MultiLegPaperOrder] = []
        self.positions: Dict[str, PaperPosition] = {}
        self.ledger = ledger

    def submit(self, decision: PaperTradeDecision) -> PaperOrder:
        if self.trading_mode != "PAPER":
            raise RuntimeError("Live trading is disabled by default; switch explicitly to LIVE before placing live orders.")

        order = PaperOrder(
            strategy=decision.strategy,
            action=decision.action,
            instrument_key=decision.instrument_key,
            quantity=decision.quantity,
            entry_price=decision.entry_price,
            stop_loss=decision.stop_loss,
            target=decision.target,
        )
        order.mark_filled()
        self.orders.append(order)

        position = self.positions.setdefault(decision.instrument_key, PaperPosition(decision.instrument_key))
        position.apply_trade(order)
        if self.ledger is not None:
            side = (decision.action or '').upper()
            if 'BUY' in side or side in {'LONG', 'BULLISH'}:
                side = 'BUY'
            elif 'SELL' in side or side in {'SHORT', 'BEARISH'}:
                side = 'SELL'
            elif side == 'HEDGE':
                side = 'BUY'
            else:
                side = 'BUY' if 'LONG' in side else 'SELL'
            self.ledger.apply_fill(
                instrument_key=decision.instrument_key,
                quantity=order.filled_quantity,
                price=order.average_fill_price or order.entry_price,
                side=side,
            )
        return order

    def submit_multi_leg(self, strategy: str, trade_id: str, legs: List[PaperLeg], strategy_id: str | None = None) -> MultiLegPaperOrder:
        if self.trading_mode != "PAPER":
            raise RuntimeError("Live multi-leg execution is disabled unless trading_mode==PAPER")
        multi = MultiLegPaperOrder(strategy=strategy, trade_id=trade_id, legs=legs, strategy_id=strategy_id or strategy)
        multi.mark_all_filled()
        self.multi_orders.append(multi)
        for leg in multi.legs:
            qty = int(leg.filled_quantity if leg.filled_quantity != 0 else leg.quantity)
            shim = PaperOrder(strategy=strategy, action=leg.side, instrument_key=leg.instrument_key, quantity=qty, entry_price=leg.average_fill_price or leg.entry_price, stop_loss=0.0, target=0.0)
            position = self.positions.setdefault(leg.instrument_key, PaperPosition(leg.instrument_key))
            position.apply_trade(shim)
            if self.ledger is not None:
                self.ledger.apply_fill(
                    instrument_key=leg.instrument_key,
                    quantity=qty,
                    price=leg.average_fill_price or leg.entry_price,
                    side=leg.side,
                )
        return multi
