"""Regression: read_scores_for_timeframes must return score_4h from SQLite."""

from __future__ import annotations

import sqlite3
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import score_worker

# Shared in-memory DB so two sync_db_session() blocks in read_scores_for_timeframes
# see the same data without Windows file-lock issues from temp files.
_MEM_DB_URI = "file:score_worker_4h_test?mode=memory&cache=shared"


class ReadScoresFourHourTests(unittest.TestCase):
    def setUp(self) -> None:
        self.keeper = sqlite3.connect(_MEM_DB_URI, uri=True)
        self.keeper.execute("DROP TABLE IF EXISTS technical_scores")
        self.keeper.execute(
            """
            CREATE TABLE technical_scores (
                symbol TEXT PRIMARY KEY,
                score_1m INTEGER,
                score_5m INTEGER,
                score_15m INTEGER,
                score_1h INTEGER,
                score_4h INTEGER,
                score_1d INTEGER,
                score_1w INTEGER,
                last_updated_utc TEXT
            )
            """
        )
        self.keeper.commit()

    def tearDown(self) -> None:
        self.keeper.close()

    def _insert_scores(
        self,
        symbol: str,
        scores: tuple[int | None, int | None, int | None, int | None, int | None, int | None, int | None],
    ) -> None:
        self.keeper.execute(
            """
            INSERT INTO technical_scores (
                symbol, score_1m, score_5m, score_15m, score_1h, score_4h,
                score_1d, score_1w, last_updated_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (symbol, *scores, "2026-01-01T00:00:00"),
        )
        self.keeper.commit()

    def _session(self):
        @contextmanager
        def _tmp_session(_path=None):
            c = sqlite3.connect(_MEM_DB_URI, uri=True)
            try:
                yield c
                c.commit()
            except Exception:
                c.rollback()
                raise
            finally:
                c.close()
        return _tmp_session

    def test_read_scores_for_timeframes_returns_4h_when_cached(self) -> None:
        self._insert_scores("AAPL", (10, 20, 30, 40, 72, 50, 60))
        with patch.object(score_worker, "sync_db_session", self._session()):
            rows = score_worker.read_scores_for_timeframes(["AAPL"], ["4h"])

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["symbol"], "AAPL")
        self.assertEqual(row["4h"], 72)
        self.assertEqual(row["status_4h"], "ok")
        self.assertIsNone(row.get("bars_4h"))

    def test_missing_scorable_score_reports_not_computed(self) -> None:
        with (
            patch.object(score_worker, "sync_db_session", self._session()),
            patch.object(
                score_worker,
                "inspect_symbol_timeframe",
                return_value={"status": "scorable", "bar_count": 120, "required_bars": 60},
            ),
        ):
            rows = score_worker.read_scores_for_timeframes(["AAPL"], ["1d"])

        row = rows[0]
        self.assertIsNone(row["1d"])
        self.assertEqual(row["status_1d"], "not_computed")
        self.assertEqual(row["bars_1d"], 120)

    def test_targeted_refresh_preserves_unrequested_scores(self) -> None:
        self._insert_scores("AAPL", (10, 20, 30, 40, 72, 50, 60))
        with (
            patch.object(score_worker, "sync_db_session", self._session()),
            patch.object(score_worker, "score_symbols", return_value={"AAPL": {"1h": 88}}),
        ):
            score_worker._compute_and_upsert_timeframes(["AAPL"], ["1h"])

        row = self.keeper.execute(
            """
            SELECT score_1m, score_5m, score_15m, score_1h, score_4h, score_1d, score_1w
            FROM technical_scores WHERE symbol = ?
            """,
            ("AAPL",),
        ).fetchone()
        self.assertEqual(row, (10, 20, 30, 88, 72, 50, 60))

    def test_parallel_scoring_splits_work_by_symbol(self) -> None:
        calls: list[tuple[str, ...]] = []

        def fake_score(symbols: list[str], timeframes: list[str]) -> dict[str, dict[str, int]]:
            calls.append(tuple(symbols))
            return {sym: {tf: 50 for tf in timeframes} for sym in symbols}

        with (
            patch.object(score_worker, "SCORE_MAX_WORKERS", 2),
            patch.object(score_worker, "score_symbols", side_effect=fake_score),
        ):
            result = score_worker._score_symbols_parallel(["AAPL", "MSFT", "NVDA"], ["1d"])

        self.assertEqual(set(result), {"AAPL", "MSFT", "NVDA"})
        self.assertEqual(len(calls), 2)
        self.assertEqual({sym for call in calls for sym in call}, {"AAPL", "MSFT", "NVDA"})

    def test_priority_symbols_include_watchlist_and_active_symbols(self) -> None:
        scorer = score_worker.TechnicalsScorer()
        scorer.set_symbols(["AAPL", "MSFT"])
        scorer.set_active_symbols(["MSFT", "NVDA"])

        self.assertEqual(scorer._priority_symbols(), ["AAPL", "MSFT", "NVDA"])

    def test_universe_batch_rotates_and_skips_priority_symbols(self) -> None:
        scorer = score_worker.TechnicalsScorer()
        scorer.set_universe(["AAPL", "MSFT", "NVDA", "TSLA", "META"])

        with patch.object(score_worker, "UNIVERSE_SCORE_BATCH_SIZE", 2):
            first = scorer._next_universe_batch({"AAPL"})
            second = scorer._next_universe_batch({"AAPL"})
            third = scorer._next_universe_batch({"AAPL"})

        self.assertEqual(first, ["MSFT", "NVDA"])
        self.assertEqual(second, ["TSLA", "META"])
        self.assertEqual(third, ["MSFT", "NVDA"])


if __name__ == "__main__":
    unittest.main()
