from __future__ import annotations

import numpy as np


def pair_correlation_bin_edges(
    bin_width_nm: float,
    maximum_nm: float,
) -> tuple[float, ...]:
    """Build stable g(r) bin edges including a possible final partial bin."""

    full_bin_count = int(np.floor(maximum_nm / bin_width_nm))
    edges = [float(index * bin_width_nm) for index in range(full_bin_count + 1)]
    if not np.isclose(edges[-1], maximum_nm, rtol=1e-12, atol=1e-12):
        edges.append(float(maximum_nm))
    else:
        edges[-1] = float(maximum_nm)
    return tuple(edges)
