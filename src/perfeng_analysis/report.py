"""Construction of complete, validated analysis-result documents."""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .evaluator import compare_candidate_references
from .validation import parse_analysis, parse_normalized, parse_policy, validate


@dataclass(frozen=True)
class ReferenceInput:
    """Bind one policy baseline identity to normalized bytes and their artifact claim."""

    baseline_id: str
    version: str
    data: bytes
    artifact: dict[str, Any]


def build_analysis_report(
    candidate_data: bytes,
    candidate_artifact: dict[str, Any],
    policy_data: bytes,
    *,
    producer: dict[str, Any],
    created_at: str,
    reference_data: bytes | None = None,
    reference_artifact: dict[str, Any] | None = None,
    references: Sequence[ReferenceInput] = (),
) -> dict[str, Any]:
    if (reference_data is None) != (reference_artifact is None):
        raise ValueError("Reference bytes and artifact must be supplied together")
    if references and reference_data is not None:
        raise ValueError("Legacy and policy-keyed references cannot be combined")

    validate("artifact/v1/artifact-reference.schema.json", candidate_artifact)
    candidate = parse_normalized(candidate_data)
    policy = parse_policy(policy_data)
    selected = tuple(references)
    if reference_data is not None:
        if reference_artifact is None:
            raise ValueError("Reference artifact is required with reference bytes")
        identities = _policy_reference_identities(policy)
        if len(identities) != 1:
            raise ValueError("Legacy reference input requires exactly one policy baseline")
        baseline_id, version = identities.pop()
        selected = (ReferenceInput(baseline_id, version, reference_data, reference_artifact),)

    reference_data_by_identity: dict[tuple[str, str], tuple[bytes, str]] = {}
    reference_artifacts = []
    for reference in selected:
        identity = (reference.baseline_id, reference.version)
        if identity in reference_data_by_identity:
            raise ValueError("Policy baseline reference is duplicated")
        validate("artifact/v1/artifact-reference.schema.json", reference.artifact)
        reference_data_by_identity[identity] = (reference.data, reference.artifact["id"])
        reference_artifacts.append(reference.artifact)

    evaluations = compare_candidate_references(
        candidate_data,
        policy_data,
        reference_data_by_identity,
    )

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
        "referenceArtifacts": reference_artifacts,
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
    claims = {claim["id"]: claim for claim in validated["referenceArtifacts"]}
    for reference_input in selected:
        reference = parse_normalized(reference_input.data)
        reference_claim = claims[reference_input.artifact["id"]]
        if reference_claim["runId"] != reference["runId"]:
            raise ValueError("Reference artifact run does not match its normalized result")
        _verify_artifact_bytes(reference_input.data, reference_claim)
        if datetime.fromisoformat(validated["createdAt"]) < datetime.fromisoformat(
            reference["createdAt"]
        ):
            raise ValueError("Analysis cannot predate the reference normalized result")

    return validated


def _policy_reference_identities(policy: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (rule["regression"]["reference"]["baselineId"], rule["regression"]["reference"]["version"])
        for rule in policy["spec"]["rules"]
        if "regression" in rule
    }


def _verify_artifact_bytes(data: bytes, artifact: dict[str, Any]) -> None:
    if artifact["sizeBytes"] != len(data):
        raise ValueError("Normalized artifact size does not match its bytes")
    if artifact["sha256"] != hashlib.sha256(data).hexdigest():
        raise ValueError("Normalized artifact checksum does not match its bytes")
