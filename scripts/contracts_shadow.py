"""Compare the signed historical Analysis selection to its packaged snapshot."""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from perfeng_analysis.validation import CONTRACTS, load_validators, parse_json

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "contracts-distribution.lock.json"
FIXTURES = (
    ("raw-result/v2/raw-result.schema.json", "kubernetes/raw-result-oci.json", "producer"),
    ("policy/v1/performance-policy.schema.json", "policy/checkout.json", "spec"),
    ("analysis/v1/analysis-result.schema.json", "analysis/missing-reference.json", "policy"),
)


def check_parity(projection: Path) -> int:
    """Require exact bytes and expected offline validation outcomes from both stores."""
    files = parse_json((CONTRACTS / "lock.json").read_bytes())["files"]
    for name, expected in files.items():
        vendored = (CONTRACTS / name).read_bytes()
        projected = projection / name
        if (
            not projected.is_file()
            or projected.read_bytes() != vendored
            or hashlib.sha256(vendored).hexdigest() != expected
        ):
            raise ValueError(f"Projected member missing or different: {name}")
    if {
        item.relative_to(projection).as_posix() for item in projection.rglob("*") if item.is_file()
    } != files.keys():
        raise ValueError("Unreviewed projected member")

    for store in (CONTRACTS, projection):
        validators = load_validators(store)
        for schema, fixture, required in FIXTURES:
            value = parse_json((ROOT / "tests/fixtures" / fixture).read_bytes())
            validator = validators[f"schemas/{schema}"]
            if not validator.is_valid(value):
                raise ValueError(f"Validator rejected valid fixture: {fixture}")
            del value[required]
            if validator.is_valid(value):
                raise ValueError(f"Validator accepted invalid fixture: {fixture}")
    return len(files)


def run(command: list[str], cwd: Path) -> str:
    return subprocess.run(
        command, cwd=cwd, env={}, check=True, text=True, timeout=120, stdout=subprocess.PIPE
    ).stdout


@contextmanager
def signed_projection(assets: Path, bootstrap: Path, verifier: Path) -> Iterator[Path]:
    """Yield a fresh projection from the pinned signed distribution."""
    lock = parse_json(LOCK.read_bytes())
    snapshot_bytes = (CONTRACTS / "lock.json").read_bytes()
    snapshot = parse_json(snapshot_bytes)
    revision = lock["sourceRevision"]
    if (
        not re.fullmatch(r"[a-f0-9]{40}", revision)
        or snapshot["commit"] != revision
        or snapshot["version"] != lock["bundleVersion"]
        or hashlib.sha256(snapshot_bytes).hexdigest() != lock["snapshotLockSha256"]
    ):
        raise ValueError("Analysis snapshot lock differs from the reviewed shadow selection")

    with tempfile.TemporaryDirectory(prefix="perfeng-analysis-shadow-") as temporary:
        scratch = Path(temporary)
        tool, store = scratch / "tool", scratch / "store"
        store.mkdir(mode=0o700)
        pins, policy, selection = (
            scratch / name for name in ("pins.json", "policy.json", "selection.json")
        )
        pins.write_text(json.dumps(lock["tool"]), encoding="utf-8")
        policy.write_text(json.dumps(lock["publisher"]), encoding="utf-8")
        selection.write_text(
            json.dumps(
                {
                    "sourceRevision": revision,
                    "members": {
                        name: {"destination": name, "sha256": digest}
                        for name, digest in snapshot["files"].items()
                    },
                }
            ),
            encoding="utf-8",
        )
        run(
            [
                str(bootstrap / ".venv/bin/python"),
                "-B",
                "-m",
                "scripts.contracts_tool_release",
                "restore",
                "--archive",
                str(assets / "tool/materializer.tar.gz"),
                "--bundle",
                str(assets / "tool/materializer.sigstore.jsonl"),
                "--verifier",
                str(verifier),
                "--pins",
                str(pins),
                "--target",
                str(tool),
            ],
            bootstrap,
        )
        output = run(
            [
                str(tool / "runtime/bin/python3.12"),
                "-IB",
                str(tool / "materialize.py"),
                "--manifest",
                str(assets / f"history/{revision}.manifest.json"),
                "--archive",
                str(assets / f"history/{revision}.tar.gz"),
                "--bundle",
                str(assets / "history/manifest.sigstore.jsonl"),
                "--policy",
                str(policy),
                "--verifier",
                str(tool / "bin/gh"),
                "--selection",
                str(selection),
                "--target",
                str(store),
                "--execute",
            ],
            scratch,
        )
        pointer = (store / "current").read_bytes()
        if not re.fullmatch(rb"[a-f0-9]{64}\n", pointer):
            raise ValueError("Invalid projection pointer")
        projection = store / pointer[:-1].decode("ascii")
        if output != f"{projection}\n":
            raise ValueError("Projection output disagrees with its current pointer")
        yield projection


def shadow(assets: Path, bootstrap: Path, verifier: Path) -> dict[str, Any]:
    """Compare the signed projection and packaged runtime snapshot."""
    lock = parse_json(LOCK.read_bytes())
    with signed_projection(assets, bootstrap, verifier) as projection:
        count = check_parity(projection)

    return {
        "status": "passed",
        "toolRelease": lock["toolRelease"],
        "toolArchiveSha256": lock["tool"]["archiveSha256"],
        "historyRelease": lock["historyRelease"],
        "manifestSha256": lock["publisher"]["manifestSha256"],
        "sourceRevision": lock["sourceRevision"],
        "bundleVersion": lock["bundleVersion"],
        "snapshotLockSha256": lock["snapshotLockSha256"],
        "matchedFiles": count,
        "fixtureParity": "valid accepted and invalid rejected",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("assets", "bootstrap", "verifier"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                shadow(args.assets.absolute(), args.bootstrap.absolute(), args.verifier.absolute()),
                indent=2,
            )
        )
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"contracts-shadow: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
