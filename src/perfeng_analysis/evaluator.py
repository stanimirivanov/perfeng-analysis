"""Conservative candidate, SLO, and practical-difference evaluation."""

import math
from typing import Any
from uuid import UUID

from .validation import parse_normalized, parse_policy


def evaluate_candidate(normalized_data: bytes, policy_data: bytes) -> list[dict[str, Any]]:
    normalized = parse_normalized(normalized_data)
    policy = parse_policy(policy_data)
    _check_test_identity(normalized, policy)

    results = {result["metric"]["name"]: result for result in normalized["results"]}
    return [
        _evaluate_rule(rule, results.get(rule["metric"]["name"]))
        for rule in policy["spec"]["rules"]
    ]


def compare_candidate(
    candidate_data: bytes,
    reference_data: bytes,
    policy_data: bytes,
    *,
    reference_artifact_id: str,
) -> list[dict[str, Any]]:
    candidate = parse_normalized(candidate_data)
    reference = parse_normalized(reference_data)
    policy = parse_policy(policy_data)
    _check_test_identity(candidate, policy)
    _check_test_identity(reference, policy)
    if candidate["runId"] == reference["runId"]:
        raise ValueError("Candidate and reference must come from different runs")
    if not _canonical_uuid(reference_artifact_id):
        raise ValueError("Reference artifact ID must be a canonical UUID")

    candidates = {result["metric"]["name"]: result for result in candidate["results"]}
    references = {result["metric"]["name"]: result for result in reference["results"]}
    evaluations = []
    for rule in policy["spec"]["rules"]:
        name = rule["metric"]["name"]
        candidate_result = candidates.get(name)
        evaluation = _evaluate_rule(rule, candidate_result)
        evaluation["regression"] = _evaluate_regression(
            rule,
            evaluation["quality"],
            candidate_result,
            references.get(name),
            reference_artifact_id,
        )
        evaluations.append(evaluation)
    return evaluations


def _evaluate_rule(rule: dict[str, Any], result: dict[str, Any] | None) -> dict[str, Any]:
    selector = rule["metric"]
    quality = _evaluate_quality(rule, result)
    value = None if result is None else result["distribution"].get(selector["statistic"])

    return {
        "ruleId": rule["id"],
        "metric": dict(selector),
        "quality": quality,
        "slo": _evaluate_slo(rule, quality, value),
        "regression": _unevaluated_regression(rule),
    }


def _evaluate_quality(rule: dict[str, Any], result: dict[str, Any] | None) -> dict[str, Any]:
    if result is None:
        return _outcome("INCONCLUSIVE", "The normalized result does not contain the metric.")

    selector = rule["metric"]
    if result["metric"].get("unit") != selector["unit"]:
        return _outcome("INVALID", "The normalized metric unit does not match the policy.")

    distribution = result["distribution"]
    if distribution.get(selector["statistic"]) is None:
        return _outcome(
            "INCONCLUSIVE", "The normalized result does not contain the required statistic."
        )

    evidence = {
        name: distribution[name] for name in ("samples", "cv") if distribution.get(name) is not None
    }
    requirements = rule.get("quality", {})
    inconclusive: list[str] = []
    unstable: list[str] = []
    if "minSamples" in requirements:
        samples = distribution.get("samples")
        if samples is None:
            inconclusive.append("The sample count required by the policy is unavailable.")
        elif samples < requirements["minSamples"]:
            inconclusive.append("The sample count is below the policy minimum.")
    if "maxCv" in requirements:
        cv = distribution.get("cv")
        if cv is None:
            inconclusive.append(
                "The coefficient of variation required by the policy is unavailable."
            )
        elif cv > requirements["maxCv"]:
            unstable.append("The coefficient of variation exceeds the policy maximum.")

    if inconclusive:
        return {"status": "INCONCLUSIVE", "reasons": inconclusive + unstable, **evidence}
    if unstable:
        return {"status": "UNSTABLE", "reasons": unstable, **evidence}
    return {"status": "PASS", "reasons": [], **evidence}


