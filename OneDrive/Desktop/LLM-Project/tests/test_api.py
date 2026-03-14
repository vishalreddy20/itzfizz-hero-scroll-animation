from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

SAMPLE_CONTRACT = """
Master Services Agreement
This Agreement is effective January 1, 2025 between Alpha Corp and Beta LLC.
Either party may terminate for convenience upon 15 days' notice.
Supplier shall indemnify Customer for third-party claims.
The parties will comply with applicable confidentiality obligations.
Liability is unlimited for all claims.
""".strip()


class ContractIQApiTests(unittest.TestCase):
    def test_review_endpoint_local_mode(self) -> None:
        response = client.post(
            "/api/review",
            json={
                "contract_text": SAMPLE_CONTRACT,
                "jurisdiction": "Delaware",
                "contract_type": "MSA",
                "counterparty_type": "Vendor",
                "stance": "BALANCED",
                "audience": "Legal Counsel",
                "pipeline_mode": "local",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["pipeline_mode_used"], "local")
        self.assertIn("extraction", payload)
        self.assertIn("analysis", payload)
        self.assertIn("redlines", payload)
        self.assertIn("report_markdown", payload)
        self.assertIn("request_id", payload)
        self.assertIn("prompt_version", payload)

    @patch("app.services.orchestrator.run_prompt_review", side_effect=RuntimeError("prompt unavailable"))
    def test_review_endpoint_auto_falls_back_to_local(self, _mock_prompt_review) -> None:
        response = client.post(
            "/api/review",
            json={
                "contract_text": SAMPLE_CONTRACT,
                "pipeline_mode": "auto",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["pipeline_mode_used"], "local")

    @patch("app.main.ingest_playbook")
    def test_ingest_playbook_endpoint(self, mock_ingest_playbook) -> None:
        mock_ingest_playbook.return_value = {"playbook_rules": [{"rule_id": "PB001"}]}

        response = client.post(
            "/api/ingest/playbook",
            json={"raw_text": "Limitation of liability: cap at fees paid."},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["payload"]["playbook_rules"][0]["rule_id"], "PB001")

        response_cached = client.post(
            "/api/ingest/playbook",
            json={"raw_text": "Limitation of liability: cap at fees paid."},
        )
        self.assertEqual(response_cached.status_code, 200)
        self.assertTrue(response_cached.json()["payload"]["idempotent"])

    @patch("app.main.process_dataset_record")
    def test_process_dataset_record_endpoint(self, mock_process_dataset_record) -> None:
        mock_process_dataset_record.return_value = {
            "dataset_source": "custom",
            "total_records_processed": 1,
            "valid_clauses": [],
            "invalid_records": [],
            "processing_notes": "ok",
        }

        response = client.post(
            "/api/process-dataset-record",
            json={"dataset_record": "{\"clause\": \"Confidentiality survives termination.\"}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["payload"]["dataset_source"], "custom")

    @patch("app.main.ingest_cuad")
    def test_ingest_cuad_endpoint(self, mock_ingest_cuad) -> None:
        response = client.post("/api/ingest/cuad", json={"limit": 12})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["payload"]["records_requested"], 12)
        self.assertIn("job_id", response.json()["payload"])

    def test_readiness_endpoint(self) -> None:
        response = client.get("/api/ready")
        self.assertEqual(response.status_code, 200)
        self.assertIn(response.json()["status"], ["ready", "not-ready"])

    def test_review_async_endpoint_and_job_status(self) -> None:
        response = client.post(
            "/api/review-async",
            json={
                "contract_text": SAMPLE_CONTRACT,
                "pipeline_mode": "local",
            },
        )
        self.assertEqual(response.status_code, 200)
        job_id = response.json()["job_id"]

        # Poll for completion quickly in test environment.
        for _ in range(20):
            status = client.get(f"/api/jobs/{job_id}")
            self.assertEqual(status.status_code, 200)
            status_payload = status.json()
            if status_payload["status"] == "completed":
                self.assertIsNotNone(status_payload["result"])
                return

        self.fail("Async review job did not complete within expected polling window")


if __name__ == "__main__":
    unittest.main()
