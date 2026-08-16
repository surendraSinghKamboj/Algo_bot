from app.engine.cross_asset import compute_correlated_exposure


def test_correlated_exposure_simple():
    positions = {"A": 100.0, "B": 50.0}
    correlations = {("A", "B"): 0.5}
    # exposure = 100*100*1.0 (corr A,A assumed 0) + 100*50*0.5 + 50*100*0.5 + 50*50*1.0*0 (self-corr not provided)
    # with only cross-term we get 100*50*0.5 + 50*100*0.5 = 5000
    result = compute_correlated_exposure(positions, correlations)
    assert result == 5000.0


def test_correlated_exposure_symmetry():
    positions = {"A": 10.0, "B": -10.0}
    correlations = {("A", "B"): -1.0}
    # exposure = 10 * -10 * -1 + -10 * 10 * -1 = 200
    result = compute_correlated_exposure(positions, correlations)
    assert result == 200.0
