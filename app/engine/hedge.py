from __future__ import annotations

import math


def compute_hedge_quantity(exposure_delta: float, hedge_delta: float, lot_size: int = 1) -> int:
    """Compute a hedge quantity (integer) to neutralize exposure_delta using an instrument with hedge_delta per unit."""
    if hedge_delta == 0:
        raise ValueError("hedge_delta must be non-zero")
    if lot_size <= 0:
        raise ValueError("lot_size must be positive")

    raw_qty = -exposure_delta / hedge_delta
    rounded_lots = round(abs(raw_qty) / lot_size)
    quantity = int(rounded_lots * lot_size)
    if abs(raw_qty) > 0 and quantity == 0:
        quantity = lot_size
    if raw_qty < 0:
        quantity *= -1
    return quantity
