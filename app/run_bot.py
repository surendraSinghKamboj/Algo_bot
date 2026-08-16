from __future__ import annotations

import logging
import signal
import sys
from app.config.settings import get_settings
from app.engine.trading_engine_fixed import TradingEngine
from app.engine.runner import Runner

log = logging.getLogger(__name__)


def main() -> int:
    settings = get_settings()
    mode = str(settings.trading_mode).upper()
    strategy_name = f"{settings.app_env.upper()}_STRATEGY" if False else "NIFTY_HEDGED_V1"
    capital = 500000

    print("# ====================================")
    print("ALGO BOT")
    print()
    print(f"Mode: {mode}")
    print("Broker: UPSTOX")
    print(f"Strategy: {strategy_name}")
    print(f"Capital: 9{capital}")
    print("Status: STARTING")

    engine = TradingEngine()
    runner = Runner(engine=engine)

    def _shutdown(signum, frame):
        log.info("Shutting down due to signal %s", signum)
        runner.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        runner.start()
        print("[INFO] Runner started. Press Ctrl+C to stop.")
        # Keep main thread alive
        signal.pause()
    except KeyboardInterrupt:
        print("Interrupted; shutting down")
        runner.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())