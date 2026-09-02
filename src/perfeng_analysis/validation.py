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
