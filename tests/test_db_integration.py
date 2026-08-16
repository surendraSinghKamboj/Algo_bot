import os
import pytest
from datetime import datetime, timezone
from decimal import Decimal

from app.data.models import MarketTick
from app.data import storage
from app.database.models import MarketTickRecord
from app.database.session import SessionLocal


pytestmark = pytest.mark.integration


def test_upsert_ticks_into_database():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set for integration test")

    session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        tick = MarketTick(instrument_key="TEST|TICK", timestamp=now, ltp=Decimal("123.45"), volume=10, open_interest=5, source="integration_test")
        count = storage.upsert_ticks(session, [tick])
        assert count >= 1

        # Verify persisted row exists
        row = session.query(MarketTickRecord).filter(MarketTickRecord.instrument_key == "TEST|TICK").order_by(MarketTickRecord.observed_at.desc()).first()
        assert row is not None
        assert float(row.ltp) == 123.45
    finally:
        session.close()
