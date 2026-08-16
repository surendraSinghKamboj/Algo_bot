from __future__ import annotations

import logging
import signal
import sys
import threading
import time

from app.config.settings import get_settings
from app.engine.runner import Runner
from app.engine.trading_engine import TradingEngine

log = logging.getLogger(__name__)


def main() -> int:
    settings = get_settings()
    mode = str(settings.trading_mode).upper()
    strategy_name = 'NIFTY_HEDGED_V1'
    capital = 500000

    print('# ====================================')
    print('ALGO BOT')
    print()
    print(f'Mode: {mode}')
    print('Broker: UPSTOX')
    print(f'Strategy: {strategy_name}')
    print(f'Capital: Rs {capital:,.0f}')
    print('Status: STARTING')

    engine = TradingEngine()
    runner = Runner(engine=engine)
    shutdown_event = threading.Event()

    def _shutdown(signum, frame):
        log.info('Shutting down due to signal %s', signum)
        shutdown_event.set()
        runner.stop()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        runner.start()
        print('[INFO] Runner started. Press Ctrl+C to stop.')
        while not shutdown_event.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print('Interrupted; shutting down')
        runner.stop()
        shutdown_event.set()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
