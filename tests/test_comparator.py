import copy
import json
import unittest

from test_evaluator import browser_policy, encode, fixture, normalized_result

from perfeng_analysis import compare_candidate, parse_analysis

REFERENCE_RUN_ID = "perf-20260901-130000-a1b2c3d5"
REFERENCE_ARTIFACT_ID = "66666666-6666-4666-8666-666666666666"


def reference_result(value: float = 100) -> dict:
    reference = normalized_result()
    reference["runId"] = REFERENCE_RUN_ID
    reference["sourceArtifacts"][0]["runId"] = REFERENCE_RUN_ID
    reference["sourceArtifacts"][0]["uri"] = (
        f"s3://perfeng-example/runs/{REFERENCE_RUN_ID}/summary.json"
    )
    reference["results"][0]["runId"] = REFERENCE_RUN_ID
    reference["results"][0]["distribution"]["mean"] = value
    return reference


def compare(candidate: dict, reference: dict, policy: bytes | None = None) -> dict:
    evaluations = compare_candidate(
        encode(candidate),
        encode(reference),
        fixture("policy/browser.json") if policy is None else policy,
        reference_artifact_id=REFERENCE_ARTIFACT_ID,
    )
    return evaluations[0]


class ComparatorTests(unittest.TestCase):
    def test_relative_degradation_produces_contract_valid_failure(self):
        evaluation = compare(normalized_result(), reference_result())

        self.assertEqual(
            evaluation["regression"],
            {
                "status": "FAIL",
                "reasons": ["The practical regression threshold was met or exceeded."],
                "candidateValue": 140,
                "referenceValue": 100,
                "referenceArtifactId": REFERENCE_ARTIFACT_ID,
                "effect": {"kind": "relative", "value": 0.4},
                "method": {"name": "point-estimate-comparison", "version": "1.0.0"},
            },
        )

        report = fixture("analysis/slo-pass-regression-fail.json")
        report_document = json.loads(report)
        report_document["evaluations"] = [evaluation]
        parse_analysis(encode(report_document), fixture("policy/browser.json"))

    def test_improvement_passes_without_a_reason(self):
        candidate = normalized_result()
        candidate["results"][0]["distribution"]["mean"] = 90

        regression = compare(candidate, reference_result())["regression"]

        self.assertEqual(regression["status"], "PASS")
        self.assertEqual(regression["reasons"], [])
        self.assertAlmostEqual(regression["effect"]["value"], -0.1)

    def test_practical_threshold_is_inclusive(self):
        candidate = normalized_result()
        candidate["results"][0]["distribution"]["mean"] = 110

        regression = compare(candidate, reference_result())["regression"]

        self.assertEqual(regression["status"], "FAIL")
        self.assertAlmostEqual(regression["effect"]["value"], 0.1)

    def test_absolute_and_higher_is_better_comparisons(self):
        policy = browser_policy()
        requirement = policy["spec"]["rules"][0]["regression"]
        requirement["practicalDifference"] = {"kind": "absolute", "value": 20}
        absolute = compare(normalized_result(), reference_result(), encode(policy))["regression"]
        self.assertEqual(absolute["status"], "FAIL")
        self.assertEqual(absolute["effect"], {"kind": "absolute", "value": 40})

        policy = browser_policy()
        policy["spec"]["rules"][0]["regression"]["direction"] = "higher-is-better"
        candidate = normalized_result()
        candidate["results"][0]["metric"]["direction"] = "higher-is-better"
        candidate["results"][0]["distribution"]["mean"] = 90
        reference = reference_result()
        reference["results"][0]["metric"]["direction"] = "higher-is-better"
        higher = compare(candidate, reference, encode(policy))["regression"]
        self.assertEqual(higher["status"], "FAIL")
        self.assertAlmostEqual(higher["effect"]["value"], 0.1)

    def test_zero_relative_reference_is_inconclusive(self):
        regression = compare(normalized_result(), reference_result(0))["regression"]

        self.assertEqual(regression["status"], "INCONCLUSIVE")
        self.assertEqual(regression["referenceValue"], 0)
        self.assertEqual(regression["referenceArtifactId"], REFERENCE_ARTIFACT_ID)

    def test_candidate_and_reference_quality_must_pass(self):
        candidate = normalized_result()
        candidate["results"][0]["distribution"]["samples"] = 1
        candidate_regression = compare(candidate, reference_result())["regression"]
        self.assertEqual(candidate_regression["status"], "INCONCLUSIVE")
        self.assertEqual(candidate_regression["referenceArtifactId"], REFERENCE_ARTIFACT_ID)

        reference = reference_result()
        del reference["results"][0]["distribution"]["samples"]
        reference_regression = compare(normalized_result(), reference)["regression"]
        self.assertEqual(reference_regression["status"], "INCONCLUSIVE")

    def test_missing_reference_metric_and_direction_mismatch_are_inconclusive(self):
        reference = reference_result()
        reference["results"][0]["metric"]["name"] = "different.metric"
        missing = compare(normalized_result(), reference)["regression"]
        self.assertEqual(missing["status"], "INCONCLUSIVE")

        reference = reference_result()
        reference["results"][0]["metric"]["direction"] = "higher-is-better"
        mismatch = compare(normalized_result(), reference)["regression"]
        self.assertEqual(mismatch["status"], "INCONCLUSIVE")

    def test_comparison_requires_distinct_runs_and_policy_test_identity(self):
        same_run = normalized_result()
        with self.assertRaisesRegex(ValueError, "different runs"):
            compare_candidate(
                encode(same_run),
                encode(copy.deepcopy(same_run)),
                fixture("policy/browser.json"),
                reference_artifact_id=REFERENCE_ARTIFACT_ID,
            )

        reference = reference_result()
        reference["testId"] = "another-test"
        with self.assertRaisesRegex(ValueError, "test ID does not match policy"):
            compare(normalized_result(), reference)

    def test_reference_artifact_id_must_be_canonical(self):
        with self.assertRaisesRegex(ValueError, "canonical UUID"):
            compare_candidate(
                encode(normalized_result()),
                encode(reference_result()),
                fixture("policy/browser.json"),
                reference_artifact_id="not-a-uuid",
            )

    def test_unconfigured_regression_remains_not_evaluated(self):
        policy = browser_policy()
        del policy["spec"]["rules"][0]["regression"]

        regression = compare(normalized_result(), reference_result(), encode(policy))["regression"]

        self.assertEqual(regression["status"], "NOT_EVALUATED")

    def test_non_finite_derived_effect_is_inconclusive(self):
        candidate = normalized_result()
        candidate["results"][0]["distribution"]["mean"] = 1e308

        regression = compare(candidate, reference_result(-1e308))["regression"]

        self.assertEqual(regression["status"], "INCONCLUSIVE")


if __name__ == "__main__":
    unittest.main()
