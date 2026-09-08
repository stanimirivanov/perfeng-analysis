"""Normalization of semantic Playwright duration measurements."""

from collections import defaultdict
from datetime import datetime
from typing import Any

from .distribution import summarize
from .validation import validate


class PlaywrightNormalizer:
    """Normalize validated Playwright v2 durations without inferring other semantics."""

    def normalize(
        self,
        document: dict[str, Any],
        metric_names: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        validate("playwright-measurements/v2/playwright-measurements.schema.json", document)
        self._check_times(document)

        grouped: dict[str, dict[int, float | int]] = defaultdict(dict)
        for measurement in document["measurements"]:
            name = measurement["name"]
            iteration = measurement["iteration"]
            if iteration in grouped[name]:
                raise ValueError(f"Duplicate iteration for metric: {name}")
            grouped[name][iteration] = measurement["durationMs"]

        names = list(grouped) if metric_names is None else metric_names
        if not names or len(names) != len(set(names)):
            raise ValueError("Metric selection must be non-empty and unique")
        if any(name not in grouped for name in names):
            raise ValueError("Missing selected metric")

        expected_iterations = set(range(1, document["scenario"]["measurementIterations"] + 1))
        results = []
        for name in names:
            if set(grouped[name]) != expected_iterations:
                raise ValueError(f"Metric does not cover every measurement iteration: {name}")
            values = [grouped[name][iteration] for iteration in sorted(grouped[name])]
            result = {
                "schemaVersion": 2,
                "runId": document["runId"],
                "metric": {
                    "name": name,
                    "type": "latency",
                    "unit": "ms",
                    "direction": "lower-is-better",
                },
                "distribution": summarize(values),
            }
            validate("result/v2/test-result.schema.json", result)
            results.append(result)
        return results

    @staticmethod
    def _check_times(document: dict[str, Any]) -> None:
        window = document["measurementWindow"]
        start = datetime.fromisoformat(window["start"])
        end = datetime.fromisoformat(window["end"])
        created = datetime.fromisoformat(document["createdAt"])
        if start >= end or created < end:
            raise ValueError("Invalid Playwright measurement window or creation time")


def check_playwright_manifest(document: dict[str, Any], manifest: dict[str, Any]) -> None:
    """Require the measurement document to describe the manifest's exact run and window."""
    for field in ("runId", "testId", "measurementWindow"):
        if document[field] != manifest[field]:
            raise ValueError(f"Playwright measurements do not match manifest {field}")
    for field in ("id", "version", "sha256"):
        if document["workload"][field] != manifest["workload"][field]:
            raise ValueError(f"Playwright measurements do not match manifest workload {field}")

    if datetime.fromisoformat(document["createdAt"]) > datetime.fromisoformat(
        manifest["createdAt"]
    ):
        raise ValueError("Playwright measurements postdate the raw manifest")
