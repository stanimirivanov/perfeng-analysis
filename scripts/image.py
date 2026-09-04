"""Verify the local analysis image and resolve its published registry digest."""

import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
IMAGE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9./:@_-]*$")
REPOSITORY_PATTERN = re.compile(r"^ghcr\.io/[a-z0-9_-]+/perfeng-analysis$")
DIGEST_PATTERN = re.compile(r"^[^@]+@sha256:[0-9a-f]{64}$")


def validate_image_name(image: str) -> None:
    if "://" in image or IMAGE_PATTERN.fullmatch(image) is None:
        raise ValueError("Expected a Docker image name, not command options or a URL")


def validate_metadata(metadata: dict[str, Any], revision: str | None = None) -> None:
    config = metadata.get("Config", {})
    labels = config.get("Labels") or {}
    if metadata.get("Os") != "linux" or metadata.get("Architecture") != "amd64":
        raise ValueError("Expected a Linux AMD64 image")
    if config.get("User") != "65532:65532":
        raise ValueError("Expected the unprivileged analysis runtime identity")
    if config.get("WorkingDir") != "/work" or config.get("Entrypoint") != ["perfeng-analysis"]:
        raise ValueError("Unexpected analysis image process configuration")
    if labels.get("org.opencontainers.image.title") != "perfeng-analysis":
        raise ValueError("Unexpected analysis image title")
    if revision is not None and labels.get("org.opencontainers.image.revision") != revision:
        raise ValueError("Analysis image revision does not match the source revision")


def published_reference(repo_digests: Any, repository: str) -> str:
    if REPOSITORY_PATTERN.fullmatch(repository) is None:
        raise ValueError("Expected the analysis GHCR repository")
    values = repo_digests if isinstance(repo_digests, list) else []
    matches = [
        value
        for value in values
        if isinstance(value, str)
        and value.startswith(repository + "@sha256:")
        and DIGEST_PATTERN.fullmatch(value) is not None
    ]
    if len(matches) != 1:
        raise ValueError("A unique published registry digest is required")
    return matches[0]


def inspect_image(image: str) -> dict[str, Any]:
    response = _docker("image", "inspect", image)
    documents = json.loads(response)
    if not isinstance(documents, list) or len(documents) != 1:
        raise ValueError("Docker returned unexpected image metadata")
    return documents[0]


def verify_image(image: str, revision: str | None = None) -> None:
    validate_image_name(image)
    validate_metadata(inspect_image(image), revision)
    restricted = (
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
    )
    _docker(*restricted, image, "--help")
    _docker(*restricted, "--entrypoint", "perfeng-report", image, "--help")
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    installed = _docker(
        *restricted,
        "--entrypoint",
        "python",
        image,
        "-c",
        "import perfeng_analysis; print(perfeng_analysis.__version__)",
    ).strip()
    if installed != version:
        raise ValueError("Installed analysis package version does not match the source")
    print(
        f"Verified image: perfeng-analysis {version}, non-root Linux AMD64 runtime, offline CLIs."
    )


def _docker(*arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["docker", *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError("Docker command could not be executed") from error
    if completed.returncode != 0:
        raise ValueError(f"Docker {arguments[0]} failed; inspect the local Docker environment")
    return completed.stdout


def main() -> int:
    try:
        action, image, *extra = sys.argv[1:]
        validate_image_name(image)
        if action == "verify" and len(extra) <= 1:
            verify_image(image, extra[0] if extra else None)
        elif action == "reference" and len(extra) == 1:
            metadata = inspect_image(image)
            print(published_reference(metadata.get("RepoDigests"), extra[0]))
        else:
            raise ValueError(
                "Usage: image.py verify IMAGE [REVISION] | reference IMAGE GHCR_REPOSITORY"
            )
    except (ValueError, json.JSONDecodeError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
