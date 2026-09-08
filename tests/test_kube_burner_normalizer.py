from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from perfeng_analysis import KubeBurnerNormalizer
from perfeng_analysis.kube_burner_normalizer import check_kube_burner_manifest
from perfeng_analysis.validation import parse_json, validate

RUN_ID = "perf-20260908-120000-a1b2c3d4"
ARTIFACT_ID = "11111111-1111-4111-8111-111111111111"


def observations() -> list[dict[str, Any]]:
    return [
        {
            "timestamp": f"2026-09-01T12:00:{iteration + 1:02d}Z",
            "schedulingLatency": iteration + 1,
            "initializedLatency": 0,
            "containersReadyLatency": 20 + iteration,
            "podReadyLatency": 30 + iteration,
            "containersStartedLatency": 15 + iteration,
            "readyToStartContainersLatency": 18 + iteration,
            "metricName": "podLatencyMeasurement",
            "uuid": RUN_ID,
            "jobName": "pod-startup-smoke",
            "jobIteration": iteration,
            "replica": 1,
        }
        for iteration in range(10)
    ]


def raw_manifest(raw: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    artifact = {
        "id": ARTIFACT_ID,
        "runId": RUN_ID,
        "kind": "raw",
        "uri": f"s3://perfeng-artifacts/runs/{RUN_ID}/raw/pod-latency.json",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "sizeBytes": len(raw),
        "mediaType": "application/json",
        "format": "kube-burner-pod-latency-json",
    }
    manifest = {
        "schemaVersion": 2,
        "kind": "RawResult",
        "contractsVersion": "0.13.0",
        "runId": RUN_ID,
        "testId": "pod-startup-k8s",
        "workload": {"id": "pod-startup-smoke", "version": "1.0.0", "sha256": "a" * 64},
        "producer": {
            "name": "kube-burner",
            "version": "2.8.5",
            "artifact": {
                "kind": "release-archive",
                "url": "https://example.com/kube-burner-v2.8.5.zip",
                "archiveSha256": "b" * 64,
                "executableSha256": "c" * 64,
            },
        },
        "measurementWindow": {
            "start": "2026-09-01T12:00:00Z",
            "end": "2026-09-01T12:01:00Z",
        },
        "createdAt": "2026-09-01T12:01:01Z",
        "artifacts": [artifact],
    }
    return manifest, artifact


class KubeBurnerNormalizerTests(unittest.TestCase):
    def test_normalizes_complete_observations_with_platform_statistics(self) -> None:
        results = KubeBurnerNormalizer().normalize(observations(), RUN_ID)

        self.assertEqual(len(results), 6)
        by_name = {result["metric"]["name"]: result for result in results}
        scheduling = by_name["k8s.pod.scheduling.duration"]
        self.assertEqual(scheduling["distribution"]["samples"], 10)
        self.assertEqual(scheduling["distribution"]["mean"], 5.5)
        self.assertEqual(scheduling["distribution"]["median"], 5.5)
        self.assertAlmostEqual(scheduling["distribution"]["p95"], 9.55)
        self.assertEqual(scheduling["metric"]["unit"], "ms")
        initialized = by_name["k8s.pod.initialized.duration"]["distribution"]
        self.assertEqual(initialized["mean"], 0)
        self.assertNotIn("cv", initialized)
        for result in results:
            validate("result/v2/test-result.schema.json", result)

    def test_metric_selection_is_explicit_and_unique(self) -> None:
        selected = KubeBurnerNormalizer().normalize(
            observations(), RUN_ID, ["k8s.pod.ready.duration"]
        )
        self.assertEqual(
            [result["metric"]["name"] for result in selected], ["k8s.pod.ready.duration"]
        )
        for selection in ([], ["unknown"], ["k8s.pod.ready.duration"] * 2):
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                KubeBurnerNormalizer().normalize(observations(), RUN_ID, selection)

    def test_rejects_incomplete_or_misattributed_observations(self) -> None:
        mutations = {
            "missing": lambda values: values.pop(),
            "duplicate": lambda values: values[1].update(jobIteration=0),
            "run": lambda values: values[0].update(uuid="perf-20260908-120000-deadbeef"),
            "job": lambda values: values[0].update(jobName="other"),
        }
        for name, mutate in mutations.items():
            values = observations()
            mutate(values)
            with self.subTest(name=name), self.assertRaises(ValueError):
                KubeBurnerNormalizer().normalize(values, RUN_ID)

    def test_rejects_invalid_latency_values(self) -> None:
        for value in (-1, True, "1", float("nan"), float("inf")):
            document = observations()
            document[0]["podReadyLatency"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                KubeBurnerNormalizer().normalize(document, RUN_ID)

    def test_manifest_binding_requires_release_provenance_and_windowed_timestamps(self) -> None:
        raw = json.dumps(observations()).encode()
        manifest, _ = raw_manifest(raw)
        check_kube_burner_manifest(observations(), manifest)

        for name, mutate in {
            "producer": lambda value: value["producer"].update(name="other"),
            "artifact": lambda value: value["producer"]["artifact"].update(kind="oci-image"),
            "workload": lambda value: value["workload"].update(id="other"),
        }.items():
            changed = copy.deepcopy(manifest)
            mutate(changed)
            with self.subTest(name=name), self.assertRaises(ValueError):
                check_kube_burner_manifest(observations(), changed)

        changed_observations = observations()
        changed_observations[0]["timestamp"] = "2026-09-01T12:01:00Z"
        with self.assertRaisesRegex(ValueError, "outside"):
            check_kube_burner_manifest(changed_observations, manifest)

    def test_cli_normalizes_verified_kube_burner_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = json.dumps(observations()).encode()
            summary = root / "pod-latency.json"
            summary.write_bytes(raw)
            manifest, artifact = raw_manifest(raw)
            manifest_path = root / "raw-result.json"
            output = root / "normalized-result.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            command = [
                sys.executable,
                "-m",
                "perfeng_analysis",
                "--manifest",
                str(manifest_path),
                "--summary",
                str(summary),
                "--artifact-id",
                artifact["id"],
                "--producer-image",
                "example.invalid/analysis@sha256:" + "d" * 64,
                "--output",
                str(output),
            ]

            completed = subprocess.run(command, capture_output=True, text=True)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            normalized = parse_json(output.read_bytes())
            validate("normalized-result/v1/normalized-result.schema.json", normalized)
            self.assertEqual(normalized["contractsVersion"], "0.13.0")
            self.assertEqual(normalized["sourceArtifacts"], [artifact])
            self.assertEqual(len(normalized["results"]), 6)


if __name__ == "__main__":
    unittest.main()
