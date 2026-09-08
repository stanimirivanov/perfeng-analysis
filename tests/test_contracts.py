import copy
import unittest
from typing import Any

from jsonschema.exceptions import ValidationError

from perfeng_analysis.validation import check_manifest, validate

RUN_ID = "perf-20260908-120000-a1b2c3d4"


def release_archive_manifest() -> dict[str, Any]:
    return {
        "schemaVersion": 2,
        "kind": "RawResult",
        "contractsVersion": "0.13.0",
        "runId": RUN_ID,
        "testId": "pod-startup-k8s",
        "workload": {
            "id": "pod-startup-smoke",
            "version": "1.0.0",
            "sha256": "a" * 64,
        },
        "producer": {
            "name": "kube-burner",
            "version": "2.8.5",
            "artifact": {
                "kind": "release-archive",
                "url": (
                    "https://github.com/kube-burner/kube-burner/releases/download/"
                    "v2.8.5/kube-burner-V2.8.5-windows-x86_64.zip"
                ),
                "archiveSha256": "b" * 64,
                "executableSha256": "c" * 64,
            },
        },
        "measurementWindow": {
            "start": "2026-09-08T12:00:00Z",
            "end": "2026-09-08T12:01:00Z",
        },
        "createdAt": "2026-09-08T12:01:01Z",
        "artifacts": [
            {
                "id": "11111111-1111-4111-8111-111111111111",
                "runId": RUN_ID,
                "kind": "raw",
                "uri": f"s3://perfeng-artifacts/runs/{RUN_ID}/raw/kube-burner.json",
                "sha256": "d" * 64,
                "sizeBytes": 1024,
                "mediaType": "application/json",
                "format": "kube-burner-pod-latency-json",
            }
        ],
    }


class ContractSnapshotTests(unittest.TestCase):
    def test_accepts_release_archive_raw_provenance(self) -> None:
        check_manifest(release_archive_manifest())

    def test_rejects_unsafe_or_incomplete_release_archive_provenance(self) -> None:
        mutations = {
            "credentials": lambda artifact: artifact.update(
                url="https://user@example.com/kube-burner.zip"
            ),
            "query": lambda artifact: artifact.update(
                url="https://example.com/kube-burner.zip?download=1"
            ),
            "archive hash": lambda artifact: artifact.update(archiveSha256="invalid"),
            "executable hash": lambda artifact: artifact.update(executableSha256="invalid"),
            "mixed kind": lambda artifact: artifact.update(
                repository="https://github.com/kube-burner/kube-burner"
            ),
        }
        for name, mutate in mutations.items():
            manifest = copy.deepcopy(release_archive_manifest())
            artifact = manifest["producer"]["artifact"]
            mutate(artifact)
            with self.subTest(name=name), self.assertRaises(ValidationError):
                validate("raw-result/v2/raw-result.schema.json", manifest)


if __name__ == "__main__":
    unittest.main()
