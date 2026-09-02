import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from perfeng_analysis import K6Normalizer
from perfeng_analysis.validation import parse_json, validate

RUN = "perf-20240115-143022-ab12cd34"
FIXTURE = Path(__file__).parent / "fixtures/prototype-summary.json"


class NormalizerTests(unittest.TestCase):
    def setUp(self):
        self.normalizer = K6Normalizer()
        self.data = parse_json(FIXTURE.read_bytes())

    def test_prototype_metrics_and_corrected_units(self):
        results = self.normalizer.normalize(self.data, RUN)
        self.assertEqual(len(results), 4)
        self.assertEqual(results[0]["distribution"]["samples"], 1000)
        self.assertEqual(results[0]["distribution"]["p95"], 345)
        self.assertEqual(results[1]["metric"]["unit"], "ratio")
        self.assertEqual(results[1]["distribution"], {"mean": 0.005})
        self.assertEqual(results[2]["metric"]["unit"], "req/s")
        self.assertEqual(results[2]["distribution"], {"mean": 50.5})
        self.assertNotIn("thresholds", results[0])

    def test_real_k6_220_export(self):
        data = parse_json((FIXTURE.parent / "k6-2.2.0-summary.json").read_bytes())
        results = self.normalizer.normalize(data, RUN, layout="legacy-export")
        metrics = {result["metric"]["name"]: result for result in results}
        self.assertEqual(len(metrics), 5)
        self.assertEqual(
            metrics["api.http.duration"]["distribution"]["mean"],
            data["metrics"]["http_req_duration"]["avg"],
        )
        self.assertNotIn("samples", metrics["api.http.duration"]["distribution"])
        self.assertEqual(metrics["api.http.error_rate"]["distribution"]["mean"], 0)

    def test_selection_and_layout_fail_closed(self):
        for selection in [[], ["http_req_duration", "http_req_duration"]]:
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                self.normalizer.normalize(self.data, RUN, selection)
        for layout in ["unknown", "legacy-export"]:
            with self.subTest(layout=layout), self.assertRaises(ValueError):
                self.normalizer.normalize(self.data, RUN, layout=layout)

    def test_overflow_and_null_only_measurements(self):
        for values in [{"avg": 10**1000}, {"avg": 1e-320, "stddev": 1}, {"avg": None, "count": 1}]:
            data = {"metrics": {"http_req_duration": {"type": "trend", "values": values}}}
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.normalizer.normalize(data, RUN)

    def test_unknown_statistics_not_fabricated(self):
        data = {
            "metrics": {
                "http_req_duration": {"type": "trend", "values": {"avg": 180, "p(95)": 260}}
            }
        }
        result = self.normalizer.normalize(data, RUN)[0]["distribution"]
        self.assertEqual(result, {"mean": 180, "p95": 260})

    def test_flat_export(self):
        data = {
            "metrics": {
                "http_req_duration": {"avg": 10, "min": 5, "max": 15},
                "http_req_failed": {"value": 0.25, "passes": 1, "fails": 3},
                "http_reqs": {"count": 4, "rate": 2},
            }
        }
        result = self.normalizer.normalize(data, RUN, layout="legacy-export")
        self.assertEqual(result[1]["distribution"], {"mean": 0.25})
        self.assertEqual(result[2]["distribution"], {"mean": 2})
        self.assertNotIn("samples", result[0]["distribution"])

    def test_null_and_zero_stddev(self):
        values = self.data["metrics"]["http_req_duration"]["values"]
        values["count"] = None
        values["stddev"] = 0
        result = self.normalizer.normalize(self.data, RUN, ["http_req_duration"])[0]
        self.assertIsNone(result["distribution"]["samples"])
        self.assertEqual(result["distribution"]["cv"], 0)

    def test_bad_counts(self):
        for count in [0, -1, 1.5, True, "1"]:
            with self.subTest(count=count):
                self.data["metrics"]["http_req_duration"]["values"]["count"] = count
                with self.assertRaises(ValueError):
                    self.normalizer.normalize(self.data, RUN)

    def test_malformed_and_unknown_metrics(self):
        for data in [{}, {"metrics": []}, {"metrics": {}}, {"metrics": {"unknown": {}}}]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.normalizer.normalize(data, RUN)
        with self.assertRaises(ValueError):
            self.normalizer.normalize(self.data, RUN, ["missing"])

    def test_invalid_values_and_types(self):
        for value in [True, "10", float("nan"), float("inf"), -1]:
            with self.subTest(value=value):
                self.data["metrics"]["http_req_duration"]["values"]["avg"] = value
                with self.assertRaises(ValueError):
                    self.normalizer.normalize(self.data, RUN)
        self.data["metrics"]["http_req_duration"]["type"] = "counter"
        with self.assertRaises(ValueError):
            self.normalizer.normalize(self.data, RUN)

    def test_invalid_ratio_and_alias_collision(self):
        self.data["metrics"]["http_req_failed"]["values"]["rate"] = 5
        with self.assertRaises(ValueError):
            self.normalizer.normalize(self.data, RUN)
        self.data = parse_json(FIXTURE.read_bytes())
        self.data["metrics"]["biz_checkout_duration"] = self.data["metrics"]["checkout_duration"]
        with self.assertRaises(ValueError):
            self.normalizer.normalize(self.data, RUN)

    def test_json_rejects_duplicates_and_nonfinite(self):
        for data in [b'{"x":NaN}', b'{"x":1e999}', b'{"x":1,"x":2}']:
            with self.subTest(data=data), self.assertRaises(ValueError):
                parse_json(data)

    def test_cli_integrity_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            raw = FIXTURE.read_bytes()
            summary = folder / "summary.json"
            summary.write_bytes(raw)
            artifact = {
                "id": "11111111-1111-4111-8111-111111111111",
                "runId": RUN,
                "kind": "raw",
                "uri": "s3://synthetic-fixtures/summary.json",
                "sha256": hashlib.sha256(raw).hexdigest(),
                "sizeBytes": len(raw),
                "mediaType": "application/json",
                "format": "k6-summary-json",
            }
            manifest: dict[str, Any] = {
                "schemaVersion": 1,
                "kind": "RawResult",
                "contractsVersion": "0.4.0",
                "runId": RUN,
                "testId": "checkout-api",
                "workload": {"id": "checkout-smoke", "version": "1.0.0", "sha256": "a" * 64},
                "producer": {
                    "name": "k6",
                    "version": "2.2.0",
                    "image": "example.invalid/k6@sha256:" + "b" * 64,
                },
                "measurementWindow": {
                    "start": "2024-01-15T14:30:22Z",
                    "end": "2024-01-15T14:32:22Z",
                },
                "createdAt": "2024-01-15T14:32:23Z",
                "artifacts": [artifact],
            }
            manifest_file, output = folder / "manifest.json", folder / "normalized.json"
            manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
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
                "--layout",
                "typed",
                "--summary-covers-window",
                "--output",
                str(output),
            ]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            normalized = parse_json(output.read_bytes())
            validate("normalized-result/v1/normalized-result.schema.json", normalized)
            self.assertEqual(normalized["sourceArtifacts"], [artifact])
            self.assertEqual(summary.read_bytes(), raw)
            before = output.read_bytes()
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(output.read_bytes(), before)
            for mutation in ["run", "window", "credentials", "duplicate", "image", "missing"]:
                invalid = copy.deepcopy(manifest)
                if mutation == "run":
                    invalid["artifacts"][0]["runId"] = "perf-20240115-143022-deadbeef"
                elif mutation == "window":
                    invalid["measurementWindow"]["start"] = invalid["measurementWindow"]["end"]
                elif mutation == "credentials":
                    invalid["artifacts"][0]["uri"] = "https://user:secret@example.invalid/raw"
                elif mutation == "duplicate":
                    duplicate = copy.deepcopy(artifact)
                    duplicate["uri"] = "s3://synthetic-fixtures/other"
                    invalid["artifacts"].append(duplicate)
                elif mutation == "image":
                    invalid["producer"]["image"] = "example.invalid/k6:latest"
                else:
                    invalid["artifacts"][0]["id"] = "22222222-2222-4222-8222-222222222222"
                manifest_file.write_text(json.dumps(invalid), encoding="utf-8")
                command[-1] = str(folder / f"{mutation}.json")
                with self.subTest(mutation=mutation):
                    self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
                    self.assertFalse(Path(command[-1]).exists())
            manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
            command[-1] = str(folder / "bad.json")
            summary.write_bytes(raw + b" ")
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertFalse((folder / "bad.json").exists())
            command.remove("--summary-covers-window")
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)


if __name__ == "__main__":
    unittest.main()
