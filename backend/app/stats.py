"""Tiny statistics helpers (no numpy needed, easy to read and test)."""

from __future__ import annotations

import math
from typing import Optional, Sequence


def present(values: Sequence[Optional[float]]) -> list[float]:
    """Drop missing hours (None)."""
    return [v for v in values if v is not None]


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def percentile(values: Sequence[float], p: float) -> float:
    """Nearest-rank percentile, p in [0, 100]. Same method as most textbooks."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[rank - 1]
