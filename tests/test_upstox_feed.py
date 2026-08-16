from datetime import UTC, datetime
from decimal import Decimal
from app.broker.upstox_feed import UpstoxMarketFeed, ticks_from_v3_message


def test_parses_official_sdk_ltpc_message():
    ticks = ticks_from_v3_message({"type": "liveFeed", "currentTs": "1780000001000", "feeds": {"NSE_INDEX|Nifty 50": {"ltpc": {"ltp": 25001.5, "ltt": "1780000000000", "ltq": "25", "cp": 24900}}}})
    assert len(ticks) == 1
    assert ticks[0].ltp == Decimal("25001.5")
    assert ticks[0].volume == 25
    assert ticks[0].timestamp == datetime.fromtimestamp(1780000000, UTC)


def test_parses_full_and_option_message_variants():
    message = {"type": "liveFeed", "currentTs": "1780000001000", "feeds": {"NSE_FO|1": {"fullFeed": {"marketFF": {"ltpc": {"ltp": 100, "ltt": "1780000000000", "ltq": "50"}, "oi": 1000}}}, "NSE_FO|2": {"firstLevelWithGreeks": {"ltpc": {"ltp": 20, "ltt": "1780000000000", "ltq": "75"}, "oi": 500}}}}
    ticks = ticks_from_v3_message(message)
    assert [tick.open_interest for tick in ticks] == [1000, 500]


class FakeStreamer:
    def __init__(self):
        self.callbacks = {}
        self.reconnect = None
        self.connected = False
    def on(self, event, listener): self.callbacks[event] = listener
    def auto_reconnect(self, enable, interval=1, retry_count=5): self.reconnect = (enable, interval, retry_count)
    def connect(self): self.connected = True; self.callbacks["open"]()
    def disconnect(self): self.callbacks["close"]()


def test_feed_adapter_connects_and_gates_ticks():
    fake, received = FakeStreamer(), []
    feed = UpstoxMarketFeed("token", ["NSE_INDEX|Nifty 50"], "ltpc", received.append, streamer_factory=lambda *_: fake)
    feed.start()
    fake.callbacks["message"]({"type": "liveFeed", "currentTs": str(int(datetime.now(UTC).timestamp() * 1000)), "feeds": {"NSE_INDEX|Nifty 50": {"ltpc": {"ltp": 25000, "ltt": str(int(datetime.now(UTC).timestamp() * 1000)), "ltq": "1"}}}})
    assert fake.reconnect == (True, 2, 5)
    assert feed.status.connected and len(received) == 1
    feed.stop()
    assert not feed.status.connected
