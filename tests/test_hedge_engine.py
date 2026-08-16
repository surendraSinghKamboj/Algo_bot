from app.engine.hedge import compute_hedge_quantity


def test_compute_hedge_simple():
    # Exposure +100 delta, hedge instrument delta per unit is -0.5 (e.g., shorting a put?)
    qty = compute_hedge_quantity(exposure_delta=100.0, hedge_delta=-0.5, lot_size=1)
    # Need to buy 200 units of hedge (because -100 / -0.5 = 200 positive)
    assert qty == 200


def test_compute_hedge_with_lot_size_rounded():
    qty = compute_hedge_quantity(exposure_delta=123.0, hedge_delta=0.3, lot_size=25)
    # raw qty = -410, rounded to nearest lot -> magnitude 400 or 425 depending; ensure integer and multiple of lot_size
    assert isinstance(qty, int)
    assert abs(qty) % 25 == 0


def test_compute_hedge_zero_delta_raises():
    import pytest
    with pytest.raises(ValueError):
        compute_hedge_quantity(10.0, 0.0)
