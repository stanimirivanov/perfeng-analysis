import unittest
from pathlib import Path

from scripts.image import published_reference, validate_image_name, validate_metadata

ROOT = Path(__file__).parent.parent


class ImageTests(unittest.TestCase):
    def test_build_inputs_and_runtime_are_pinned_and_non_root(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn(
            "FROM ghcr.io/astral-sh/uv:0.12.5@sha256:"
            "db2d5999728c5837e1bf9ba278ee6b05cef1e95e82a20e27b0c915cb4478b9d7 AS uv",
            dockerfile,
        )
        self.assertEqual(dockerfile.count("python:3.12.11-slim-bookworm@sha256:"), 2)
        self.assertIn("USER 65532:65532", dockerfile)
        self.assertIn("uv sync --locked --no-dev --no-editable --no-cache", dockerfile)

        ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        self.assertEqual(ignored[0], "*")
        self.assertIn("!src/**", ignored)
        self.assertNotIn("!.git", ignored)
        self.assertNotIn("!.venv", ignored)

    def test_image_argument_cannot_become_docker_options(self):
        for image in ("", "--privileged", "x;whoami", "https://example.com/image"):
            with self.subTest(image=image), self.assertRaises(ValueError):
                validate_image_name(image)

        validate_image_name("ghcr.io/example/perfeng-analysis@sha256:" + "a" * 64)

    def test_runtime_metadata_is_exact(self):
        metadata = {
            "Os": "linux",
            "Architecture": "amd64",
            "Config": {
                "User": "65532:65532",
                "WorkingDir": "/work",
                "Entrypoint": ["perfeng-analysis"],
                "Labels": {
                    "org.opencontainers.image.title": "perfeng-analysis",
                    "org.opencontainers.image.revision": "abc123",
                },
            },
        }

        validate_metadata(metadata, "abc123")
        for mutation in ("Os", "Architecture"):
            with self.subTest(mutation=mutation):
                changed = {**metadata, mutation: "wrong"}
                with self.assertRaises(ValueError):
                    validate_metadata(changed, "abc123")
        with self.assertRaises(ValueError):
            validate_metadata(metadata, "another-revision")

    def test_registry_manifest_digest_is_required(self):
        repository = "ghcr.io/example/perfeng-analysis"
        reference = repository + "@sha256:" + "a" * 64

        self.assertEqual(published_reference([reference], repository), reference)
        for values in (
            None,
            [],
            ["sha256:" + "a" * 64],
            [repository + ":latest"],
            [repository + "@sha256:bad"],
            [reference, reference],
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                published_reference(values, repository)
        with self.assertRaises(ValueError):
            published_reference([reference], "registry.example/perfeng-analysis")

    def test_publication_is_manual_and_main_branch_only(self):
        workflow = (ROOT / ".github/workflows/publish-image.yml").read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("if: github.ref == 'refs/heads/main'", workflow)
        self.assertIn("if: inputs.publish", workflow)
        self.assertIn('docker pull "$reference"', workflow)
        self.assertNotIn("pull_request:", workflow)


if __name__ == "__main__":
    unittest.main()
