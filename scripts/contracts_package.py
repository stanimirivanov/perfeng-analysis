"""Prove current and rollback Analysis wheels validate using their own resources."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts.contracts_shadow import FIXTURES, LOCK, ROOT

PROBE = """
import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path

from perfeng_analysis.validation import CONTRACTS, parse_json, validate
from jsonschema import ValidationError

lock, wheel_url, fixtures, *cases = sys.argv[1:]
if not CONTRACTS.resolve().is_relative_to(Path(sys.prefix).resolve()):
    raise ValueError("Contracts were not loaded from the installed environment")
if hashlib.sha256((CONTRACTS / "lock.json").read_bytes()).hexdigest() != lock:
    raise ValueError("Installed wheel contract lock differs from the reviewed selection")
direct_url = json.loads(importlib.metadata.distribution("perfeng-analysis").read_text("direct_url.json"))
if direct_url["url"] != wheel_url:
    raise ValueError("Installed wheel differs from the selected archive")
for schema, fixture, required in map(json.loads, cases):
    value = parse_json((Path(fixtures) / fixture).read_bytes())
    validate(schema, value)
    del value[required]
    try:
        validate(schema, value)
    except ValidationError:
        continue
    raise ValueError(f"Invalid fixture was accepted: {fixture}")
"""


def check_wheels(current: Path, rollback: Path, rollback_sha256: str) -> dict[str, str]:
    """Install the current and retained wheel in order with the same locked dependencies."""
    current, rollback = current.resolve(), rollback.resolve()
    with current.open("rb") as stream:
        current_digest = hashlib.file_digest(stream, "sha256").hexdigest()
    with rollback.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != rollback_sha256:
            raise ValueError("Retained rollback wheel digest differs from its reviewed pin")
    if current_digest == rollback_sha256:
        raise ValueError("Current and rollback wheel artifacts must be distinct")
    lock_digest = json.loads(LOCK.read_bytes())["snapshotLockSha256"]

    with tempfile.TemporaryDirectory(prefix="perfeng-analysis-wheel-") as directory:
        scratch = Path(directory)
        venv = scratch / "venv"
        python = venv / "bin/python"
        env = {**os.environ, "UV_PROJECT_ENVIRONMENT": str(venv)}
        env.pop("VIRTUAL_ENV", None)
        subprocess.run(
            [
                "uv",
                "sync",
                "--offline",
                "--locked",
                "--no-dev",
                "--no-install-project",
                "--project",
                str(ROOT),
            ],
            cwd=scratch,
            env=env,
            check=True,
            timeout=120,
            stdout=sys.stderr,
        )
        for wheel in (current, rollback):
            subprocess.run(
                [
                    "uv",
                    "pip",
                    "install",
                    "--offline",
                    "--no-deps",
                    "--reinstall",
                    "--python",
                    str(python),
                    str(wheel),
                ],
                cwd=scratch,
                check=True,
                timeout=120,
                stdout=sys.stderr,
            )
            subprocess.run(
                [
                    str(python),
                    "-I",
                    "-c",
                    PROBE,
                    lock_digest,
                    wheel.as_uri(),
                    str(ROOT / "tests/fixtures"),
                    *map(json.dumps, FIXTURES),
                ],
                cwd=scratch,
                check=True,
                timeout=30,
            )
    return {
        "status": "passed",
        "currentWheelSha256": current_digest,
        "rollbackWheelSha256": rollback_sha256,
        "snapshotLockSha256": lock_digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", required=True, type=Path)
    parser.add_argument("--rollback", required=True, type=Path)
    parser.add_argument("--rollback-sha256", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(check_wheels(args.current, args.rollback, args.rollback_sha256)))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"contracts-package: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
