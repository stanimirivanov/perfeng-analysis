"""Prepare Analysis wheel resources using only the reviewed signed distribution."""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from perfeng_analysis.validation import CONTRACTS
from scripts.contracts_shadow import check_parity, signed_projection


def prepare_snapshot(projection: Path, target: Path) -> int:
    """Publish a wheel-ready snapshot into a fresh operator-owned destination."""
    count = check_parity(projection)
    target.mkdir(mode=0o700)
    try:
        shutil.copytree(projection, target, dirs_exist_ok=True)
        shutil.copyfile(CONTRACTS / "lock.json", target / "lock.json")
    except BaseException:
        shutil.rmtree(target)
        raise
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("assets", "bootstrap", "verifier"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--target", type=Path, help="Create a fresh wheel-ready snapshot here")
    args = parser.parse_args()
    try:
        with signed_projection(
            args.assets.absolute(), args.bootstrap.absolute(), args.verifier.absolute()
        ) as projection:
            count = (
                prepare_snapshot(projection, args.target)
                if args.target is not None
                else check_parity(projection)
            )
        print(
            json.dumps({"status": "prepared" if args.target else "preview", "matchedFiles": count})
        )
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"contracts-update: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
