"""Diagnostic script: verify DailyIQ intraday bar timeframes are internally consistent.

Usage:
    cd backend && python tests/test_dailyiq_timeframe_integrity.py

Checks:
1. Raw DailyIQ payloads for intraday timeframes include timestamps, not date-only strings.
2. Parsed bars from dailyiq_provider preserve the requested timeframe.
3. The intra-session spacing for 1h/4h bars matches the requested timeframe
   instead of collapsing into daily spacing.
"""

from __future__ import annotations

import os
import statistics
import sys
from collections import Counter
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import dailyiq_provider
from env_loader import env_candidates, load_local_backend_env

LOADED_ENV_PATHS = load_local_backend_env()
ENV_CANDIDATES = env_candidates()

API_KEY = os.getenv("DAILYIQ_API_KEY")
BASE_URL = f"https://dailyiq.me/v1/{API_KEY}" if API_KEY else None
SYMBOL = os.getenv("DAILYIQ_TEST_SYMBOL", "AAPL").upper()

EXPECTED_HOURS = {
    "1h": 1.0,
    "4h": 4.0,
    "1d": 24.0,
}


def _fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    raise SystemExit(1)


def _pass(msg: str) -> None:
    print(f"[PASS] {msg}")


def _load_raw_items(timeframe: str, limit: int) -> list[dict]:
    if not BASE_URL:
        searched = "\n".join(f"  - {path}" for path in ENV_CANDIDATES)
        raise SystemExit(
            "DAILYIQ_API_KEY not found in environment or searched .env paths:\n"
            f"{searched}"
        )
    response = requests.get(
        f"{BASE_URL}/price-bars",
        params={"symbol": SYMBOL, "timeframe": timeframe, "limit": limit, "order": "asc"},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("items", [])


def _source_endpoint_diagnostics(target_timeframe: str, limit: int) -> str:
    candidate_specs = {
        "1h": [("15m", 15 * 60_000, 4), ("5m", 5 * 60_000, 12), ("1m", 60_000, 60)],
        "4h": [("15m", 15 * 60_000, 16), ("5m", 5 * 60_000, 48), ("1m", 60_000, 240)],
    }
    parts: list[str] = []
    for source_tf, step_ms, multiple in candidate_specs.get(target_timeframe, []):
        raw_limit = max(50, min(5000, limit * multiple + multiple * 4))
        raw_items = _load_raw_items(source_tf, raw_limit)
        raw_dates = [str(item.get("date_utc", "")) for item in raw_items if item.get("date_utc")]
        has_time = any("T" in value or " " in value for value in raw_dates)
        parsed = dailyiq_provider._items_to_bars(raw_items)
        has_spacing = dailyiq_provider._has_intraday_spacing(parsed, step_ms)
        parts.append(
            f"{source_tf}: items={len(raw_items)}, timed={'yes' if has_time else 'no'}, "
            f"intraday_spacing={'yes' if has_spacing else 'no'}"
        )
    return "; ".join(parts)


def _format_hours(hours: float) -> str:
    if abs(hours - round(hours)) < 1e-9:
        return f"{int(round(hours))}h"
    return f"{hours:.2f}h"


def _dominant_intraday_spacing_hours(bars: list[dict], expected_hours: float) -> float | None:
    if len(bars) < 2:
        return None
    deltas_h = [
        (bars[i]["time"] - bars[i - 1]["time"]) / 3_600_000
        for i in range(1, len(bars))
        if bars[i]["time"] > bars[i - 1]["time"]
    ]
    if not deltas_h:
        return None

    intraday_window = max(expected_hours * 3.0, expected_hours + 0.5)
    intraday_deltas = [round(delta, 2) for delta in deltas_h if delta <= intraday_window]
    if not intraday_deltas:
        return None

    counts = Counter(intraday_deltas)
    dominant, _ = counts.most_common(1)[0]
    return float(dominant)


def _validate_timeframe(timeframe: str, limit: int) -> None:
    expected_hours = EXPECTED_HOURS[timeframe]
    raw_items = _load_raw_items(timeframe, limit)
    if not raw_items:
        _fail(f"{timeframe}: raw DailyIQ payload returned no items")

    raw_dates = [str(item.get("date_utc", "")) for item in raw_items if item.get("date_utc")]
    if not raw_dates:
        _fail(f"{timeframe}: raw DailyIQ payload had no date_utc values")

    bars = dailyiq_provider.fetch_bars_from_dailyiq(SYMBOL, timeframe=timeframe, limit=limit, ttl_s=0)
    if not bars:
        extra = ""
        if timeframe in {"1h", "4h"}:
            extra = f" | lower-timeframe diagnostics: {_source_endpoint_diagnostics(timeframe, limit)}"
        _fail(f"{timeframe}: provider returned no parsed bars{extra}")

    raw_time_component_ok = True
    if timeframe in {"1h", "4h"}:
        timed_rows = [value for value in raw_dates if "T" in value or " " in value]
        if not timed_rows:
            raw_time_component_ok = False

    dominant_spacing = _dominant_intraday_spacing_hours(bars, expected_hours)
    if dominant_spacing is None:
        _fail(f"{timeframe}: unable to find any in-session bar spacing to validate")

    tolerance = 0.15 if timeframe != "1d" else 0.25
    if abs(dominant_spacing - expected_hours) > max(tolerance, expected_hours * tolerance):
        _fail(
            f"{timeframe}: dominant spacing was {_format_hours(dominant_spacing)} "
            f"(expected about {_format_hours(expected_hours)})"
        )

    first_ts = bars[0]["time"]
    last_ts = bars[-1]["time"]
    span_h = (last_ts - first_ts) / 3_600_000 if len(bars) >= 2 else 0.0
    median_volume = statistics.median(bar["volume"] for bar in bars)

    if timeframe in {"1h", "4h"}:
        if raw_time_component_ok:
            _pass(f"{timeframe}: raw DailyIQ payload includes time-of-day stamps")
        else:
            print(f"[WARN] {timeframe}: raw DailyIQ payload is date-only; provider must compensate")

    _pass(
        f"{timeframe}: {len(bars)} bars, dominant spacing {_format_hours(dominant_spacing)}, "
        f"span {_format_hours(span_h)}, median volume {median_volume:.0f}"
    )


def main() -> int:
    print(f"DailyIQ timeframe integrity check for {SYMBOL}")
    print("=" * 48)
    if LOADED_ENV_PATHS:
        print("Loaded .env paths:")
        for env_path in LOADED_ENV_PATHS:
            print(f"  - {env_path}")
        print()

    checks = [("1h", 120), ("4h", 120), ("1d", 120)]
    for timeframe, limit in checks:
        _validate_timeframe(timeframe, limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
