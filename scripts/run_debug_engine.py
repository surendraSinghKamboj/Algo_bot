from datetime import datetime, timezone
from decimal import Decimal
from app.engine.trading_engine_fixed import TradingEngine
from app.data.models import MarketTick

engine = TradingEngine()
print('paper_engine id', id(engine.paper_engine))
print('pipeline uses paper_engine id', id(engine.pipeline.paper_engine) if hasattr(engine.pipeline, 'paper_engine') else None)

tick = MarketTick(instrument_key='NSE_INDEX|Nifty 50', timestamp=datetime.now(timezone.utc), ltp=Decimal('24000.0'))
order = engine.handle_tick(tick)
print('order', order)
print('paper_engine.orders', engine.paper_engine.orders)
print('ledger.positions', engine.ledger.positions)
print('ledger.cash', engine.ledger.cash)
print('ledger.trade_history', engine.ledger.trade_history)
