"""Construction of complete, validated analysis-result documents."""

import hashlib
import json
from datetime import datetime
from typing import Any

from .evaluator import compare_candidate, evaluate_candidate
from .validation import parse_analysis, parse_normalized, parse_policy, validate


def build_analysis_report(
    candidate_data: bytes,
    candidate_artifact: dict[str, Any],
    policy_data: bytes,
    *,
    producer: dict[str, Any],
    created_at: str,
    reference_data: bytes | None = None,
    reference_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if (reference_data is None) != (reference_artifact is None):
        raise ValueError("Reference bytes and artifact must be supplied together")

    validate("artifact/v1/artifact-reference.schema.json", candidate_artifact)
    if reference_artifact is not None:
        validate("artifact/v1/artifact-reference.schema.json", reference_artifact)
    candidate = parse_normalized(candidate_data)
    policy = parse_policy(policy_data)
    if reference_data is None:
        evaluations = evaluate_candidate(candidate_data, policy_data)
        _mark_missing_references(evaluations, candidate, policy)
        references = []
    else:
        if reference_artifact is None:
            raise ValueError("Reference artifact is required with reference bytes")
        evaluations = compare_candidate(
            candidate_data,
            reference_data,
            policy_data,
            reference_artifact_id=reference_artifact["id"],
        )
        references = [reference_artifact]

    report = {
        "schemaVersion": 1,
        "kind": "AnalysisResult",
        "contractsVersion": candidate["contractsVersion"],
        "runId": candidate["runId"],
        "testId": candidate["testId"],
        "createdAt": created_at,
        "producer": producer,
        "policy": {
            "id": policy["metadata"]["name"],
            "version": policy["metadata"]["version"],
            "sha256": hashlib.sha256(policy_data).hexdigest(),
            "mode": policy["spec"]["mode"],
        },
        "candidateArtifact": candidate_artifact,
        "referenceArtifacts": references,
        "blocking": False,
        "evaluations": evaluations,
    }
    encoded = json.dumps(report, allow_nan=False, separators=(",", ":")).encode()
    validated = parse_analysis(encoded, policy_data)

    if datetime.fromisoformat(validated["createdAt"]) < datetime.fromisoformat(
        candidate["createdAt"]
    ):
        raise ValueError("Analysis cannot predate the candidate normalized result")
    _verify_artifact_bytes(candidate_data, validated["candidateArtifact"])
    if reference_data is not None:
        reference = parse_normalized(reference_data)
        reference_claim = validated["referenceArtifacts"][0]
        if reference_claim["runId"] != reference["runId"]:
            raise ValueError("Reference artifact run does not match its normalized result")
        _verify_artifact_bytes(reference_data, reference_claim)
        if datetime.fromisoformat(validated["createdAt"]) < datetime.fromisoformat(
            reference["createdAt"]
        ):
            raise ValueError("Analysis cannot predate the reference normalized result")

    return validated


def _mark_missing_references(
    evaluations: list[dict[str, Any]],
    candidate: dict[str, Any],
    policy: dict[str, Any],
) -> None:
    results = {result["metric"]["name"]: result for result in candidate["results"]}
    for rule, evaluation in zip(policy["spec"]["rules"], evaluations, strict=True):
        if "regression" not in rule:
            continue
        result = results.get(rule["metric"]["name"])
        value = None if result is None else result["distribution"].get(rule["metric"]["statistic"])
        reason = (
            "The approved reference artifact is unavailable."
            if evaluation["quality"]["status"] == "PASS"
            else "Candidate measurement quality did not pass."
        )
        evaluation["regression"] = {"status": "INCONCLUSIVE", "reasons": [reason]}
        if value is not None:
            evaluation["regression"]["candidateValue"] = value


def _verify_artifact_bytes(data: bytes, artifact: dict[str, Any]) -> None:
    if artifact["sizeBytes"] != len(data):
        raise ValueError("Normalized artifact size does not match its bytes")
    if artifact["sha256"] != hashlib.sha256(data).hexdigest():
        raise ValueError("Normalized artifact checksum does not match its bytes")
