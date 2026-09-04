"""Conservative candidate quality and SLO evaluation."""

from typing import Any

from .validation import parse_normalized, parse_policy


def evaluate_candidate(normalized_data: bytes, policy_data: bytes) -> list[dict[str, Any]]:
    normalized = parse_normalized(normalized_data)
    policy = parse_policy(policy_data)
    if normalized["testId"] != policy["metadata"]["name"]:
        raise ValueError("Normalized test ID does not match policy")

    results = {result["metric"]["name"]: result for result in normalized["results"]}
    return [
        _evaluate_rule(rule, results.get(rule["metric"]["name"]))
        for rule in policy["spec"]["rules"]
    ]


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


def _outcome(status: str, reason: str) -> dict[str, Any]:
    return {"status": status, "reasons": [reason]}
