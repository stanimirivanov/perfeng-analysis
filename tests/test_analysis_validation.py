import copy
import json
import unittest
from pathlib import Path
from typing import Any

from perfeng_analysis import parse_analysis, parse_policy

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(path: str) -> bytes:
    return (FIXTURES / path).read_bytes()


def document(path: str) -> dict[str, Any]:
    return json.loads(fixture(path))


def encode(value: dict[str, Any]) -> bytes:
    return json.dumps(value).encode()


class AnalysisValidationTests(unittest.TestCase):
    def test_accepts_vendored_contract_examples(self):
        examples = [
            ("analysis/slo-pass-regression-fail.json", "policy/browser.json"),
            ("analysis/missing-reference.json", "policy/browser.json"),
            ("analysis/unknown-samples.json", "policy/checkout.json"),
        ]

        for report_path, policy_path in examples:
            with self.subTest(report=report_path):
                policy = parse_policy(fixture(policy_path))
                report = parse_analysis(fixture(report_path), fixture(policy_path))
                self.assertEqual(report["policy"]["id"], policy["metadata"]["name"])

    def test_analysis_can_be_checked_without_resolving_policy(self):
        report = parse_analysis(fixture("analysis/missing-reference.json"))

        self.assertEqual(report["evaluations"][0]["regression"]["status"], "INCONCLUSIVE")

    def test_policy_must_be_the_exact_referenced_bytes(self):
        report = fixture("analysis/slo-pass-regression-fail.json")
        equivalent_policy = fixture("policy/browser.json") + b"\n"

        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            parse_analysis(report, equivalent_policy)

    def test_policy_rule_ids_and_selectors_are_unique(self):
        policy = document("policy/browser.json")
        duplicate = copy.deepcopy(policy["spec"]["rules"][0])
        duplicate["metric"]["name"] = "ui.search.other_ms"
        policy["spec"]["rules"].append(duplicate)
        with self.assertRaisesRegex(ValueError, "Duplicate policy rule ID"):
            parse_policy(encode(policy))

        policy = document("policy/browser.json")
        duplicate = copy.deepcopy(policy["spec"]["rules"][0])
        duplicate["id"] = "other-rule"
        policy["spec"]["rules"].append(duplicate)
        with self.assertRaisesRegex(ValueError, "Duplicate policy metric/statistic selector"):
            parse_policy(encode(policy))

    def test_policy_slo_bounds_must_be_ordered(self):
        policy = document("policy/browser.json")
        policy["spec"]["rules"][0]["slo"] = {"min": 300, "max": 200}

        with self.assertRaisesRegex(ValueError, "minimum exceeds maximum"):
            parse_policy(encode(policy))

    def test_candidate_and_reference_provenance_is_consistent(self):
        report = document("analysis/slo-pass-regression-fail.json")
        report["candidateArtifact"]["runId"] = report["referenceArtifacts"][0]["runId"]
        with self.assertRaisesRegex(ValueError, "Candidate run ID"):
            parse_analysis(encode(report))

        report = document("analysis/slo-pass-regression-fail.json")
        report["referenceArtifacts"] = []
        with self.assertRaisesRegex(ValueError, "reference artifact is not declared"):
            parse_analysis(encode(report))

    def test_evaluations_have_unique_rule_ids_and_explanations(self):
        report = document("analysis/slo-pass-regression-fail.json")
        duplicate = copy.deepcopy(report["evaluations"][0])
        duplicate["slo"]["value"] = 150
        report["evaluations"].append(duplicate)
        with self.assertRaisesRegex(ValueError, "Duplicate evaluation rule ID"):
            parse_analysis(encode(report))

        report = document("analysis/slo-pass-regression-fail.json")
        report["evaluations"][0]["regression"]["reasons"] = []
        with self.assertRaisesRegex(ValueError, "Non-PASS outcomes require reasons"):
            parse_analysis(encode(report))

    def test_untrusted_quality_cannot_produce_decisive_results(self):
        report = document("analysis/slo-pass-regression-fail.json")
        report["evaluations"][0]["quality"] = {
            "status": "INCONCLUSIVE",
            "reasons": ["Sample count is unavailable."],
        }

        with self.assertRaisesRegex(ValueError, "Untrusted quality"):
            parse_analysis(encode(report))

    def test_policy_rule_coverage_and_metric_selector_must_match(self):
        report = document("analysis/slo-pass-regression-fail.json")
        report["evaluations"][0]["ruleId"] = "unconfigured-rule"
        with self.assertRaisesRegex(ValueError, "every policy rule"):
            parse_analysis(encode(report), fixture("policy/browser.json"))

        report = document("analysis/slo-pass-regression-fail.json")
        report["evaluations"][0]["metric"]["unit"] = "s"
        with self.assertRaisesRegex(ValueError, "does not match policy"):
            parse_analysis(encode(report), fixture("policy/browser.json"))

    def test_claimed_quality_slo_and_regression_outcomes_are_consistent(self):
        report = document("analysis/slo-pass-regression-fail.json")
        report["evaluations"][0]["quality"]["samples"] = 1
        with self.assertRaisesRegex(ValueError, "sample count"):
            parse_analysis(encode(report), fixture("policy/browser.json"))

        report = document("analysis/slo-pass-regression-fail.json")
        report["evaluations"][0]["slo"]["value"] = 240
        with self.assertRaisesRegex(ValueError, "SLO outcome contradicts"):
            parse_analysis(encode(report), fixture("policy/browser.json"))

        report = document("analysis/slo-pass-regression-fail.json")
        report["evaluations"][0]["regression"]["effect"]["value"] = 0.3
        with self.assertRaisesRegex(ValueError, "effect contradicts"):
            parse_analysis(encode(report), fixture("policy/browser.json"))


if __name__ == "__main__":
    unittest.main()