def _evaluate_slo(rule: dict[str, Any], quality: dict[str, Any], value: Any) -> dict[str, Any]:
    if "slo" not in rule:
        return _outcome("NOT_EVALUATED", "No SLO is configured for this rule.")
    if quality["status"] != "PASS":
        outcome = _outcome("INCONCLUSIVE", "Measurement quality did not pass.")
        if value is not None:
            outcome["value"] = value
        return outcome

    reasons = []
    bounds = rule["slo"]
    if "min" in bounds and value < bounds["min"]:
        reasons.append("The measured value is below the policy minimum.")
    if "max" in bounds and value > bounds["max"]:
        reasons.append("The measured value exceeds the policy maximum.")
    return {"status": "FAIL" if reasons else "PASS", "reasons": reasons, "value": value}


def _unevaluated_regression(rule: dict[str, Any]) -> dict[str, Any]:
    if "regression" not in rule:
        return _outcome("NOT_EVALUATED", "No regression comparison is configured for this rule.")
    return _outcome("NOT_EVALUATED", "Reference comparison is not part of candidate evaluation.")


def _evaluate_regression(
    rule: dict[str, Any],
    candidate_quality: dict[str, Any],
    candidate: dict[str, Any] | None,
    reference: dict[str, Any] | None,
    reference_artifact_id: str,
) -> dict[str, Any]:
    if "regression" not in rule:
        return _outcome("NOT_EVALUATED", "No regression comparison is configured for this rule.")

    statistic = rule["metric"]["statistic"]
    candidate_value = None if candidate is None else candidate["distribution"].get(statistic)
    evidence = {"referenceArtifactId": reference_artifact_id}
    if candidate_value is not None:
        evidence["candidateValue"] = candidate_value
    if candidate_quality["status"] != "PASS":
        return {
            **_outcome("INCONCLUSIVE", "Candidate measurement quality did not pass."),
            **evidence,
        }
    if candidate is None or candidate_value is None:
        raise ValueError("Candidate quality outcome contradicts its measurement")
    if reference is None:
        return {
            **_outcome("INCONCLUSIVE", "The reference result does not contain the metric."),
            **evidence,
        }

    reference_quality = _evaluate_quality(rule, reference)
    reference_value = reference["distribution"].get(statistic)
    if reference_quality["status"] != "PASS":
        if reference_value is not None:
            evidence["referenceValue"] = reference_value
        return {
            **_outcome("INCONCLUSIVE", "Reference measurement quality did not pass."),
            **evidence,
        }

    requirement = rule["regression"]
    expected_direction = requirement["direction"]
    if (
        candidate["metric"]["direction"] != expected_direction
        or reference["metric"]["direction"] != expected_direction
    ):
        return {
            **_outcome("INCONCLUSIVE", "Metric direction does not match the regression policy."),
            **evidence,
            "referenceValue": reference_value,
        }

    difference = requirement["practicalDifference"]
    change = candidate_value - reference_value
    if expected_direction == "higher-is-better":
        change = -change
    if difference["kind"] == "relative":
        if reference_value == 0:
            return {
                **_outcome("INCONCLUSIVE", "A relative comparison against zero is undefined."),
                **evidence,
                "referenceValue": reference_value,
            }
        change /= abs(reference_value)
    if not math.isfinite(change):
        return {
            **_outcome("INCONCLUSIVE", "The comparison effect is not representable."),
            **evidence,
            "referenceValue": reference_value,
        }

    failed = change >= difference["value"]
    reasons = ["The practical regression threshold was met or exceeded."] if failed else []
    return {
        "status": "FAIL" if failed else "PASS",
        "reasons": reasons,
        "candidateValue": candidate_value,
        "referenceValue": reference_value,
        "referenceArtifactId": reference_artifact_id,
        "effect": {"kind": difference["kind"], "value": change},
        "method": {"name": "point-estimate-comparison", "version": "1.0.0"},
    }


def _check_test_identity(normalized: dict[str, Any], policy: dict[str, Any]) -> None:
    if normalized["testId"] != policy["metadata"]["name"]:
        raise ValueError("Normalized test ID does not match policy")


def _canonical_uuid(value: str) -> bool:
    try:
        return str(UUID(value)) == value.lower()
    except (AttributeError, TypeError, ValueError):
        return False


def _outcome(status: str, reason: str) -> dict[str, Any]:
    return {"status": status, "reasons": [reason]}
