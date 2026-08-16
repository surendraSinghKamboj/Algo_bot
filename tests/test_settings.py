import pytest
from pydantic import ValidationError
from app.config.settings import Settings, TradingMode


def test_paper_is_default():
    assert Settings().trading_mode is TradingMode.PAPER


def test_live_requires_explicit_confirmation():
    with pytest.raises(ValidationError):
        Settings(trading_mode="LIVE")
    assert Settings(trading_mode="LIVE", live_trading_confirmation="I_UNDERSTAND_LIVE_TRADING").trading_mode is TradingMode.LIVE
