"""Synthetic OCI capture-to-report coverage; no cluster qualification is implied."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from perfeng_analysis import KubeBurnerNormalizer, ReferenceInput, build_analysis_report
from perfeng_analysis.distribution import summarize
from perfeng_analysis.kube_burner_normalizer import check_kube_burner_manifest
from perfeng_analysis.validation import check_manifest, parse_analysis, parse_json, parse_normalized

FIXTURES = Path(__file__).parent / "fixtures" / "kubernetes"
IMAGE = "example.invalid/perfeng-analysis@sha256:" + "b" * 64
CANDIDATE_ID = "22222222-2222-4222-8222-222222222222"
REFERENCE_ID = "33333333-3333-4333-8333-333333333333"
REFERENCE_RUN = "perf-20260907-120000-deadbeef"


def encode(value: Any) -> bytes:
    return json.dumps(value, allow_nan=False).encode()


def fixture_manifest() -> dict[str, Any]:
    return parse_json((FIXTURES / "raw-result-oci.json").read_bytes())


def fixture_observations() -> list[Any]:
    return parse_json((FIXTURES / "pod-latencies.json").read_bytes())


def normalized_fixture(*, reference: bool = False) -> dict[str, Any]:
    manifest = fixture_manifest()
    run_id = REFERENCE_RUN if reference else manifest["runId"]
    document = fixture_observations()
    for observation in document:
        observation["uuid"] = run_id
    source = copy.deepcopy(manifest["artifacts"][0])
    source["runId"] = run_id
    source["uri"] = f"s3://perfeng-fixtures/runs/{run_id}/raw/pod-latencies.json"
    content = encode(document)
    source.update(sha256=hashlib.sha256(content).hexdigest(), sizeBytes=len(content))
    return {
        "schemaVersion": 1,
        "kind": "NormalizedResult",
        "contractsVersion": "0.22.0",
        "runId": run_id,
        "testId": manifest["testId"],
        "workload": manifest["workload"],
        "producer": {"name": "perfeng-analysis", "version": "0.8.1", "image": IMAGE},
        "measurementWindow": manifest["measurementWindow"],
        "createdAt": "2026-09-08T12:01:02Z",
        "sourceArtifacts": [source],
        "results": KubeBurnerNormalizer().normalize(document, run_id),
    }


def artifact(data: bytes, run_id: str, identity: str) -> dict[str, Any]:
    return {
        "id": identity,
        "runId": run_id,
        "kind": "normalized",
        "uri": f"s3://perfeng-fixtures/runs/{run_id}/normalized-result.json",
        "sha256": hashlib.sha256(data).hexdigest(),
        "sizeBytes": len(data),
        "mediaType": "application/json",
        "format": "normalized-result/v1",
    }


def report_for(
    candidate: dict[str, Any],
    reference: dict[str, Any] | None,
    policy: dict[str, Any],
) -> dict[str, Any]:
    candidate_bytes = encode(candidate)
    references = []
    if reference is not None:
        data = encode(reference)
        references.append(
            ReferenceInput(
                "approved-pod-startup",
                "1.0.0",
                data,
                artifact(data, reference["runId"], REFERENCE_ID),
            )
        )
    return build_analysis_report(
        candidate_bytes,
        artifact(candidate_bytes, candidate["runId"], CANDIDATE_ID),
        encode(policy),
        producer=candidate["producer"],
        created_at="2026-09-08T12:02:00Z",
        references=references,
    )


class KubernetesOCIProvenanceTests(unittest.TestCase):
    def test_fixture_binds_exact_bytes_and_all_six_distributions(self) -> None:
        manifest = fixture_manifest()
        content = (FIXTURES / "pod-latencies.json").read_bytes()
        claim = manifest["artifacts"][0]
        self.assertEqual(claim["sha256"], hashlib.sha256(content).hexdigest())
        self.assertEqual(claim["sizeBytes"], len(content))
        check_manifest(manifest)
        check_kube_burner_manifest(fixture_observations(), manifest)
        results = KubeBurnerNormalizer().normalize(fixture_observations(), manifest["runId"])
        means = [5.5, 6.5, 94.5, 104.5, 84.5, 74.5]
        self.assertEqual(len(results), len(means))
        for result, mean in zip(results, means, strict=True):
            with self.subTest(metric=result["metric"]["name"]):
                distribution = result["distribution"]
                self.assertEqual(result["metric"]["unit"], "ms")
                self.assertEqual(result["metric"]["direction"], "lower-is-better")
                self.assertEqual(distribution["samples"], 10)
                self.assertEqual(distribution["mean"], mean)
                self.assertEqual(distribution["median"], mean)
                self.assertEqual(distribution["min"], mean - 4.5)
                self.assertEqual(distribution["max"], mean + 4.5)
                self.assertAlmostEqual(distribution["p90"], mean + 3.6)
                self.assertAlmostEqual(distribution["p95"], mean + 4.05)
                self.assertAlmostEqual(distribution["p99"], mean + 4.41)
                self.assertAlmostEqual(distribution["stddev"], math.sqrt(8.25))
                self.assertAlmostEqual(distribution["cv"], math.sqrt(8.25) / mean)

    def test_rejects_crossed_or_changed_execution_recipes(self) -> None:
        for name, mutate in {
            "host workload": lambda value: value["workload"].update(id="pod-startup-smoke"),
            "changed workload hash": lambda value: value["workload"].update(sha256="c" * 64),
            "changed workload version": lambda value: value["workload"].update(version="2.0.0"),
            "changed tool version": lambda value: value["producer"].update(version="2.9.0"),
            "wrong tool": lambda value: value["producer"].update(name="k6"),
            "wrong test": lambda value: value.update(testId="another-test"),
            "archive with contained workload": lambda value: value["producer"].update(
                artifact={
                    "kind": "release-archive",
                    "url": "https://example.invalid/kube-burner.zip",
                    "archiveSha256": "c" * 64,
                    "executableSha256": "d" * 64,
                }
            ),
            "source checkout": lambda value: value["producer"].update(
                artifact={
                    "kind": "native-source-checkout",
                    "repository": "https://example.invalid/runner",
                    "commit": "c" * 40,
                }
            ),
        }.items():
            manifest = fixture_manifest()
            mutate(manifest)
            with self.subTest(name=name), self.assertRaises(ValueError):
                check_kube_burner_manifest(fixture_observations(), manifest)

    def test_timestamp_boundaries_offsets_and_missing_values(self) -> None:
        manifest = fixture_manifest()
        for timestamp in ("2026-09-08T12:00:00Z", "2026-09-08T14:00:00+02:00"):
            values = fixture_observations()
            values[0]["timestamp"] = timestamp
            check_kube_burner_manifest(values, manifest)
        for timestamp in (
            "2026-09-08T12:01:00Z",
            "2026-09-08T11:59:59Z",
            "2026-09-08T12:00:00",
            "not-a-timestamp",
            None,
        ):
            values = fixture_observations()
            values[0]["timestamp"] = timestamp
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                check_kube_burner_manifest(values, manifest)


class KubernetesDecisionTests(unittest.TestCase):
    def test_complete_decision_matrix_uses_the_existing_report_pipeline(self) -> None:
        cases = (
            ("pass", "PASS", "PASS", "PASS"),
            ("regression", "PASS", "PASS", "FAIL"),
            ("slo failure", "PASS", "FAIL", "FAIL"),
            ("missing reference", "PASS", "PASS", "INCONCLUSIVE"),
            ("missing metric", "INCONCLUSIVE", "INCONCLUSIVE", "INCONCLUSIVE"),
            ("missing statistic", "INCONCLUSIVE", "INCONCLUSIVE", "INCONCLUSIVE"),
            ("missing samples", "INCONCLUSIVE", "INCONCLUSIVE", "INCONCLUSIVE"),
            ("insufficient samples", "INCONCLUSIVE", "INCONCLUSIVE", "INCONCLUSIVE"),
            ("missing cv", "INCONCLUSIVE", "INCONCLUSIVE", "INCONCLUSIVE"),
            ("unstable candidate", "UNSTABLE", "INCONCLUSIVE", "INCONCLUSIVE"),
            ("unstable reference", "PASS", "PASS", "INCONCLUSIVE"),
            ("wrong unit", "INVALID", "INCONCLUSIVE", "INCONCLUSIVE"),
            ("zero relative reference", "PASS", "PASS", "INCONCLUSIVE"),
        )
        for name, quality, slo, regression in cases:
            with self.subTest(name=name):
                candidate = normalized_fixture()
                reference = normalized_fixture(reference=True)
                policy = parse_json((FIXTURES / "policy.json").read_bytes())
                result = candidate["results"][3]
                distribution = result["distribution"]
                reference_distribution = reference["results"][3]["distribution"]
                if name == "regression":
                    distribution.update(summarize(list(range(120, 130))))
                elif name == "slo failure":
                    distribution.update(summarize(list(range(150, 160))))
                elif name == "missing reference":
                    reference = None
                elif name == "missing metric":
                    candidate["results"].pop(3)
                elif name.startswith("missing "):
                    del distribution[
                        {
                            "missing statistic": "mean",
                            "missing samples": "samples",
                            "missing cv": "cv",
                        }[name]
                    ]
                elif name == "insufficient samples":
                    distribution["samples"] = 9
                elif name == "unstable candidate":
                    distribution.update(summarize([1] * 9 + [1000]))
                elif name == "unstable reference":
                    reference_distribution.update(summarize([1] * 9 + [1000]))
                elif name == "wrong unit":
                    result["metric"]["unit"] = "s"
                elif name == "zero relative reference":
                    reference_distribution.clear()
                    reference_distribution.update(summarize([0] * 10))
                    del policy["spec"]["rules"][0]["quality"]["maxCv"]

                report = report_for(candidate, reference, policy)
                parse_analysis(encode(report), encode(policy))
                evaluation = report["evaluations"][0]
                self.assertEqual(evaluation["quality"]["status"], quality)
                self.assertEqual(evaluation["slo"]["status"], slo)
                self.assertEqual(evaluation["regression"]["status"], regression)
                self.assertFalse(report["blocking"])
                self.assertEqual(report["contractsVersion"], "0.22.0")

    def test_inclusive_slo_and_absolute_regression_boundaries(self) -> None:
        policy = parse_json((FIXTURES / "policy.json").read_bytes())
        policy["spec"]["rules"][0]["slo"]["max"] = 104.5
        policy["spec"]["rules"][0]["regression"]["practicalDifference"] = {
            "kind": "absolute",
            "value": 10,
        }
        candidate = normalized_fixture()
        reference = normalized_fixture(reference=True)
        reference["results"][3]["distribution"].update(summarize(list(range(90, 100))))
        report = report_for(candidate, reference, policy)
        evaluation = report["evaluations"][0]
        self.assertEqual(evaluation["slo"]["status"], "PASS")
        self.assertEqual(evaluation["regression"]["status"], "FAIL")
        self.assertEqual(evaluation["regression"]["effect"], {"kind": "absolute", "value": 10})
        self.assertEqual(evaluation["regression"]["referenceArtifactId"], REFERENCE_ID)
        self.assertEqual(
            report["candidateArtifact"]["sha256"], hashlib.sha256(encode(candidate)).hexdigest()
        )

    def test_references_cannot_cross_kubernetes_workload_id_version_or_hash(self) -> None:
        policy = parse_json((FIXTURES / "policy.json").read_bytes())
        for field, value in (
            ("id", "pod-startup-smoke"),
            ("version", "2.0.0"),
            ("sha256", "c" * 64),
        ):
            reference = normalized_fixture(reference=True)
            reference["workload"][field] = value
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(ValueError, "workload identities"),
            ):
                report_for(normalized_fixture(), reference, policy)


class KubernetesDecisionCLITests(unittest.TestCase):
    def test_normalize_then_report_from_verified_local_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "normalized.json"
            arguments = self.normalization_command(root, output)
            completed = subprocess.run(arguments, capture_output=True, text=True, timeout=30)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            candidate_bytes = output.read_bytes()
            candidate = parse_normalized(candidate_bytes)
            self.assertEqual(candidate["workload"], fixture_manifest()["workload"])
            self.assertEqual(candidate["sourceArtifacts"], fixture_manifest()["artifacts"])
            self.assertEqual(candidate["producer"]["image"], IMAGE)
            claim = root / "candidate-artifact.json"
            claim.write_bytes(encode(artifact(candidate_bytes, candidate["runId"], CANDIDATE_ID)))
            reference = normalized_fixture(reference=True)
            reference_bytes = encode(reference)
            (root / "reference.json").write_bytes(reference_bytes)
            (root / "reference-artifact.json").write_bytes(
                encode(artifact(reference_bytes, reference["runId"], REFERENCE_ID))
            )
            report_path = root / "analysis.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "perfeng_analysis.report_cli",
                    "--candidate",
                    str(output),
                    "--candidate-artifact",
                    str(claim),
                    "--policy",
                    str(FIXTURES / "policy.json"),
                    "--producer-image",
                    IMAGE,
                    "--output",
                    str(report_path),
                    "--baseline",
                    "approved-pod-startup",
                    "1.0.0",
                    str(root / "reference.json"),
                    str(root / "reference-artifact.json"),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = parse_analysis(
                report_path.read_bytes(), (FIXTURES / "policy.json").read_bytes()
            )
            self.assertEqual(report["evaluations"][0]["regression"]["status"], "PASS")
            self.assertEqual(
                report["candidateArtifact"]["sha256"], hashlib.sha256(candidate_bytes).hexdigest()
            )
            repeated = subprocess.run(arguments, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertEqual(output.read_bytes(), candidate_bytes)

    def test_invalid_oci_inputs_leave_no_output(self) -> None:
        for failure in (
            "bytes",
            "size",
            "image",
            "quantiles",
            "job summary",
            "missing latency",
            "naive timestamp",
        ):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                output = root / "normalized.json"
                arguments = self.normalization_command(root, output)
                manifest = fixture_manifest()
                if failure == "bytes":
                    (root / "summary.json").write_bytes(b"changed")
                elif failure == "size":
                    manifest["artifacts"][0]["sizeBytes"] += 1
                elif failure == "image":
                    manifest["producer"]["artifact"]["image"] = "example.invalid/runner:latest"
                elif failure in ("quantiles", "job summary"):
                    manifest["artifacts"][0]["format"] = (
                        "kube-burner-pod-latency-quantiles-json"
                        if failure == "quantiles"
                        else "kube-burner-job-summary-json"
                    )
                else:
                    values = fixture_observations()
                    if failure == "missing latency":
                        del values[0]["podReadyLatency"]
                    else:
                        values[0]["timestamp"] = "2026-09-08T12:00:01"
                    content = encode(values)
                    (root / "summary.json").write_bytes(content)
                    manifest["artifacts"][0].update(
                        sha256=hashlib.sha256(content).hexdigest(), sizeBytes=len(content)
                    )
                (root / "manifest.json").write_bytes(encode(manifest))
                completed = subprocess.run(arguments, capture_output=True, text=True, timeout=30)
                self.assertNotEqual(completed.returncode, 0)
                self.assertNotIn("Traceback", completed.stderr)
                self.assertFalse(output.exists())

    @staticmethod
    def normalization_command(root: Path, output: Path) -> list[str]:
        (root / "summary.json").write_bytes((FIXTURES / "pod-latencies.json").read_bytes())
        (root / "manifest.json").write_bytes((FIXTURES / "raw-result-oci.json").read_bytes())
        return [
            sys.executable,
            "-m",
            "perfeng_analysis",
            "--manifest",
            str(root / "manifest.json"),
            "--summary",
            str(root / "summary.json"),
            "--artifact-id",
            fixture_manifest()["artifacts"][0]["id"],
            "--producer-image",
            IMAGE,
            "--output",
            str(output),
        ]


if __name__ == "__main__":
    unittest.main()
