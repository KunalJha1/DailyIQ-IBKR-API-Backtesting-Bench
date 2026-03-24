from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main


class FinnhubSettingsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.settings_path = Path(self.tmpdir.name) / "tws-settings.json"
        self.settings_path.write_text(
            json.dumps(
                {
                    "clientId": 1234,
                    "autoProbe": True,
                    "finnhubApiKey": "existing-key",
                    "finnhubConnected": True,
                    "finnhubStatusMessage": "Finnhub validated with AAPL",
                    "finnhubValidatedAt": 1111,
                }
            ),
            encoding="utf-8",
        )
        self.settings_patch = patch.object(main, "SETTINGS_PATH", self.settings_path)
        self.settings_patch.start()
        self.client = TestClient(main.create_app())

    def tearDown(self) -> None:
        self.settings_patch.stop()
        self.tmpdir.cleanup()

    def test_status_reports_saved_key(self) -> None:
        response = self.client.get("/settings/finnhub/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "connected")
        self.assertTrue(response.json()["hasKey"])

    def test_failed_validation_does_not_overwrite_saved_key(self) -> None:
        with patch.object(main, "_validate_finnhub_key", return_value=(False, "bad key")):
            response = self.client.post("/settings/finnhub/validate", json={"apiKey": "broken"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["status"], "connected")
        saved = json.loads(self.settings_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["finnhubApiKey"], "existing-key")

    def test_successful_validation_persists_new_key(self) -> None:
        with patch.object(main, "_validate_finnhub_key", return_value=(True, "Finnhub validated with AAPL")):
            response = self.client.post("/settings/finnhub/validate", json={"apiKey": "new-good-key"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["status"], "connected")
        saved = json.loads(self.settings_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["finnhubApiKey"], "new-good-key")
        self.assertTrue(saved["finnhubConnected"])


if __name__ == "__main__":
    unittest.main()
