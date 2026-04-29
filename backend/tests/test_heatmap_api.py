from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db_utils
import main
from fastapi.testclient import TestClient

_HEATMAP_ENRICH_MEM_URI = "file:heatmap_enrich_tech_scores?mode=memory&cache=shared"


class HeatmapApiTests(unittest.TestCase):
    def test_enrich_with_tech_scores_maps_all_expected_timeframes(self) -> None:
        with sqlite3.connect(_HEATMAP_ENRICH_MEM_URI, uri=True) as conn:
            conn.execute(
                """
                CREATE TABLE technical_scores (
                    symbol TEXT PRIMARY KEY,
                    score_1m INTEGER,
                    score_5m INTEGER,
                    score_15m INTEGER,
                    score_1h INTEGER,
                    score_4h INTEGER,
                    score_1d INTEGER,
                    score_1w INTEGER
                )
                """
            )
            conn.execute(
                """
                INSERT INTO technical_scores (
                    symbol, score_1m, score_5m, score_15m, score_1h, score_4h, score_1d, score_1w
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("AAPL", 10, 20, 30, 40, 45, 50, 60),
            )
            payloads = [{"symbol": "AAPL"}]
            main._enrich_with_tech_scores(conn, payloads)

        self.assertEqual(
            payloads[0]["techScores"],
            {"1m": 10, "5m": 20, "15m": 30, "1h": 40, "4h": 45, "1d": 50, "1w": 60},
        )
        self.assertEqual(payloads[0]["techScore1d"], 50)
        self.assertEqual(payloads[0]["techScore1w"], 60)

    def test_enrich_with_tech_scores_handles_short_rows(self) -> None:
        class _Cursor:
            def fetchall(self) -> list[tuple]:
                return [("AAPL", 10, 20, 30)]

        class _Conn:
            def execute(self, *_args, **_kwargs) -> _Cursor:
                return _Cursor()

        payloads = [{"symbol": "AAPL"}]
        main._enrich_with_tech_scores(_Conn(), payloads)

        self.assertEqual(
            payloads[0]["techScores"],
            {"1m": 10, "5m": 20, "15m": 30, "1h": None, "4h": None, "1d": None, "1w": None},
        )
        self.assertIsNone(payloads[0]["techScore1d"])
        self.assertIsNone(payloads[0]["techScore1w"])


class HeatmapGroupApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "market.db"
        db_utils._schema_ready = False
        self.db_patch = patch.object(db_utils, "DB_PATH", self.db_path)
        self.main_db_patch = patch.object(main, "sync_db_session", db_utils.sync_db_session)
        self.run_db_patch = patch.object(main, "run_db", db_utils.run_db)
        self.db_patch.start()
        self.main_db_patch.start()
        self.run_db_patch.start()
        self._test_client_cm = TestClient(main.create_app())
        self.client = self._test_client_cm.__enter__()
        db_utils._schema_ready = False
        with db_utils.sync_db_session(self.db_path):
            pass

    def tearDown(self) -> None:
        self._test_client_cm.__exit__(None, None, None)
        self.run_db_patch.stop()
        self.main_db_patch.stop()
        self.db_patch.stop()
        db_utils._schema_ready = False
        self.tmpdir.cleanup()

    def test_custom_group_create_normalizes_symbols_and_lists_group(self) -> None:
        response = self.client.post("/heatmap/groups", json={
            "name": " Semis ",
            "type": "custom",
            "etf_symbol": "SPY",
            "symbols": [" nvda ", "AMD", "nvda", "BRK.B"],
        })

        self.assertEqual(response.status_code, 200)
        created = response.json()
        self.assertEqual(created["name"], "Semis")
        self.assertEqual(created["type"], "custom")
        self.assertIsNone(created["etfSymbol"])
        self.assertEqual(created["symbols"], ["NVDA", "AMD", "BRK.B"])
        self.assertIn("createdAt", created)
        self.assertIn("updatedAt", created)

        listed = self.client.get("/heatmap/groups")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["groups"], [created])

    def test_custom_group_rejects_empty_symbol_list(self) -> None:
        response = self.client.post("/heatmap/groups", json={
            "name": "Empty",
            "type": "custom",
            "symbols": [],
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Custom groups require at least one symbol.")

    def test_sector_group_create_persists_resolved_symbols(self) -> None:
        response = self.client.post("/heatmap/groups", json={
            "name": "Technology",
            "type": "sector",
            "symbols": ["AAPL", "MSFT", "AAPL"],
        })

        self.assertEqual(response.status_code, 200)
        created = response.json()
        self.assertEqual(created["name"], "Technology")
        self.assertEqual(created["type"], "sector")
        self.assertIsNone(created["etfSymbol"])
        self.assertEqual(created["symbols"], ["AAPL", "MSFT"])

    def test_update_group_clears_fields_for_non_custom_types(self) -> None:
        created = self.client.post("/heatmap/groups", json={
            "name": "Semis",
            "type": "custom",
            "symbols": ["NVDA", "AMD"],
        }).json()

        response = self.client.put(f"/heatmap/groups/{created['id']}", json={
            "name": "My Watchlist",
            "type": "watchlist",
            "etf_symbol": "QQQ",
            "symbols": ["AAPL"],
        })

        self.assertEqual(response.status_code, 200)
        updated = response.json()
        self.assertEqual(updated["id"], created["id"])
        self.assertEqual(updated["name"], "My Watchlist")
        self.assertEqual(updated["type"], "watchlist")
        self.assertIsNone(updated["etfSymbol"])
        self.assertIsNone(updated["symbols"])
        self.assertEqual(updated["createdAt"], created["createdAt"])
        self.assertGreaterEqual(updated["updatedAt"], created["updatedAt"])


if __name__ == "__main__":
    unittest.main()
