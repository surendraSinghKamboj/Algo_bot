from __future__ import annotations

import math


def compute_hedge_quantity(exposure_delta: float, hedge_delta: float, lot_size: int = 1) -> int:
    """Compute a hedge quantity (integer) to neutralize exposure_delta using an instrument with hedge_delta per unit.

    Args:
        exposure_delta: total portfolio delta exposure (positive means long delta needing shorting to neutralize)
        hedge_delta: per-unit delta of hedge instrument (signed)
        lot_size: integer lot size multiplier (default 1)

    Returns:
        quantity: integer number of contracts to trade (signed). Positive indicates buying hedge instrument, negative selling.
    """
    if hedge_delta == 0:
        raise ValueError("hedge_delta must be non-zero")
    raw_qty = -exposure_delta / hedge_delta
    # Round to nearest whole lot
    qty = int(math.copysign(max(0, int(abs(raw_qty) // lot_size) * lot_size), raw_qty))
    # If rounding led to zero but raw_qty magnitude >= half a lot, round up
    if qty == 0 and abs(raw_qty) >= 0.5 * lot_size:
        qty = int(math.copysign(lot_size, raw_qty))
    return qty
