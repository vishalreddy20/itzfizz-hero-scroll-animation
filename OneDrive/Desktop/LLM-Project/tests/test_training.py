from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.legal_ml import clear_model_cache, predict_clause_risk
from training.train_legal_risk_model import DEFAULT_SEED_DATASET, train_and_save_model


class ContractIQTrainingTests(unittest.TestCase):
    def test_train_and_use_tfidf_legal_risk_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            metrics = train_and_save_model(dataset_paths=[DEFAULT_SEED_DATASET], output_dir=output_dir, backend="tfidf")

            self.assertTrue((output_dir / "legal_risk_model.joblib").exists())
            self.assertTrue((output_dir / "legal_risk_model_metrics.json").exists())
            self.assertGreater(metrics["training_examples"], 10)

            with patch.dict(
                os.environ,
                {
                    "CONTRACTIQ_LEGAL_MODEL_ENABLED": "true",
                    "CONTRACTIQ_LEGAL_MODEL_PATH": str(output_dir / "legal_risk_model.joblib"),
                    "CONTRACTIQ_LEGAL_MODEL_MIN_CONFIDENCE": "0.10",
                },
                clear=False,
            ):
                clear_model_cache()
                prediction = predict_clause_risk(
                    "Limitation of Liability",
                    "Provider liability is unlimited for all direct, indirect, and consequential damages.",
                )

            self.assertIsNotNone(prediction)
            assert prediction is not None
            self.assertEqual(prediction.label, "CRITICAL")


if __name__ == "__main__":
    unittest.main()