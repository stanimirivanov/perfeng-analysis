"""Deterministic descriptive statistics for complete observation series."""

import math
import statistics


def percentile(values: list[float | int], probability: float) -> float | int:
    """Return the linearly interpolated sample percentile (Hyndman-Fan type 7)."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def summarize(values: list[float | int]) -> dict[str, float | int]:
    """Summarize a non-empty complete series using population variability."""
    if not values:
        raise ValueError("Cannot summarize an empty observation series")
    mean = statistics.fmean(values)
    standard_deviation = statistics.pstdev(values, mu=mean)
    result: dict[str, float | int] = {
        "samples": len(values),
        "mean": mean,
        "median": statistics.median(values),
        "p90": percentile(values, 0.90),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "stddev": standard_deviation,
        "min": min(values),
        "max": max(values),
    }
    if mean > 0:
        result["cv"] = standard_deviation / mean
    return result
