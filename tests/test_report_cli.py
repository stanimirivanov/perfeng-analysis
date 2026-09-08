import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_comparator import REFERENCE_ARTIFACT_ID, reference_result
from test_evaluator import RUN_ID, encode, fixture, normalized_result
from test_report import CANDIDATE_ARTIFACT_ID, artifact

from perfeng_analysis import parse_analysis

PRODUCER_IMAGE = "ghcr.io/example/perfeng-analysis@sha256:" + "d" * 64


def write_inputs(folder: Path) -> dict[str, Path]:
    candidate_data = encode(normalized_result())
    reference_document = reference_result()
    reference_data = encode(reference_document)
    paths = {
        "candidate": folder / "candidate.json",
        "candidate_artifact": folder / "candidate-artifact.json",
        "policy": folder / "policy.json",
        "reference": folder / "reference.json",
        "reference_artifact": folder / "reference-artifact.json",
    }
    paths["candidate"].write_bytes(candidate_data)
    paths["candidate_artifact"].write_text(
        json.dumps(artifact(candidate_data, RUN_ID, CANDIDATE_ARTIFACT_ID)), encoding="utf-8"
    )
    paths["policy"].write_bytes(fixture("policy/browser.json"))
    paths["reference"].write_bytes(reference_data)
    paths["reference_artifact"].write_text(
        json.dumps(artifact(reference_data, reference_document["runId"], REFERENCE_ARTIFACT_ID)),
        encoding="utf-8",
    )
    return paths


def command(paths: dict[str, Path], output: Path, *, with_reference: bool) -> list[str]:
    result = [
        sys.executable,
        "-m",
        "perfeng_analysis.report_cli",
        "--candidate",
        str(paths["candidate"]),
        "--candidate-artifact",
        str(paths["candidate_artifact"]),
        "--policy",
        str(paths["policy"]),
        "--producer-image",
        PRODUCER_IMAGE,
        "--output",
        str(output),
    ]
    if with_reference:
        result.extend(
            [
                "--reference",
                str(paths["reference"]),
                "--reference-artifact",
                str(paths["reference_artifact"]),
            ]
        )
    return result


class ReportCLITests(unittest.TestCase):
    def test_generates_valid_report_without_network_or_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            paths = write_inputs(folder)
            output = folder / "analysis.json"

            completed = subprocess.run(
                command(paths, output, with_reference=False), capture_output=True, text=True
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = parse_analysis(output.read_bytes(), paths["policy"].read_bytes())
            self.assertEqual(report["producer"]["version"], "0.8.0")
            self.assertEqual(report["producer"]["image"], PRODUCER_IMAGE)
            self.assertEqual(report["evaluations"][0]["regression"]["status"], "INCONCLUSIVE")

    def test_generates_report_with_explicit_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            paths = write_inputs(folder)
            output = folder / "analysis.json"

            completed = subprocess.run(
                command(paths, output, with_reference=True), capture_output=True, text=True
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = parse_analysis(output.read_bytes(), paths["policy"].read_bytes())
            self.assertEqual(report["evaluations"][0]["regression"]["status"], "FAIL")
            self.assertEqual(report["referenceArtifacts"][0]["id"], REFERENCE_ARTIFACT_ID)

    def test_generates_report_with_policy_keyed_baseline(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            paths = write_inputs(folder)
            output = folder / "analysis.json"
            arguments = command(paths, output, with_reference=False)
            arguments.extend(
                [
                    "--baseline",
                    "approved-search-browser",
                    "1.0.0",
                    str(paths["reference"]),
                    str(paths["reference_artifact"]),
                ]
            )

            completed = subprocess.run(arguments, capture_output=True, text=True)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = parse_analysis(output.read_bytes(), paths["policy"].read_bytes())
            self.assertEqual(report["referenceArtifacts"][0]["id"], REFERENCE_ARTIFACT_ID)

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            paths = write_inputs(folder)
            output = folder / "analysis.json"
            output.write_bytes(b"existing")

            completed = subprocess.run(
                command(paths, output, with_reference=False), capture_output=True, text=True
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(output.read_bytes(), b"existing")

    def test_unpaired_reference_and_changed_candidate_fail_without_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            paths = write_inputs(folder)
            output = folder / "analysis.json"
            unpaired = command(paths, output, with_reference=False)
            unpaired.extend(["--reference", str(paths["reference"])])

            completed = subprocess.run(unpaired, capture_output=True, text=True)
            self.assertNotEqual(completed.returncode, 0)
            self.assertFalse(output.exists())

            paths["candidate"].write_bytes(paths["candidate"].read_bytes() + b" ")
            completed = subprocess.run(
                command(paths, output, with_reference=False), capture_output=True, text=True
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertFalse(output.exists())

    def test_invalid_producer_identity_fails_without_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            paths = write_inputs(folder)
            output = folder / "analysis.json"
            arguments = command(paths, output, with_reference=False)
            arguments[arguments.index(PRODUCER_IMAGE)] = "perfeng-analysis:latest"

            completed = subprocess.run(arguments, capture_output=True, text=True)

            self.assertNotEqual(completed.returncode, 0)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
