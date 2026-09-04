import copy
import json
import unittest
from pathlib import Path
from typing import Any

from perfeng_analysis import evaluate_candidate, parse_analysis, parse_normalized

FIXTURES = Path(__file__).parent / "fixtures"
RUN_ID = "perf-20260902-130000-a1b2c3d5"


def fixture(path: str) -> bytes:
    return (FIXTURES / path).read_bytes()


def encode(value: dict[str, Any]) -> bytes:
    return json.dumps(value).encode()


def normalized_result() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": "NormalizedResult",
        "contractsVersion": "0.6.0",
        "runId": RUN_ID,
        "testId": "search-browser",
        "workload": {
            "id": "search-browser-smoke",
            "version": "1.0.0",
            "sha256": "a" * 64,
        },
        "producer": {
            "name": "perfeng-analysis",
            "version": "0.3.0",
            "image": "ghcr.io/example/perfeng-analysis@sha256:" + "b" * 64,
        },
        "measurementWindow": {
            "start": "2026-09-02T13:00:00Z",
            "end": "2026-09-02T13:01:00Z",
        },
        "createdAt": "2026-09-02T13:01:01Z",
        "sourceArtifacts": [
            {
                "id": "11111111-1111-4111-8111-111111111111",
                "runId": RUN_ID,
                "kind": "raw",
                "uri": f"s3://perfeng-example/runs/{RUN_ID}/summary.json",
                "sha256": "c" * 64,
                "sizeBytes": 1024,
                "mediaType": "application/json",
                "format": "k6-summary-json",
            }
        ],
        "results": [
            {
                "schemaVersion": 2,
                "runId": RUN_ID,
                "metric": {
                    "name": "ui.search.action_to_visible_ms",
                    "type": "latency",
                    "unit": "ms",
                    "direction": "lower-is-better",
                },
                "distribution": {
                    "samples": 2,
                    "mean": 140,
                    "stddev": 7,
                    "cv": 0.05,
                },
            }
        ],
    }


def browser_policy() -> dict[str, Any]:
    return json.loads(fixture("policy/browser.json"))


