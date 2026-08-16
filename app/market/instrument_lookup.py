from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List

from sqlalchemy.orm import Session

from app.database.models import Instrument, MarketTickRecord


def nearest_expiry_for_underlying(session: Session, underlying_key: str) -> Optional[datetime]:
    # Find the nearest future expiry for instruments with the given underlying_key
    now = datetime.now(timezone.utc)
    q = session.query(Instrument).filter(Instrument.underlying_key == underlying_key, Instrument.expiry_at != None)
    q = q.order_by(Instrument.expiry_at)
    rows = q.all()
    for r in rows:
        if r.expiry_at and r.expiry_at >= now:
            return r.expiry_at
    return None


def resolve_option_by_strike(session: Session, underlying_key: str, expiry: datetime, strike: Decimal, right: str) -> Optional[Instrument]:
    # right should be 'CE' or 'PE'
    right = right.upper()
    # Query instruments matching underlying, expiry and strike and option type
    instr = (
        session.query(Instrument)
        .filter(
            Instrument.underlying_key == underlying_key,
            Instrument.expiry_at == expiry,
            Instrument.strike_price == strike,
        )
        .all()
    )
    # Prefer matching right in trading_symbol or instrument_type
    for r in instr:
        ts = (r.trading_symbol or "").upper()
        if right in ts or (r.instrument_type and right in r.instrument_type.upper()):
            return r
    # fallback to first match
    return instr[0] if instr else None


def get_latest_tick_for_instrument(session: Session, instrument_key: str) -> Optional[MarketTickRecord]:
    return (
        session.query(MarketTickRecord)
        .filter(MarketTickRecord.instrument_key == instrument_key)
        .order_by(MarketTickRecord.observed_at.desc())
        .limit(1)
        .first()
    )


def atm_strike_from_spot(spot: float, strike_step: int = 50) -> Decimal:
    # Round to nearest strike step (default 50 for NIFTY)
    s = int(round(spot / strike_step) * strike_step)
    return Decimal(s)


def candidate_strikes(spot: float, width: int = 200, steps: int = 2, step_size: int = 50) -> List[Decimal]:
    atm = int(round(spot / step_size) * step_size)
    strikes = []
    # create symmetric strikes around ATM using width and steps
    for i in range(-steps, steps + 1):
        strikes.append(Decimal(atm + i * step_size))
    # unique and sorted
    strikes = sorted(list(dict.fromkeys(strikes)))
    return strikes
