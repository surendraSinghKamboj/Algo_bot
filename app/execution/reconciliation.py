from __future__ import annotations

from dataclasses import dataclass

from app.portfolio.ledger import PositionLedger


@dataclass(frozen=True)
class BrokerState:
    positions: dict[str, int]
    cash: float


@dataclass(frozen=True)
class ReconciliationMismatch:
    instrument_key: str
    local_quantity: int
    broker_quantity: int
    message: str


class ReconciliationEngine:
    """Flags mismatches between local paper state and broker state before trading continues."""

    def compare(self, local: PositionLedger, broker: BrokerState) -> ReconciliationMismatch | None:
        for instrument_key, position in local.positions.items():
            broker_qty = broker.positions.get(instrument_key, 0)
            if position.quantity != broker_qty:
                return ReconciliationMismatch(
                    instrument_key=instrument_key,
                    local_quantity=position.quantity,
                    broker_quantity=broker_qty,
                    message="position mismatch between local ledger and broker state",
                )
        return None
