from __future__ import annotations

from typing import Dict, Tuple


def compute_correlated_exposure(positions: Dict[str, float], correlations: Dict[Tuple[str, str], float]) -> float:
    """Compute a simple correlated exposure metric given positions and pairwise correlations.

    positions: mapping instrument_key -> exposure (signed numeric)
    correlations: mapping (a,b) -> correlation coefficient in [-1,1]. If (a,b) not present, assumes 0.

    Returns a scalar exposure estimate: sum_i sum_j positions[i] * positions[j] * corr(i,j)
    """
    keys = list(positions.keys())
    total = 0.0
    for i in range(len(keys)):
        for j in range(len(keys)):
            a, b = keys[i], keys[j]
            corr = correlations.get((a, b)) or correlations.get((b, a)) or 0.0
            total += positions[a] * positions[b] * corr
    return float(total)
