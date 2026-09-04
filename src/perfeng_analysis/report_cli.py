"""Generate a validated analysis report from explicit local inputs."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from jsonschema.exceptions import ValidationError

from . import __version__
from .report import build_analysis_report
from .validation import parse_object


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--candidate-artifact", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--reference-artifact", type=Path)
    parser.add_argument("--producer-image", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        candidate_data = args.candidate.read_bytes()
        candidate_artifact = parse_object(args.candidate_artifact.read_bytes())
        policy_data = args.policy.read_bytes()
        reference_data = args.reference.read_bytes() if args.reference is not None else None
        reference_artifact = (
            parse_object(args.reference_artifact.read_bytes())
            if args.reference_artifact is not None
            else None
        )
        report = build_analysis_report(
            candidate_data,
            candidate_artifact,
            policy_data,
            producer={
                "name": "perfeng-analysis",
                "version": __version__,
                "image": args.producer_image,
            },
            created_at=datetime.now(UTC).isoformat(),
            reference_data=reference_data,
            reference_artifact=reference_artifact,
        )
        encoded = json.dumps(report, indent=2, allow_nan=False) + "\n"
        with args.output.open("x", encoding="utf-8", newline="\n") as output:
            output.write(encoded)
    except (OSError, ValueError, ValidationError) as error:
        parser.exit(1, f"Analysis failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
