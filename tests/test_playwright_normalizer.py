import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from perfeng_analysis import PlaywrightNormalizer
from perfeng_analysis.playwright_normalizer import check_playwright_manifest
from perfeng_analysis.validation import parse_json, validate

FIXTURE = Path(__file__).parent / "fixtures/playwright-measurements-v2.json"


def measurements() -> dict[str, Any]:
    value = parse_json(FIXTURE.read_bytes())
    if not isinstance(value, dict):
        raise TypeError("Fixture must contain an object")
    return value


def manifest(raw: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    document = measurements()
    artifact = {
        "id": "66666666-6666-4666-8666-666666666666",
        "runId": document["runId"],
        "kind": "raw",
        "uri": f"s3://synthetic-fixtures/runs/{document['runId']}/playwright.json",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "sizeBytes": len(raw),
        "mediaType": "application/json",
        "format": "playwright-measurements/v2",
    }
    value = {
        "schemaVersion": 2,
        "kind": "RawResult",
        "contractsVersion": "0.12.0",
        "runId": document["runId"],
        "testId": document["testId"],
        "workload": {field: document["workload"][field] for field in ("id", "version", "sha256")},
        "producer": {
            "name": "playwright",
            "version": document["runtime"]["playwrightVersion"],
            "artifact": {
                "kind": "source-checkout",
                "repository": "https://github.com/example/perfeng-playwright",
                "gitSha": "a" * 40,
                "dependencyLock": {"path": "pnpm-lock.yaml", "sha256": "b" * 64},
            },
        },
        "measurementWindow": document["measurementWindow"],
        "createdAt": "2026-09-02T13:01:03Z",
        "artifacts": [artifact],
    }
    return value, artifact


class PlaywrightNormalizerTests(unittest.TestCase):
    def test_normalizes_complete_duration_series(self):
        results = PlaywrightNormalizer().normalize(measurements())

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(
            result["metric"],
            {
                "name": "ui.search.action_to_visible_ms",
                "type": "latency",
                "unit": "ms",
                "direction": "lower-is-better",
            },
        )
        distribution = result["distribution"]
        self.assertEqual(distribution["samples"], 3)
        self.assertAlmostEqual(distribution["mean"], 162.66666666666666)
        self.assertEqual(distribution["median"], 161)
        self.assertAlmostEqual(distribution["p95"], 167.3)
        self.assertEqual(distribution["min"], 159)
        self.assertEqual(distribution["max"], 168)
        validate("result/v2/test-result.schema.json", result)

    def test_selection_is_explicit_and_unique(self):
        document = measurements()
        document["measurements"].extend(
            {"iteration": iteration, "name": "ui.search.secondary_ms", "durationMs": 10}
            for iteration in range(1, 4)
        )

        result = PlaywrightNormalizer().normalize(document, ["ui.search.secondary_ms"])
        self.assertEqual([item["metric"]["name"] for item in result], ["ui.search.secondary_ms"])
        for selection in ([], ["missing"], ["ui.search.secondary_ms"] * 2):
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                PlaywrightNormalizer().normalize(document, selection)

    def test_rejects_duplicate_or_incomplete_iterations(self):
        for mutation in ("duplicate", "missing"):
            document = measurements()
            if mutation == "duplicate":
                document["measurements"].append(copy.deepcopy(document["measurements"][0]))
            else:
                document["measurements"].pop()
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                PlaywrightNormalizer().normalize(document)

    def test_manifest_binding_checks_run_workload_window_and_time(self):
        document = measurements()
        raw_manifest, _ = manifest(FIXTURE.read_bytes())
        check_playwright_manifest(document, raw_manifest)

        mutations = {
            "runId": lambda value: value.update(runId="perf-20260902-130000-deadbeef"),
            "workload": lambda value: value["workload"].update(sha256="c" * 64),
            "measurementWindow": lambda value: value["measurementWindow"].update(
                end="2026-09-02T13:00:59Z"
            ),
            "createdAt": lambda value: value.update(createdAt="2026-09-02T13:01:04Z"),
        }
        for name, mutate in mutations.items():
            invalid = copy.deepcopy(document)
            mutate(invalid)
            with self.subTest(name=name), self.assertRaises(ValueError):
                check_playwright_manifest(invalid, raw_manifest)

    def test_cli_normalizes_native_playwright_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            raw = FIXTURE.read_bytes()
            summary = folder / "playwright.json"
            summary.write_bytes(raw)
            raw_manifest, artifact = manifest(raw)
            manifest_file = folder / "raw-result.json"
            output = folder / "normalized-result.json"
            manifest_file.write_text(json.dumps(raw_manifest), encoding="utf-8")
            command = [
                sys.executable,
                "-m",
                "perfeng_analysis",
                "--manifest",
                str(manifest_file),
                "--summary",
                str(summary),
                "--artifact-id",
                artifact["id"],
                "--producer-image",
                "example.invalid/analysis@sha256:" + "c" * 64,
                "--output",
                str(output),
            ]

            completed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            normalized = parse_json(output.read_bytes())
            validate("normalized-result/v1/normalized-result.schema.json", normalized)
            self.assertEqual(normalized["contractsVersion"], "0.12.0")
            self.assertEqual(normalized["sourceArtifacts"], [artifact])
            self.assertEqual(normalized["results"][0]["distribution"]["samples"], 3)
            self.assertEqual(summary.read_bytes(), raw)

            command.extend(["--layout", "typed"])
            command[-3] = str(folder / "invalid.json")
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertFalse((folder / "invalid.json").exists())


if __name__ == "__main__":
    unittest.main()
