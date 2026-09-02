"""Explicit metric mappings adapted from the prototype k6 normalizer."""

import math
from typing import Any

from .validation import validate

# Raw name -> normalized name, native type, semantic type, unit, direction.
METRICS = {
    "http_req_duration": ("api.http.duration", "trend", "latency", "ms", "lower-is-better"),
    "http_req_failed": ("api.http.error_rate", "rate", "error_rate", "ratio", "lower-is-better"),
    "http_reqs": ("api.http.throughput", "counter", "throughput", "req/s", "higher-is-better"),
    "checkout_duration": ("biz.checkout.duration", "trend", "latency", "ms", "lower-is-better"),
    "biz_checkout_duration": ("biz.checkout.duration", "trend", "latency", "ms", "lower-is-better"),
    "search_duration": ("biz.search.duration", "trend", "latency", "ms", "lower-is-better"),
    "biz_search_duration": ("biz.search.duration", "trend", "latency", "ms", "lower-is-better"),
    "biz_account_operation_duration": (
        "biz.account.operation.duration",
        "trend",
        "latency",
        "ms",
        "lower-is-better",
    ),
    "biz_transaction_error_rate": (
        "biz.transaction.error_rate",
        "rate",
        "error_rate",
        "ratio",
        "lower-is-better",
    ),
}
STATISTICS = {
    "avg": "mean",
    "med": "median",
    "p(90)": "p90",
    "p(95)": "p95",
    "p(99)": "p99",
    "stddev": "stddev",
    "min": "min",
    "max": "max",
}


def number(value: Any) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Statistic must be numeric or null")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite or value < 0:
        raise ValueError("Statistic must be finite and non-negative")
    return value


class K6Normalizer:
    """Normalize allowlisted metrics; never infer semantics for unknown names."""

    def normalize(
        self,
        output: dict[str, Any],
        run_id: str,
        metric_names: list[str] | None = None,
        *,
        layout: str = "typed",
    ) -> list[dict[str, Any]]:
        if layout not in {"typed", "legacy-export"}:
            raise ValueError("Unsupported summary layout")
        if not isinstance(output, dict) or not isinstance(output.get("metrics"), dict):
            raise ValueError("Expected a summary metrics object")
        metrics = output["metrics"]
        names = list(metrics) if metric_names is None else metric_names
        if len(names) != len(set(names)):
            raise ValueError("Duplicate metric selection")
        if metric_names is not None and any(
            name not in metrics or name not in METRICS for name in names
        ):
            raise ValueError("Missing or unsupported selected metric")
        results, identities = [], set()
        for name in names:
            if name not in METRICS:
                continue
            normalized_name, native_type, semantic_type, unit, direction = METRICS[name]
            if normalized_name in identities:
                raise ValueError("Metric aliases collide; select one explicitly")
            metric = metrics[name]
            if not isinstance(metric, dict):
                raise ValueError("Malformed metric")
            if layout == "typed":
                if metric.get("type") != native_type or not isinstance(metric.get("values"), dict):
                    raise ValueError("Unexpected metric type or values")
                values = metric["values"]
            else:
                if "values" in metric or "type" in metric:
                    raise ValueError("Mixed summary layouts")
                values = metric
            distribution: dict[str, Any] = {}
            if native_type == "trend":
                for source, target in STATISTICS.items():
                    if source in values:
                        distribution[target] = number(values[source])
                if "count" in values:
                    count = values["count"]
                    if count is not None and (
                        isinstance(count, bool) or not isinstance(count, int) or count <= 0
                    ):
                        raise ValueError("Known trend sample count must be a positive integer")
                    distribution["samples"] = count
                mean, stddev = distribution.get("mean"), distribution.get("stddev")
                if mean is not None and mean > 0 and stddev is not None:
                    distribution["cv"] = number(stddev / mean)
            else:
                key = "value" if layout == "legacy-export" and native_type == "rate" else "rate"
                if key in values:
                    distribution["mean"] = number(values[key])
                rate = distribution.get("mean")
                if native_type == "rate" and rate is not None and rate > 1:
                    raise ValueError("Rate fraction must be between zero and one")
                # Counter totals and rate pass/fail counters are not trend sample counts.
            if not any(
                value is not None for key, value in distribution.items() if key != "samples"
            ):
                raise ValueError("Metric has no available measurements")
            result = {
                "schemaVersion": 2,
                "runId": run_id,
                "metric": {
                    "name": normalized_name,
                    "type": semantic_type,
                    "unit": unit,
                    "direction": direction,
                },
                "distribution": distribution,
            }
            validate("result/v2/test-result.schema.json", result)
            results.append(result)
            identities.add(normalized_name)
        if not results:
            raise ValueError("No supported measurements selected")
        return results
