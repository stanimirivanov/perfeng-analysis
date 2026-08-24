"""k6 result normalizer.

Converts k6 JSON output to normalized test result format.
"""

from __future__ import annotations

from typing import Any, cast


class K6Normalizer:
    """Normalize k6 JSON output to standardized format."""

    # Mapping of k6 metric types to normalized types
    METRIC_TYPE_MAP: dict[str, str] = {
        "trend": "latency",
        "counter": "throughput",
        "rate": "error_rate",
        "gauge": "resource",
    }

    # Mapping of k6 metric names to normalized names
    METRIC_NAME_MAP: dict[str, str] = {
        "http_req_duration": "api.http.duration",
        "http_req_failed": "api.http.error_rate",
        "http_reqs": "api.http.throughput",
        "checkout_duration": "biz.checkout.duration",
        "search_duration": "biz.search.duration",
    }

    def normalize(
        self,
        k6_output: dict[str, Any],
        run_id: str,
        metric_names: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Normalize k6 output to standard format.

        Args:
            k6_output: Raw k6 JSON output.
            run_id: Performance run ID.
            metric_names: Optional list of metric names to include.
                         If None, all metrics are included.

        Returns:
            List of normalized test results.
        """
        results: list[dict[str, Any]] = []

        if "metrics" not in k6_output:
            return results

        for metric_name, metric_data in k6_output["metrics"].items():
            # Skip if metric not in filter list
            if metric_names and metric_name not in metric_names:
                continue

            normalized = self._normalize_metric(
                metric_name=metric_name,
                metric_data=cast(dict[str, Any], metric_data),
                run_id=run_id,
            )

            if normalized:
                results.append(normalized)

        return results

    def _normalize_metric(
        self,
        metric_name: str,
        metric_data: dict[str, Any],
        run_id: str,
    ) -> dict[str, Any] | None:
        """Normalize a single k6 metric.

        Args:
            metric_name: Original k6 metric name.
            metric_data: k6 metric data.
            run_id: Performance run ID.

        Returns:
            Normalized metric result or None if unsupported.
        """
        metric_type = metric_data.get("type", "")
        if metric_type not in self.METRIC_TYPE_MAP:
            return None

        # Map metric name
        normalized_name = self.METRIC_NAME_MAP.get(
            metric_name,
            f"api.{metric_name.replace('_', '.')}",
        )

        # Extract distribution data
        values = metric_data.get("values", {})

        # Determine direction
        direction = self._determine_direction(metric_name, metric_type)

        # Get sample count from values (not top level)
        sample_count = values.get("count", 0)

        # Build normalized result
        result: dict[str, Any] = {
            "schemaVersion": 1,
            "runId": run_id,
            "metric": {
                "name": normalized_name,
                "direction": direction,
                "type": self.METRIC_TYPE_MAP[metric_type],
                "unit": self._determine_unit(metric_name, metric_type),
            },
            "distribution": {
                "samples": sample_count,
            },
        }

        # Add distribution values
        # k6 uses "avg" and "med" instead of "mean" and "median"
        if "avg" in values:
            result["distribution"]["mean"] = values["avg"]
        if "med" in values:
            result["distribution"]["median"] = values["med"]
        if "p(90)" in values:
            result["distribution"]["p90"] = values["p(90)"]
        if "p(95)" in values:
            result["distribution"]["p95"] = values["p(95)"]
        if "p(99)" in values:
            result["distribution"]["p99"] = values["p(99)"]
        if "stddev" in values:
            result["distribution"]["stddev"] = values["stddev"]
        if "min" in values:
            result["distribution"]["min"] = values["min"]
        if "max" in values:
            result["distribution"]["max"] = values["max"]

        # Calculate CV if mean and stddev available
        mean = values.get("avg", values.get("mean", 0))
        stddev = values.get("stddev", 0)
        if mean and stddev and mean > 0:
            result["distribution"]["cv"] = stddev / mean

        # Add threshold results if available
        if "thresholds" in metric_data:
            thresholds = metric_data["thresholds"]
            slo_results: dict[str, Any] = {}

            for threshold_name, threshold_data in thresholds.items():
                slo_results[threshold_name] = {
                    "passed": threshold_data.get("ok", False),
                    "threshold": threshold_name,
                }

            if slo_results:
                result["thresholds"] = {"slo": slo_results}

        return result

    def _determine_direction(self, metric_name: str, metric_type: str) -> str:
        """Determine metric direction (lower-is-better or higher-is-better).

        Args:
            metric_name: Original metric name.
            metric_type: k6 metric type.

        Returns:
            Direction string.
        """
        # Metrics that are higher-is-better
        higher_is_better = [
            "http_reqs",
            "throughput",
            "successful_transactions",
            "iterations",
            "checks",
        ]

        # Metrics that are lower-is-better
        lower_is_better = [
            "http_req_duration",
            "http_req_failed",
            "error_rate",
            "failed_transactions",
            "checkout_duration",
            "search_duration",
        ]

        if metric_name in higher_is_better:
            return "higher-is-better"
        elif metric_name in lower_is_better:
            return "lower-is-better"

        # Default based on type
        if metric_type == "rate":
            return "lower-is-better"
        elif metric_type == "counter":
            return "higher-is-better"
        else:
            return "lower-is-better"

    def _determine_unit(self, metric_name: str, metric_type: str) -> str | None:
        """Determine metric unit.

        Args:
            metric_name: Original metric name.
            metric_type: k6 metric type.

        Returns:
            Unit string or None.
        """
        # Duration metrics
        if "duration" in metric_name or metric_name in ["http_req_duration"]:
            return "ms"

        # Error rate metrics
        if metric_type == "rate" or "failed" in metric_name:
            return "percent"

        # Throughput metrics
        if metric_name in ["http_reqs", "iterations"]:
            return "count"

        # Default
        return None
