"""Pinned offline contracts and strict JSON parsing."""

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Never
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource

CONTRACTS = Path(__file__).parent / "contracts"


def reject_constant(value: str) -> Never:
    raise ValueError(f"Non-finite JSON value: {value}")


def finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Non-finite JSON number")
    return number


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json(data: bytes) -> Any:
    return json.loads(
        data,
        parse_constant=reject_constant,
        parse_float=finite_float,
        object_pairs_hook=unique_object,
    )


def no_network(uri: str) -> Never:
    raise NoSuchResource(ref=uri)


def load_validators() -> dict[str, Draft202012Validator]:
    lock = parse_json((CONTRACTS / "lock.json").read_bytes())
    schemas = {}
    for path, expected in lock["files"].items():
        data = (CONTRACTS / path).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"Vendored checksum mismatch: {path}")
        if path.endswith(".json"):
            schema = parse_json(data)
            Draft202012Validator.check_schema(schema)
            schemas[path] = schema
    registry = Registry(retrieve=no_network).with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas.values()
    )
    return {
        path: Draft202012Validator(schema, registry=registry, format_checker=FormatChecker())
        for path, schema in schemas.items()
    }


VALIDATORS = load_validators()


def validate(name: str, value: Any) -> None:
    VALIDATORS[f"schemas/{name}"].validate(value)


def check_manifest(manifest: dict[str, Any]) -> None:
    validate("raw-result/v1/raw-result.schema.json", manifest)
    start = datetime.fromisoformat(manifest["measurementWindow"]["start"])
    end = datetime.fromisoformat(manifest["measurementWindow"]["end"])
    created = datetime.fromisoformat(manifest["createdAt"])
    if start >= end or created < end:
        raise ValueError("Invalid measurement window or creation time")
    ids, uris = set(), set()
    for artifact in manifest["artifacts"]:
        uri = urlsplit(artifact["uri"])
        if (
            uri.scheme not in {"s3", "https"}
            or not uri.hostname
            or uri.username
            or uri.password
            or uri.query
            or uri.fragment
            or any(char in artifact["uri"] for char in "?#\\\\")
        ):
            raise ValueError("Unsafe artifact URI")
        identity = artifact["id"].lower()
        if identity in ids or artifact["uri"] in uris:
            raise ValueError("Duplicate artifact identity or URI")
        if artifact["runId"] != manifest["runId"]:
            raise ValueError("Artifact belongs to another run")
        ids.add(identity)
        uris.add(artifact["uri"])


def parse_policy(data: bytes) -> dict[str, Any]:
    policy = parse_object(data)
    validate("policy/v1/performance-policy.schema.json", policy)
    check_policy(policy)

    return policy


def parse_analysis(data: bytes, policy_data: bytes | None = None) -> dict[str, Any]:
    report = parse_object(data)
    validate("analysis/v1/analysis-result.schema.json", report)
    policy = None
    if policy_data is not None:
        policy = parse_policy(policy_data)
        if report["policy"]["sha256"] != hashlib.sha256(policy_data).hexdigest():
            raise ValueError("Analysis policy checksum mismatch")
    check_analysis(report, policy)

    return report


def parse_object(data: bytes) -> dict[str, Any]:
    value = parse_json(data)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")

    return value


def check_policy(policy: dict[str, Any]) -> None:
    ids: set[str] = set()
    selectors: set[tuple[str, str]] = set()
    for rule in policy["spec"]["rules"]:
        if rule["id"] in ids:
            raise ValueError("Duplicate policy rule ID")
        selector = (rule["metric"]["name"], rule["metric"]["statistic"])
        if selector in selectors:
            raise ValueError("Duplicate policy metric/statistic selector")
        ids.add(rule["id"])
        selectors.add(selector)
        slo = rule.get("slo", {})
        if "min" in slo and "max" in slo and slo["min"] > slo["max"]:
            raise ValueError("SLO minimum exceeds maximum")


