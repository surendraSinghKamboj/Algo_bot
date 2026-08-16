from datetime import UTC, datetime
from decimal import Decimal

from app.broker.runtime import build_runtime_feed_config, route_tick_to_market_state
from app.config.settings import Settings, TradingMode
from app.data.models import MarketTick
from app.market.state import MarketState


def test_runtime_uses_live_upstox_feed_when_token_present(monkeypatch):
    monkeypatch.setenv('UPSTOX_ACCESS_TOKEN', 'real-token')
    settings = Settings(upstox_access_token='real-token', trading_mode=TradingMode.PAPER)
    config = build_runtime_feed_config(settings)

    assert config.token_present is True
    assert config.mode == 'PAPER'
    assert 'NSE_INDEX|Nifty 50' in config.instrument_keys
    assert 'NSE_INDEX|India VIX' in config.instrument_keys


def test_market_state_routes_nifty_and_vix_ticks_separately():
    state = MarketState()
    nifty = MarketTick(
        instrument_key='NSE_INDEX|Nifty 50',
        timestamp=datetime.now(UTC),
        ltp=Decimal('24500.50'),
        volume=100,
        source='upstox_feed',
    )
    vix = MarketTick(
        instrument_key='NSE_INDEX|India VIX',
        timestamp=datetime.now(UTC),
        ltp=Decimal('15.25'),
        volume=50,
        source='upstox_feed',
    )

    route_tick_to_market_state(state, nifty)
    route_tick_to_market_state(state, vix)
    snapshot = state.get_snapshot()

    assert snapshot['NIFTY'] == 24500.5
    assert snapshot['INDIA_VIX'] == 15.25
    assert snapshot['availability']['NIFTY'] is True
    assert snapshot['availability']['INDIA_VIX'] is True
