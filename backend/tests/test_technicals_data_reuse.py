from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import technicals


def _create_ohlcv_tables(conn: sqlite3.Connection) -> None:
    for table in ("ohlcv_1m", "ohlcv_5m", "ohlcv_15m", "ohlcv_1h", "ohlcv_4h", "ohlcv_1d"):
        conn.execute(
            f"""
            CREATE TABLE {table} (
                symbol TEXT NOT NULL,
                ts INTEGER NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                PRIMARY KEY (symbol, ts)
            )
            """
        )


def _insert_bars(
    conn: sqlite3.Connection,
    table: str,
    symbol: str,
    count: int,
    step_ms: int,
    *,
    start_ts: int = 1_700_000_000_000,
) -> None:
    conn.executemany(
        f"""
        INSERT INTO {table} (symbol, ts, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                symbol,
                start_ts + index * step_ms,
                100 + index * 0.1,
                101 + index * 0.1,
                99 + index * 0.1,
                100.5 + index * 0.1,
                1000 + index,
            )
            for index in range(count)
        ],
    )
    conn.commit()


class TechnicalsDataReuseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        _create_ohlcv_tables(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_derives_5m_and_15m_from_single_1m_load(self) -> None:
        _insert_bars(self.conn, "ohlcv_1m", "AAPL", 900, 60_000)

        bundle = technicals._load_symbol_bundle(self.conn, "AAPL", ["5m", "15m"])
        df_5m = technicals._load_df_from_bundle(bundle, "5m")
        df_15m = technicals._load_df_from_bundle(bundle, "15m")

        self.assertGreaterEqual(len(df_5m), technicals.MIN_BARS)
        self.assertGreaterEqual(len(df_15m), technicals.MIN_BARS)
        self.assertEqual(len(bundle.one_minute), 900)

    def test_uses_native_1h_and_4h_tables(self) -> None:
        _insert_bars(self.conn, "ohlcv_1h", "AAPL", 70, 60 * 60_000)
        _insert_bars(self.conn, "ohlcv_4h", "AAPL", 80, 4 * 60 * 60_000)

        bundle = technicals._load_symbol_bundle(self.conn, "AAPL", ["1h", "4h"])

        self.assertEqual(len(technicals._load_df_from_bundle(bundle, "1h")), 70)
        self.assertEqual(len(technicals._load_df_from_bundle(bundle, "4h")), 80)
        self.assertTrue(bundle.one_minute.empty)

    def test_derives_weekly_from_loaded_daily_frame(self) -> None:
        _insert_bars(self.conn, "ohlcv_1d", "AAPL", 420, 24 * 60 * 60_000)

        bundle = technicals._load_symbol_bundle(self.conn, "AAPL", ["1d", "1w"])
        df_1d = technicals._load_df_from_bundle(bundle, "1d")
        df_1w = technicals._load_df_from_bundle(bundle, "1w")

        self.assertEqual(len(df_1d), 200)
        self.assertGreaterEqual(len(df_1w), technicals.MIN_BARS)

    def test_falls_back_to_native_15m_when_1m_is_too_shallow(self) -> None:
        _insert_bars(self.conn, "ohlcv_1m", "AAPL", 120, 60_000)
        _insert_bars(self.conn, "ohlcv_15m", "AAPL", 75, 15 * 60_000)

        bundle = technicals._load_symbol_bundle(self.conn, "AAPL", ["15m"])
        df_15m = technicals._load_df_from_bundle(bundle, "15m")

        self.assertEqual(len(df_15m), 75)
        self.assertEqual(df_15m["ts"].iloc[0], 1_700_000_000_000)


if __name__ == "__main__":
    unittest.main()
