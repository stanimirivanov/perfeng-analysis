import hashlib
import unittest
from typing import Any

from test_comparator import REFERENCE_ARTIFACT_ID, reference_result
from test_evaluator import RUN_ID, encode, fixture, normalized_result

from perfeng_analysis import build_analysis_report

CANDIDATE_ARTIFACT_ID = "44444444-4444-4444-8444-444444444444"


def artifact(data: bytes, run_id: str, artifact_id: str) -> dict[str, Any]:
    return {
        "id": artifact_id,
        "runId": run_id,
        "kind": "normalized",
        "uri": f"s3://perfeng-example/runs/{run_id}/normalized/result.json",
        "sha256": hashlib.sha256(data).hexdigest(),
        "sizeBytes": len(data),
        "mediaType": "application/json",
        "format": "normalized-result/v1",
    }


def producer() -> dict[str, Any]:
    return {
        "name": "perfeng-analysis",
        "version": "0.5.0",
        "image": "ghcr.io/example/perfeng-analysis@sha256:" + "d" * 64,
    }


def build_without_reference() -> dict[str, Any]:
    candidate = encode(normalized_result())
    return build_analysis_report(
        candidate,
        artifact(candidate, RUN_ID, CANDIDATE_ARTIFACT_ID),
        fixture("policy/browser.json"),
        producer=producer(),
        created_at="2026-09-02T13:02:00Z",
    )


class ReportTests(unittest.TestCase):
    def test_builds_valid_nonblocking_report_without_a_reference(self):
        report = build_without_reference()

        self.assertEqual(report["schemaVersion"], 1)
        self.assertEqual(report["kind"], "AnalysisResult")
        self.assertEqual(report["runId"], RUN_ID)
        self.assertFalse(report["blocking"])
        self.assertEqual(report["referenceArtifacts"], [])
        self.assertEqual(report["evaluations"][0]["slo"]["status"], "PASS")
        self.assertEqual(report["evaluations"][0]["regression"]["status"], "INCONCLUSIVE")
        self.assertEqual(report["evaluations"][0]["regression"]["candidateValue"], 140)
        self.assertEqual(
            report["policy"]["sha256"], hashlib.sha256(fixture("policy/browser.json")).hexdigest()
        )

    def test_builds_report_with_verified_reference_and_regression(self):
        candidate = encode(normalized_result())
        reference_document = reference_result()
        reference_document["measurementWindow"] = {
            "start": "2026-09-01T13:00:00Z",
            "end": "2026-09-01T13:01:00Z",
        }
        reference_document["createdAt"] = "2026-09-01T13:01:01Z"
        reference = encode(reference_document)
        reference_claim = artifact(reference, reference_document["runId"], REFERENCE_ARTIFACT_ID)

        report = build_analysis_report(
            candidate,
            artifact(candidate, RUN_ID, CANDIDATE_ARTIFACT_ID),
            fixture("policy/browser.json"),
            producer=producer(),
            created_at="2026-09-02T13:02:00Z",
            reference_data=reference,
            reference_artifact=reference_claim,
        )

        self.assertEqual(report["referenceArtifacts"], [reference_claim])
        self.assertEqual(report["evaluations"][0]["regression"]["status"], "FAIL")
        self.assertEqual(
            report["evaluations"][0]["regression"]["referenceArtifactId"],
            REFERENCE_ARTIFACT_ID,
        )

    def test_reference_bytes_and_artifact_must_be_supplied_together(self):
        candidate = encode(normalized_result())
        candidate_claim = artifact(candidate, RUN_ID, CANDIDATE_ARTIFACT_ID)

        with self.assertRaisesRegex(ValueError, "supplied together"):
            build_analysis_report(
                candidate,
                candidate_claim,
                fixture("policy/browser.json"),
                producer=producer(),
                created_at="2026-09-02T13:02:00Z",
                reference_data=encode(reference_result()),
            )

    def test_artifact_size_and_checksum_bind_the_exact_bytes(self):
        candidate = encode(normalized_result())
        candidate_claim = artifact(candidate, RUN_ID, CANDIDATE_ARTIFACT_ID)
        candidate_claim["sizeBytes"] += 1
        with self.assertRaisesRegex(ValueError, "size does not match"):
            build_analysis_report(
                candidate,
                candidate_claim,
                fixture("policy/browser.json"),
                producer=producer(),
                created_at="2026-09-02T13:02:00Z",
            )

        candidate_claim = artifact(candidate, RUN_ID, CANDIDATE_ARTIFACT_ID)
        candidate_claim["sha256"] = "e" * 64
        with self.assertRaisesRegex(ValueError, "checksum does not match"):
            build_analysis_report(
                candidate,
                candidate_claim,
                fixture("policy/browser.json"),
                producer=producer(),
                created_at="2026-09-02T13:02:00Z",
            )

    def test_reference_artifact_run_matches_the_reference_document(self):
        candidate = encode(normalized_result())
        reference = encode(reference_result())
        reference_claim = artifact(
            reference, "perf-20260831-130000-deadbeef", REFERENCE_ARTIFACT_ID
        )

        with self.assertRaisesRegex(ValueError, "run does not match"):
            build_analysis_report(
                candidate,
                artifact(candidate, RUN_ID, CANDIDATE_ARTIFACT_ID),
                fixture("policy/browser.json"),
                producer=producer(),
                created_at="2026-09-02T13:02:00Z",
                reference_data=reference,
                reference_artifact=reference_claim,
            )

    def test_report_cannot_predate_its_normalized_inputs(self):
        candidate = encode(normalized_result())

        with self.assertRaisesRegex(ValueError, "cannot predate"):
            build_analysis_report(
                candidate,
                artifact(candidate, RUN_ID, CANDIDATE_ARTIFACT_ID),
                fixture("policy/browser.json"),
                producer=producer(),
                created_at="2026-09-02T13:00:30Z",
            )

    def test_returned_report_does_not_alias_caller_metadata(self):
        candidate = encode(normalized_result())
        candidate_claim = artifact(candidate, RUN_ID, CANDIDATE_ARTIFACT_ID)
        producer_claim = producer()
        report = build_analysis_report(
            candidate,
            candidate_claim,
            fixture("policy/browser.json"),
            producer=producer_claim,
            created_at="2026-09-02T13:02:00Z",
        )

        candidate_claim["uri"] = "s3://changed/result.json"
        producer_claim["name"] = "changed"
        self.assertNotEqual(report["candidateArtifact"]["uri"], candidate_claim["uri"])
        self.assertNotEqual(report["producer"]["name"], producer_claim["name"])

    def test_inconclusive_candidate_quality_is_preserved_without_reference(self):
        candidate_document = normalized_result()
        candidate_document["results"][0]["distribution"]["samples"] = 1
        candidate = encode(candidate_document)
        report = build_analysis_report(
            candidate,
            artifact(candidate, RUN_ID, CANDIDATE_ARTIFACT_ID),
            fixture("policy/browser.json"),
            producer=producer(),
            created_at="2026-09-02T13:02:00Z",
        )

        self.assertEqual(report["evaluations"][0]["quality"]["status"], "INCONCLUSIVE")
        self.assertEqual(report["evaluations"][0]["regression"]["status"], "INCONCLUSIVE")
        self.assertIn("quality did not pass", report["evaluations"][0]["regression"]["reasons"][0])


if __name__ == "__main__":
    unittest.main()