class CandidateEvaluatorTests(unittest.TestCase):
    def test_passes_quality_and_slo_and_defers_regression(self):
        evaluations = evaluate_candidate(
            encode(normalized_result()), fixture("policy/browser.json")
        )

        self.assertEqual(
            evaluations[0]["quality"],
            {
                "status": "PASS",
                "reasons": [],
                "samples": 2,
                "cv": 0.05,
            },
        )
        self.assertEqual(
            evaluations[0]["slo"],
            {
                "status": "PASS",
                "reasons": [],
                "value": 140,
            },
        )
        self.assertEqual(evaluations[0]["regression"]["status"], "NOT_EVALUATED")

        report = json.loads(fixture("analysis/slo-pass-regression-fail.json"))
        report["evaluations"] = evaluations
        parse_analysis(encode(report), fixture("policy/browser.json"))

    def test_fails_slo_outside_the_inclusive_policy_boundary(self):
        normalized = normalized_result()
        normalized["results"][0]["distribution"]["mean"] = 200

        boundary = evaluate_candidate(encode(normalized), fixture("policy/browser.json"))[0]
        self.assertEqual(boundary["slo"]["status"], "PASS")

        normalized["results"][0]["distribution"]["mean"] = 201
        evaluation = evaluate_candidate(encode(normalized), fixture("policy/browser.json"))[0]

        self.assertEqual(evaluation["quality"]["status"], "PASS")
        self.assertEqual(evaluation["slo"]["status"], "FAIL")
        self.assertEqual(evaluation["slo"]["value"], 201)

    def test_missing_or_insufficient_quality_evidence_is_inconclusive(self):
        cases = {
            "missing samples": None,
            "insufficient samples": 1,
        }
        for name, samples in cases.items():
            with self.subTest(name=name):
                normalized = normalized_result()
                if samples is None:
                    del normalized["results"][0]["distribution"]["samples"]
                else:
                    normalized["results"][0]["distribution"]["samples"] = samples

                evaluation = evaluate_candidate(encode(normalized), fixture("policy/browser.json"))[
                    0
                ]

                self.assertEqual(evaluation["quality"]["status"], "INCONCLUSIVE")
                self.assertEqual(evaluation["slo"]["status"], "INCONCLUSIVE")

    def test_excessive_variability_is_unstable(self):
        policy = browser_policy()
        policy["spec"]["rules"][0]["quality"]["maxCv"] = 0.1
        normalized = normalized_result()
        normalized["results"][0]["distribution"]["cv"] = 0.2

        evaluation = evaluate_candidate(encode(normalized), encode(policy))[0]

        self.assertEqual(evaluation["quality"]["status"], "UNSTABLE")
        self.assertEqual(evaluation["slo"]["status"], "INCONCLUSIVE")

    def test_missing_measurement_and_wrong_unit_are_not_decisive(self):
        cases = {
            "missing metric": ("different.metric", "ms", "INCONCLUSIVE"),
            "missing statistic": ("ui.search.action_to_visible_ms", "ms", "INCONCLUSIVE"),
            "wrong unit": ("ui.search.action_to_visible_ms", "s", "INVALID"),
        }
        for name, (metric, unit, status) in cases.items():
            with self.subTest(name=name):
                normalized = normalized_result()
                result = normalized["results"][0]
                result["metric"]["name"] = metric
                result["metric"]["unit"] = unit
                if name == "missing statistic":
                    del result["distribution"]["mean"]

                evaluation = evaluate_candidate(encode(normalized), fixture("policy/browser.json"))[
                    0
                ]

                self.assertEqual(evaluation["quality"]["status"], status)
                self.assertEqual(evaluation["slo"]["status"], "INCONCLUSIVE")

    def test_producer_thresholds_do_not_override_platform_policy(self):
        normalized = normalized_result()
        normalized["results"][0]["thresholds"] = {"slo": {"mean": {"passed": False, "actual": 999}}}

        evaluation = evaluate_candidate(encode(normalized), fixture("policy/browser.json"))[0]

        self.assertEqual(evaluation["slo"]["status"], "PASS")
        self.assertEqual(evaluation["slo"]["value"], 140)

    def test_unconfigured_slo_is_not_evaluated(self):
        policy = browser_policy()
        del policy["spec"]["rules"][0]["slo"]

        evaluation = evaluate_candidate(encode(normalized_result()), encode(policy))[0]

        self.assertEqual(evaluation["slo"]["status"], "NOT_EVALUATED")

    def test_test_identity_must_match_policy(self):
        normalized = normalized_result()
        normalized["testId"] = "another-test"

        with self.assertRaisesRegex(ValueError, "test ID does not match policy"):
            evaluate_candidate(encode(normalized), fixture("policy/browser.json"))

    def test_normalized_envelope_has_consistent_run_and_metric_identity(self):
        normalized = normalized_result()
        duplicate = copy.deepcopy(normalized["results"][0])
        duplicate["distribution"]["mean"] = 150
        normalized["results"].append(duplicate)
        with self.assertRaisesRegex(ValueError, "Duplicate normalized metric"):
            parse_normalized(encode(normalized))

        normalized = normalized_result()
        normalized["results"][0]["runId"] = "perf-20260901-130000-deadbeef"
        with self.assertRaisesRegex(ValueError, "metric belongs to another run"):
            parse_normalized(encode(normalized))

        normalized = normalized_result()
        normalized["sourceArtifacts"][0]["runId"] = "perf-20260901-130000-deadbeef"
        with self.assertRaisesRegex(ValueError, "artifact belongs to another run"):
            parse_normalized(encode(normalized))


if __name__ == "__main__":
    unittest.main()
