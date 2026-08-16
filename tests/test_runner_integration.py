import time
from datetime import datetime
from decimal import Decimal

from app.engine.trading_engine_fixed import TradingEngine
from app.engine.runner import Runner, MockStreamer
from app.broker.upstox_feed import ticks_from_v3_message


def test_runner_with_mock_feed():
    engine = TradingEngine()

    # Provide a custom streamer factory that returns a MockStreamer instance
    def streamer_factory():
        return MockStreamer()

    runner = Runner(engine=engine, streamer_factory=streamer_factory)
    runner.start()

    # Wait briefly for feed to start
    time.sleep(0.5)

    # craft a V3-style message that ticks_from_v3_message will accept
    now_ms = int(datetime.utcnow().timestamp() * 1000)
    message = {
        "type": "liveFeed",
        "currentTs": now_ms,
        "feeds": {
            "NSE_INDEX|Nifty 50": {
                "ltpc": {"ltp": 24000.0, "ltt": now_ms, "ltq": 100}
            }
        }
    }

    # Emit the message via the mock streamer
    # Find the internal mock streamer instance
    mock_feed = runner._feed
    # depending on implementation, _feed may be wrapper exposing _streamer
    streamer = getattr(mock_feed, "_streamer", None)
    assert streamer is not None

    # Send message
    streamer.emit_message(message)

    # Allow some processing time
    time.sleep(0.5)

    # Check that engine produced orders in paper engine
    assert len(engine.paper_engine.orders) >= 1

    runner.stop()
