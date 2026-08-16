from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass
class MultiLegPaperOrder:
    strategy: str
    trade_id: str
    legs: List[PaperLeg]

    def mark_all_filled(self) -> None:
        for l in self.legs:
            l.mark_filled()

    def net_premium(self) -> float:
        # debit = positive cost to open (buys positive), credit = negative cost (sells reduce cost)
        net = 0.0
        for l in self.legs:
            side = l.side.upper()
            if side == "BUY":
                net += float(l.entry_price) * l.filled_quantity
            elif side == "SELL":
                net -= float(l.entry_price) * l.filled_quantity
        return net


@dataclass
class PaperPosition:
    instrument_key: str
    quantity: int = 0
    average_price: float = 0.0
    unrealized_pnl: float = 0.0

    def apply_trade(self, order: PaperOrder) -> None:
        if order.action.upper() == "BUY":
            total_cost = self.average_price * self.quantity + order.entry_price * order.filled_quantity
            new_quantity = self.quantity + order.filled_quantity
            self.average_price = total_cost / new_quantity if new_quantity else 0.0
            self.quantity = new_quantity
        elif order.action.upper() == "SELL":
            self.quantity = max(0, self.quantity - order.filled_quantity)
            if self.quantity == 0:
                self.average_price = 0.0


class PaperExecutionEngine:
    """Virtual execution engine that simulates fills without sending broker orders.

    Supports multi-leg orders (spreads) and records legs as linked to a single trade id.
    """

    def __init__(self, trading_mode: str = "PAPER"):
        self.trading_mode = trading_mode.upper()
        self.orders: List[PaperOrder] = []
        self.multi_orders: List[MultiLegPaperOrder] = []
        self.positions: Dict[str, PaperPosition] = {}

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
        return order

    def submit_multi_leg(self, strategy: str, trade_id: str, legs: List[PaperLeg]) -> MultiLegPaperOrder:
        if self.trading_mode != "PAPER":
            raise RuntimeError("Live multi-leg execution is disabled unless trading_mode==PAPER")
        m = MultiLegPaperOrder(strategy=strategy, trade_id=trade_id, legs=legs)
        # simulate immediate fills for all legs
        m.mark_all_filled()
        self.multi_orders.append(m)
        # apply leg-by-leg to positions
        for leg in m.legs:
            side = leg.side.upper()
            # create a PaperOrder shim for ledger compatibility
            shim = PaperOrder(strategy=strategy, action=leg.side, instrument_key=leg.instrument_key, quantity=leg.filled_quantity, entry_price=leg.average_fill_price or leg.entry_price, stop_loss=0.0, target=0.0,)
            position = self.positions.setdefault(leg.instrument_key, PaperPosition(leg.instrument_key))
            position.apply_trade(shim)
        return m
