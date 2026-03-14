from __future__ import annotations

import json
import unittest
from pathlib import Path

from app.services.orchestrator import run_full_review


class ContractIQSnapshotTests(unittest.TestCase):
    def test_local_review_snapshot(self) -> None:
        root = Path(__file__).resolve().parents[1]
        snapshot_path = root / "tests" / "snapshots" / "local_review_snapshot.json"
        sample_path = root / "sample" / "sample_contract.txt"
        playbook_path = root / "playbook" / "company_legal_playbook_v1.md"
        output_dir = root / "output"

        expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
        contract_text = sample_path.read_text(encoding="utf-8")

        result = run_full_review(
            contract_text=contract_text,
            jurisdiction="Delaware",
            contract_type="MSA",
            counterparty_type="Vendor",
            stance="BALANCED",
            audience="Legal Counsel",
            playbook_path=playbook_path,
            output_dir=output_dir,
            pipeline_mode="local",
        )

        self.assertEqual(result["analysis"]["overall_contract_risk"], expected["overall_contract_risk"])
        self.assertGreaterEqual(len(result["extraction"]["clauses"]), expected["minimum_clause_count"])
        for section in expected["required_report_sections"]:
            self.assertIn(section, result["report_markdown"])


if __name__ == "__main__":
    unittest.main()
