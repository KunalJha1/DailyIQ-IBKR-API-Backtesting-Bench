from __future__ import annotations

import unittest
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import dailyiq_provider


def _make_items(count: int, step_minutes: int) -> list[dict]:
    base_ts_ms = 1_710_000_000_000
    items: list[dict] = []
    for index in range(count):
        ts_ms = base_ts_ms + index * step_minutes * 60_000
        iso = dailyiq_provider.datetime.fromtimestamp(
            ts_ms / 1000,
            tz=dailyiq_provider.timezone.utc,
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        price = 100.0 + index
        items.append({
            "date_utc": iso,
            "open": price,
            "high": price + 0.5,
            "low": price - 0.5,
            "close": price + 0.25,
            "volume": 1000 + index,
        })
    return items


class DailyIQProviderTimeframeTests(unittest.TestCase):
    def test_watchlist_quotes_use_bulk_price_endpoint(self) -> None:
        payload = {
            "AAPL": {
                "symbol": "AAPL",
                "price": 201.5,
                "change": 3.5,
                "changePct": 1.77,
                "sentimentScore": 64,
                "source": "ibkr_live",
                "session": "regular",
                "regular": {
                    "open": 198.0,
                    "high": 202.0,
                    "low": 197.5,
                    "close": 201.5,
                    "change": 3.5,
                    "changePct": 1.77,
                },
            },
            "MSFT": {
                "symbol": "MSFT",
                "price": 0,
                "change": 0,
                "changePct": 0,
                "source": "ibkr_live",
                "session": "regular",
                "regular": {
                    "open": 0,
                    "high": 0,
                    "low": 0,
                    "close": 0,
                    "change": 0,
                    "changePct": 0,
                },
            },
        }

        with (
            patch.object(dailyiq_provider, "_dailyiq_post_json", return_value=payload) as mock_post,
            patch.object(dailyiq_provider, "_write_sentiment_score_cache") as mock_sentiment_cache,
        ):
            quotes = dailyiq_provider.fetch_watchlist_quotes_from_dailyiq(["AAPL", "MSFT"])

        self.assertEqual(mock_post.call_args.args[0], "price/batch")
        self.assertEqual(mock_post.call_args.kwargs["json_body"], {"symbols": ["AAPL", "MSFT"]})
        self.assertEqual(len(quotes), 1)
        self.assertEqual(quotes[0]["symbol"], "AAPL")
        self.assertEqual(quotes[0]["last"], 201.5)
        self.assertEqual(quotes[0]["open"], 198.0)
        self.assertEqual(quotes[0]["high"], 202.0)
        self.assertEqual(quotes[0]["low"], 197.5)
        self.assertEqual(quotes[0]["prev_close"], 198.0)
        self.assertEqual(quotes[0]["source"], "ibkr_live")
        self.assertEqual(quotes[0]["sentimentScore"], 64)
        mock_sentiment_cache.assert_called_once_with("AAPL", 64)

    def test_snapshot_refresh_is_used_for_missing_sentiment(self) -> None:
        def fake_quote(symbol: str) -> dict:
            return {
                "symbol": symbol,
                "last": 100,
                "sentimentScore": 70 if symbol == "AAPL" else 55,
            }

        with (
            patch.object(dailyiq_provider, "fetch_quote_from_dailyiq", side_effect=fake_quote) as mock_snapshot,
            patch.object(
                dailyiq_provider,
                "fetch_sentiment_scores_from_cache",
                return_value={"AAPL": 70, "MSFT": 55},
            ) as mock_cache,
        ):
            scores = dailyiq_provider.refresh_sentiment_scores_from_snapshots(["AAPL", "MSFT"])

        self.assertEqual(scores, {"AAPL": 70, "MSFT": 55})
        self.assertEqual({call.args[0] for call in mock_snapshot.call_args_list}, {"AAPL", "MSFT"})
        mock_cache.assert_called_once_with(["AAPL", "MSFT"])

    def test_fundamentals_parse_forward_pe_from_dailyiq(self) -> None:
        payload = {
            "symbol": "AAPL",
            "asofDate": "2025-03-28",
            "peRatio": 34.1,
            "forwardPe": 28.4,
            "forwardPeSource": "yahoo",
            "high52w": 237.23,
            "low52w": 164.08,
            "marketCap": {"usd": 3_251_400_000_000, "display": "3251.40B"},
        }

        with patch.object(dailyiq_provider, "_dailyiq_get_json", return_value=payload) as mock_get:
            trailing_pe, forward_pe, market_cap = dailyiq_provider.fetch_fundamentals_from_dailyiq("AAPL")

        self.assertEqual(trailing_pe, 34.1)
        self.assertEqual(forward_pe, 28.4)
        self.assertEqual(market_cap, 3_251_400_000_000)
        mock_get.assert_called_once_with(
            "fundamentals/AAPL",
            params={"units": "B"},
            ttl_s=dailyiq_provider.CACHE_TTL_FUNDAMENTALS,
        )

    def test_fundamentals_parse_tsm_market_cap_display(self) -> None:
        payload = {
            "peRatio": 26.4,
            "forwardPe": 22.1,
            "marketCapDisplay": "1.98T",
        }

        with patch.object(dailyiq_provider, "_dailyiq_get_json", return_value=payload):
            _, _, market_cap = dailyiq_provider.fetch_fundamentals_from_dailyiq("TSM")

        self.assertEqual(market_cap, 1_980_000_000_000)

    def test_fundamentals_scale_tsm_billion_market_cap_to_usd(self) -> None:
        payload = {
            "peRatio": 26.4,
            "forwardPe": 22.1,
            "marketCap": 1_984.2,
        }

        with patch.object(dailyiq_provider, "_dailyiq_get_json", return_value=payload):
            _, _, market_cap = dailyiq_provider.fetch_fundamentals_from_dailyiq("TSM")

        self.assertEqual(market_cap, 1_984_200_000_000)

    def test_fundamentals_use_tsm_public_market_cap_for_bad_provider_value(self) -> None:
        payload = {
            "peRatio": 26.4,
            "forwardPe": 22.1,
            "marketCap": 325_000_000,
        }

        with patch.object(dailyiq_provider, "_dailyiq_get_json", return_value=payload):
            _, _, market_cap = dailyiq_provider.fetch_fundamentals_from_dailyiq("TSM")

        self.assertEqual(market_cap, dailyiq_provider.TSM_STANDARD_MARKET_CAP_USD)

    def test_fundamentals_use_tsm_public_market_cap_when_missing(self) -> None:
        payload = {
            "peRatio": 26.4,
            "forwardPe": 22.1,
        }

        with patch.object(dailyiq_provider, "_dailyiq_get_json", return_value=payload):
            _, _, market_cap = dailyiq_provider.fetch_fundamentals_from_dailyiq("TSM")

        self.assertEqual(market_cap, dailyiq_provider.TSM_STANDARD_MARKET_CAP_USD)

    def test_items_to_bars_prefers_ts_utc_over_date_utc(self) -> None:
        bars = dailyiq_provider._items_to_bars([
            {
                "ts_utc": 1_710_000_000,
                "date_utc": "2026-04-01",
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100.5,
                "volume": 1000,
            }
        ])

        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0]["time"], 1_710_000_000 * 1000)

    def test_hourly_fetch_falls_back_to_5m_rollup(self) -> None:
        broken_15m = [{"date_utc": "2026-04-01", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}] * 24
        items_5m = _make_items(24, step_minutes=5)

        def fake_get_json(endpoint: str, params: dict | None = None, **_: object) -> dict:
            if params and params.get("timeframe") == "15m":
                return {"items": broken_15m}
            if params and params.get("timeframe") == "5m":
                return {"items": items_5m}
            return {"items": []}

        with patch.object(dailyiq_provider, "_dailyiq_get_json", side_effect=fake_get_json) as mock_get:
            bars = dailyiq_provider.fetch_bars_from_dailyiq("AAPL", timeframe="1h", limit=10, ttl_s=0)

        self.assertEqual(len(bars), 2)
        requested_timeframes = [call.kwargs["params"]["timeframe"] for call in mock_get.call_args_list]
        self.assertEqual(requested_timeframes[:2], ["15m", "5m"])
        self.assertEqual(bars[0]["time"], dailyiq_provider._parse_date_to_ms(items_5m[0]["date_utc"]))
        self.assertEqual(bars[0]["open"], 100.0)
        self.assertEqual(bars[0]["close"], 111.25)
        self.assertEqual(bars[0]["high"], 111.5)
        self.assertEqual(bars[0]["low"], 99.5)
        self.assertEqual(bars[0]["volume"], sum(1000 + index for index in range(12)))

    def test_four_hour_fetch_falls_back_to_5m_rollup(self) -> None:
        broken_15m = [{"date_utc": "2026-04-01", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}] * 60
        items_5m = _make_items(60, step_minutes=5)

        def fake_get_json(endpoint: str, params: dict | None = None, **_: object) -> dict:
            if params and params.get("timeframe") == "15m":
                return {"items": broken_15m}
            if params and params.get("timeframe") == "5m":
                return {"items": items_5m}
            return {"items": []}

        with patch.object(dailyiq_provider, "_dailyiq_get_json", side_effect=fake_get_json) as mock_get:
            bars = dailyiq_provider.fetch_bars_from_dailyiq("AAPL", timeframe="4h", limit=10, ttl_s=0)

        self.assertEqual(len(bars), 2)
        requested_timeframes = [call.kwargs["params"]["timeframe"] for call in mock_get.call_args_list]
        self.assertEqual(requested_timeframes[:2], ["15m", "5m"])
        self.assertEqual(bars[0]["open"], 100.0)
        self.assertEqual(bars[0]["close"], 147.25)
        self.assertEqual(bars[1]["open"], 148.0)
        self.assertEqual(bars[1]["close"], 159.25)


if __name__ == "__main__":
    unittest.main()
