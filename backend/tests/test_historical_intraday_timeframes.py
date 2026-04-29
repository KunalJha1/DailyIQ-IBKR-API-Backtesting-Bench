from __future__ import annotations

import asyncio
import tempfile
import time
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import dailyiq_provider
import db_utils
import historical
import technicals


class HistoricalIntradayTimeframeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "market.db"
        db_utils.DB_PATH = self.db_path
        db_utils._schema_ready = False
        historical._schema_initialized = False

    def tearDown(self) -> None:
        db_utils._schema_ready = False
        historical._schema_initialized = False
        self.tmpdir.cleanup()

    def test_normalize_bar_size_preserves_hourly_variants(self) -> None:
        self.assertEqual(historical._normalize_bar_size("1h"), "1h")
        self.assertEqual(historical._normalize_bar_size("1 hour"), "1h")
        self.assertEqual(historical._normalize_bar_size("60 mins"), "1h")
        self.assertEqual(historical._normalize_bar_size("4h"), "4h")
        self.assertEqual(historical._normalize_bar_size("4 hours"), "4h")
        self.assertEqual(historical._normalize_bar_size("240 min"), "4h")

    def test_write_and_read_hourly_bars_uses_hourly_tables(self) -> None:
        now_ms = int(time.time() * 1000)
        hour_ms = 3_600_000
        bars_1h = [
            {"time": now_ms - (2 * hour_ms), "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000.0},
            {"time": now_ms - hour_ms, "open": 100.5, "high": 102.0, "low": 100.0, "close": 101.5, "volume": 1200.0},
        ]
        bars_4h = [
            {"time": now_ms - (8 * hour_ms), "open": 200.0, "high": 205.0, "low": 198.0, "close": 204.0, "volume": 5000.0},
            {"time": now_ms - (4 * hour_ms), "open": 204.0, "high": 207.0, "low": 203.0, "close": 206.0, "volume": 4500.0},
        ]

        with db_utils.sync_db_session(self.db_path) as conn:
            historical._init_schema(conn)
            historical._write_bars(conn, "AAPL", bars_1h, "1h", source="dailyiq")
            historical._write_bars(conn, "AAPL", bars_4h, "4h", source="dailyiq")

            count_1h = conn.execute(
                "SELECT COUNT(*) FROM ohlcv_1h WHERE symbol = ?",
                ("AAPL",),
            ).fetchone()[0]
            count_4h = conn.execute(
                "SELECT COUNT(*) FROM ohlcv_4h WHERE symbol = ?",
                ("AAPL",),
            ).fetchone()[0]
            count_1m = conn.execute(
                "SELECT COUNT(*) FROM ohlcv_1m WHERE symbol = ?",
                ("AAPL",),
            ).fetchone()[0]

        self.assertEqual(count_1h, 2)
        self.assertEqual(count_4h, 2)
        self.assertEqual(count_1m, 0)

        cached_1h = historical.read_cached_series("AAPL", "1h", duration="30 D")
        cached_4h = historical.read_cached_series("AAPL", "4h", duration="365 D")

        self.assertEqual(cached_1h["count"], 2)
        self.assertEqual(cached_1h["bars"][0]["time"], bars_1h[0]["time"])
        self.assertEqual(cached_4h["count"], 2)
        self.assertEqual(cached_4h["bars"][1]["time"], bars_4h[1]["time"])

    def test_technicals_use_native_hourly_bars(self) -> None:
        now_ms = int(time.time() * 1000)
        hour_ms = 3_600_000
        start_ms = now_ms - (80 * hour_ms)
        bars_1h = [
            {
                "time": start_ms + i * hour_ms,
                "open": 100.0 + i * 0.1,
                "high": 101.0 + i * 0.1,
                "low": 99.0 + i * 0.1,
                "close": 100.5 + i * 0.1,
                "volume": 1000.0 + i,
            }
            for i in range(80)
        ]

        with db_utils.sync_db_session(self.db_path) as conn:
            historical._init_schema(conn)
            historical._write_bars(conn, "AAPL", bars_1h, "1h", source="dailyiq")
            inspection = technicals.inspect_symbol_timeframe(conn, "AAPL", "1h")

        self.assertEqual(inspection["status"], "scorable")
        self.assertEqual(inspection["bar_count"], 80)

    def test_yahoo_fallback_rolls_5m_bars_up_to_1h(self) -> None:
        now_ms = int(time.time() * 1000)
        base_ts = now_ms - (24 * 5 * 60_000)
        yahoo_5m_bars = []
        for index in range(24):
            yahoo_5m_bars.append({
                "time": base_ts + index * 5 * 60_000,
                "open": 100.0 + index,
                "high": 100.5 + index,
                "low": 99.5 + index,
                "close": 100.25 + index,
                "volume": 1000.0 + index,
            })

        async def fake_dailyiq(*args, **kwargs):
            return []

        async def fake_yahoo(*args, **kwargs):
            return yahoo_5m_bars

        with patch.object(dailyiq_provider, "fetch_bars_from_dailyiq_async", side_effect=fake_dailyiq):
            with patch.object(historical, "fetch_from_yahoo", side_effect=fake_yahoo):
                bars, source = asyncio.run(
                    historical.get_historical_bars(
                        "AAPL",
                        ib=None,
                        tws_connected=False,
                        duration="30 D",
                        bar_size="1h",
                    )
                )

        self.assertEqual(source, "yahoo")
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[0]["open"], 100.0)
        self.assertEqual(bars[0]["close"], 111.25)
        self.assertEqual(bars[1]["open"], 112.0)
        self.assertEqual(bars[1]["close"], 123.25)


if __name__ == "__main__":
    unittest.main()
