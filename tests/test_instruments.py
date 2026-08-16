from app.data.instruments import normalize_instrument


def test_normalizes_current_instrument_master_shape():
    result = normalize_instrument({"instrument_key": "NSE_FO|123", "exchange_token": "123", "segment": "NSE_FO", "exchange": "NSE", "instrument_type": "CE", "trading_symbol": "NIFTY 25000 CE", "expiry": 1781879400000, "strike_price": 25000, "lot_size": 65, "minimum_lot": 65, "tick_size": 5, "weekly": True})
    assert result["instrument_key"] == "NSE_FO|123"
    assert result["lot_size"] == 65
    assert str(result["strike_price"]) == "25000"
