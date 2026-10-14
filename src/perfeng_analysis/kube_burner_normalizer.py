"""Normalization of kube-burner pod-startup observations."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from .distribution import summarize
from .validation import validate

# Normalized metric name -> kube-burner observation field.
METRICS = {
    "k8s.pod.scheduling.duration": "schedulingLatency",
    "k8s.pod.initialized.duration": "initializedLatency",
    "k8s.pod.containers_ready.duration": "containersReadyLatency",
    "k8s.pod.ready.duration": "podReadyLatency",
    "k8s.pod.containers_started.duration": "containersStartedLatency",
    "k8s.pod.ready_to_start_containers.duration": "readyToStartContainersLatency",
}
EXPECTED_ITERATIONS = set(range(10))
CONTAINED_WORKLOAD = {
    "id": "pod-startup-contained",
    "version": "1.0.0",
    "sha256": "1dd90543d8cbd79014fbb522890463c0ee0c324d0ecff92973da58423500a29d",
}


def latency(value: Any) -> float | int:
    """Return one finite non-negative millisecond duration."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Pod latency must be numeric")
    if not math.isfinite(value) or value < 0:
        raise ValueError("Pod latency must be finite and non-negative")
    return value


class KubeBurnerNormalizer:
    """Normalize ten complete observations, without attesting external provenance.

    File adapters must validate the raw manifest, verify the selected bytes and
    call ``check_kube_burner_manifest`` before using this statistical boundary.
    """

    def normalize(
        self,
        document: list[Any],
        run_id: str,
        metric_names: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return selected lower-is-better millisecond distributions.

        Reject incomplete, duplicated or misattributed iterations, unsupported
        selections and non-finite/negative latency values. Input is not mutated.
        """
        observations = self._observations(document, run_id)
        names = list(METRICS) if metric_names is None else metric_names
        if not names or len(names) != len(set(names)) or any(name not in METRICS for name in names):
            raise ValueError("Metric selection must be supported, non-empty, and unique")

        results = []
        for name in names:
            field = METRICS[name]
            values = [latency(observations[iteration].get(field)) for iteration in range(10)]
            result = {
                "schemaVersion": 2,
                "runId": run_id,
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
    def _observations(document: list[Any], run_id: str) -> dict[int, dict[str, Any]]:
        if len(document) != len(EXPECTED_ITERATIONS):
            raise ValueError("Expected ten pod-startup observations")
        observations: dict[int, dict[str, Any]] = {}
        for value in document:
            if not isinstance(value, dict):
                raise ValueError("Expected kube-burner observation objects")
            iteration = value.get("jobIteration")
            if (
                isinstance(iteration, bool)
                or not isinstance(iteration, int)
                or iteration not in EXPECTED_ITERATIONS
                or iteration in observations
            ):
                raise ValueError("Pod-startup iterations must be complete and unique")
            if (
                value.get("uuid") != run_id
                or value.get("jobName") != "pod-startup-smoke"
                or value.get("metricName") != "podLatencyMeasurement"
            ):
                raise ValueError("Kube-burner observation identity does not match the run")
            observations[iteration] = value
        return observations


def check_kube_burner_manifest(document: list[Any], manifest: dict[str, Any]) -> None:
    """Bind observations to a validated raw manifest and a supported execution recipe.

    Archive captures retain their host workload. OCI captures require the exact
    contained workload from perfeng-k8s a0e2b670bea91af182aaff78c925f4a3c6d1d861.
    This check neither authenticates the runner image nor establishes environment
    qualification or baseline eligibility; those are the caller's responsibilities.
    """
    producer = manifest["producer"]
    provenance = producer.get("artifact", {}).get("kind")
    workload = manifest["workload"]
    supported = (provenance == "release-archive" and workload["id"] == "pod-startup-smoke") or (
        provenance == "oci-image"
        and producer["version"] == "2.8.5"
        and workload == CONTAINED_WORKLOAD
    )
    if (
        manifest["testId"] != "pod-startup-k8s"
        or producer["name"] != "kube-burner"
        or not supported
    ):
        raise ValueError("Raw manifest does not describe the reviewed kube-burner workload")
    start = datetime.fromisoformat(manifest["measurementWindow"]["start"])
    end = datetime.fromisoformat(manifest["measurementWindow"]["end"])
    for value in document:
        if not isinstance(value, dict) or not isinstance(value.get("timestamp"), str):
            raise ValueError("Kube-burner observation timestamp is missing")
        try:
            observed = datetime.fromisoformat(value["timestamp"])
        except ValueError as error:
            raise ValueError("Kube-burner observation timestamp is invalid") from error
        if observed.tzinfo is None:
            raise ValueError("Kube-burner observation timestamp requires a timezone")
        if observed < start or observed >= end:
            raise ValueError("Kube-burner observation is outside the measurement window")
