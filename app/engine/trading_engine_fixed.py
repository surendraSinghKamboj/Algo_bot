import sys

import app.engine.trading_engine as _canonical

sys.modules[__name__] = _canonical

TradingEngine = _canonical.TradingEngine
__all__ = ['TradingEngine']
