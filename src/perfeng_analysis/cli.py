"""Offline summary normalization; output is exclusively created."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from jsonschema.exceptions import ValidationError

from . import __version__
from .normalizer import K6Normalizer
from .playwright_normalizer import PlaywrightNormalizer, check_playwright_manifest
from .validation import check_manifest, parse_json, validate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--artifact-id", required=True)
    parser.add_argument("--producer-image", required=True)
    parser.add_argument("--layout", choices=["typed", "legacy-export"])
    parser.add_argument(
        "--summary-covers-window",
        action="store_true",
        help="Assert summary covers exactly the manifest measurement window",
    )
    parser.add_argument("--metric", action="append")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = parse_json(args.manifest.read_bytes())
        check_manifest(manifest)
        matches = [a for a in manifest["artifacts"] if a["id"].lower() == args.artifact_id.lower()]
        if len(matches) != 1:
            raise ValueError("Summary artifact ID is not declared")
        artifact = matches[0]
        if artifact["mediaType"] != "application/json":
            raise ValueError("Unsupported raw artifact format")
        raw = args.summary.read_bytes()
        if (
            len(raw) != artifact["sizeBytes"]
            or hashlib.sha256(raw).hexdigest() != artifact["sha256"]
        ):
            raise ValueError("Summary checksum/size mismatch")
        source = parse_json(raw)
        if artifact["format"] == "k6-summary-json":
            if manifest["producer"]["name"] != "k6":
                raise ValueError("Expected k6 raw producer")
            if args.layout is None or not args.summary_covers_window:
                raise ValueError("k6 normalization requires layout and window assertion")
            results = K6Normalizer().normalize(
                source, manifest["runId"], args.metric, layout=args.layout
            )
        elif artifact["format"] == "playwright-measurements/v2":
            if manifest["producer"]["name"] != "playwright":
                raise ValueError("Expected Playwright raw producer")
            if args.layout is not None or args.summary_covers_window:
                raise ValueError("Playwright measurements define their own layout and window")
            if not isinstance(source, dict):
                raise ValueError("Expected a Playwright measurements object")
            check_playwright_manifest(source, manifest)
            results = PlaywrightNormalizer().normalize(source, args.metric)
        else:
            raise ValueError("Unsupported raw artifact format")
        now = datetime.now(UTC)
        if now < datetime.fromisoformat(manifest["createdAt"]):
            raise ValueError("Raw manifest creation time is in the future")
        result = {
            "schemaVersion": 1,
            "kind": "NormalizedResult",
            "contractsVersion": manifest["contractsVersion"],
            "runId": manifest["runId"],
            "testId": manifest["testId"],
            "workload": manifest["workload"],
            "producer": {
                "name": "perfeng-analysis",
                "version": __version__,
                "image": args.producer_image,
            },
            "measurementWindow": manifest["measurementWindow"],
            "createdAt": now.isoformat(),
            "sourceArtifacts": [artifact],
            "results": results,
        }
        validate("normalized-result/v1/normalized-result.schema.json", result)
        encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
        with args.output.open("x", encoding="utf-8", newline="\n") as output:
            output.write(encoded)
    except (OSError, ValueError, ValidationError) as error:
        parser.exit(1, f"Normalization failed: {error}\n")
    return 0
