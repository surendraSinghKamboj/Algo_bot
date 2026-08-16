from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from app.data.models import MarketTick
from app.data.streaming import TickGate, subscription_message


def test_subscription_is_binary_and_deduplicates_keys():
    message = subscription_message(["NSE_INDEX|Nifty 50", "NSE_INDEX|Nifty 50"], "full")
    assert json.loads(message)["data"]["instrumentKeys"] == ["NSE_INDEX|Nifty 50"]


def test_tick_gate_rejects_duplicates_and_stale_ticks():
    now = datetime.now(UTC)
    gate = TickGate(stale_after=timedelta(seconds=5))
    tick = MarketTick("NSE_INDEX|Nifty 50", now, Decimal("25000"))
    assert gate.accept(tick, now)
    assert not gate.accept(tick, now)
    assert not gate.accept(MarketTick("NSE_INDEX|Nifty 50", now - timedelta(seconds=6), Decimal("25000")), now)