def check_analysis(report: dict[str, Any], policy: dict[str, Any] | None = None) -> None:
    candidate = report["candidateArtifact"]
    check_artifact(candidate)
    if candidate["runId"] != report["runId"]:
        raise ValueError("Candidate run ID does not match analysis")

    ids = {candidate["id"].lower()}
    locations = {candidate["uri"]}
    references: set[str] = set()
    for artifact in report["referenceArtifacts"]:
        check_artifact(artifact)
        identity = artifact["id"].lower()
        if identity in ids or artifact["uri"] in locations:
            raise ValueError("Duplicate candidate/reference artifact identity")
        if artifact["runId"] == report["runId"]:
            raise ValueError("Reference must come from a different run")
        ids.add(identity)
        locations.add(artifact["uri"])
        references.add(identity)

    evaluations: dict[str, Any] = {}
    for evaluation in report["evaluations"]:
        if evaluation["ruleId"] in evaluations:
            raise ValueError("Duplicate evaluation rule ID")
        evaluations[evaluation["ruleId"]] = evaluation
        for section in ("quality", "slo", "regression"):
            verdict = evaluation[section]
            if verdict["status"] != "PASS" and not verdict["reasons"]:
                raise ValueError("Non-PASS outcomes require reasons")
        if evaluation["quality"]["status"] != "PASS" and any(
            evaluation[section]["status"] in {"PASS", "FAIL"} for section in ("slo", "regression")
        ):
            raise ValueError("Untrusted quality cannot yield a decisive performance outcome")
        regression = evaluation["regression"]
        if (
            "referenceArtifactId" in regression
            and regression["referenceArtifactId"].lower() not in references
        ):
            raise ValueError("Regression reference artifact is not declared")

    if policy is None:
        return
    if (report["policy"]["id"], report["policy"]["version"], report["policy"]["mode"]) != (
        policy["metadata"]["name"],
        policy["metadata"]["version"],
        policy["spec"]["mode"],
    ):
        raise ValueError("Analysis policy identity/version/mode mismatch")

    rules = {rule["id"]: rule for rule in policy["spec"]["rules"]}
    if set(rules) != set(evaluations):
        raise ValueError("Analysis must account for every policy rule exactly once")
    for rule_id, rule in rules.items():
        evaluation = evaluations[rule_id]
        if evaluation["metric"] != rule["metric"]:
            raise ValueError("Analysis metric/statistic/unit does not match policy")
        check_configured_sections(rule, evaluation)
        check_quality(rule, evaluation["quality"])
        check_slo(rule, evaluation["slo"])
        check_regression(rule, evaluation["regression"])


def check_artifact(artifact: dict[str, Any]) -> None:
    location = urlsplit(artifact["uri"])
    if not location.hostname or location.username is not None or location.password is not None:
        raise ValueError("Unsafe artifact URI")


def check_configured_sections(rule: dict[str, Any], evaluation: dict[str, Any]) -> None:
    for section in ("slo", "regression"):
        if section not in rule and evaluation[section]["status"] != "NOT_EVALUATED":
            raise ValueError("Unconfigured policy sections must be NOT_EVALUATED")


def check_quality(rule: dict[str, Any], quality: dict[str, Any]) -> None:
    if quality["status"] != "PASS":
        return
    requirement = rule.get("quality", {})
    if "minSamples" in requirement and quality.get("samples", 0) < requirement["minSamples"]:
        raise ValueError("Quality PASS requires the configured sample count")
    if "maxCv" in requirement and ("cv" not in quality or quality["cv"] > requirement["maxCv"]):
        raise ValueError("Quality PASS requires the configured variability bound")


def check_slo(rule: dict[str, Any], slo: dict[str, Any]) -> None:
    if slo["status"] not in {"PASS", "FAIL"}:
        return
    bounds = rule["slo"]
    passes = bounds.get("min", -math.inf) <= slo["value"] <= bounds.get("max", math.inf)
    if (slo["status"] == "PASS") != passes:
        raise ValueError("SLO outcome contradicts the reported value and policy bounds")


def check_regression(rule: dict[str, Any], regression: dict[str, Any]) -> None:
    if regression["status"] not in {"PASS", "FAIL"}:
        return
    requirement = rule["regression"]
    difference = requirement["practicalDifference"]
    if regression["effect"]["kind"] != difference["kind"]:
        raise ValueError("Regression effect kind does not match policy")
    change = regression["candidateValue"] - regression["referenceValue"]
    if requirement["direction"] == "higher-is-better":
        change = -change
    if difference["kind"] == "relative":
        if regression["referenceValue"] == 0:
            raise ValueError("Relative comparison against zero is inconclusive")
        change /= abs(regression["referenceValue"])
    if not math.isclose(change, regression["effect"]["value"], rel_tol=1e-9, abs_tol=1e-12):
        raise ValueError("Reported regression effect contradicts candidate/reference values")
    if (regression["status"] == "FAIL") != (change >= difference["value"]):
        raise ValueError("Regression verdict contradicts the practical threshold")
