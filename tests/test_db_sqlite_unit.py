from datetime import datetime, timezone, date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import MarketTickRecord
from app.data.models import MarketTick
from app.data import storage


def make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    # create only the required table for ticks using a sqlite-friendly schema (INTEGER PRIMARY KEY autoincrement)
    with engine.connect() as conn:
        conn.exec_driver_sql("""
        CREATE TABLE market_ticks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instrument_key TEXT NOT NULL,
            observed_at DATETIME NOT NULL,
            ltp NUMERIC NOT NULL,
            volume INTEGER,
            open_interest INTEGER,
            source TEXT NOT NULL,
            received_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()
    Session = sessionmaker(bind=engine)
    return Session(), engine


def test_upsert_ticks_sqlite():
    session, engine = make_session()
    now = datetime.now(timezone.utc)
    tick = MarketTick(instrument_key="TEST|TICK", timestamp=now, ltp=Decimal("10.5"), volume=1, open_interest=0, source="test")
    count = storage.upsert_ticks(session, [tick])
    assert count == 1
    row = session.query(MarketTickRecord).filter(MarketTickRecord.instrument_key == "TEST|TICK").first()
    assert row is not None
    assert float(row.ltp) == 10.5
