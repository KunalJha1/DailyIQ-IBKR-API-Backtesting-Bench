#!/usr/bin/env python3
"""Quick test for GET /v1/{key}/price/{symbol}"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("VITE_DAILYIQ_URL", "https://dailyiq.me")
API_KEY  = os.getenv("DAILYIQ_API_KEY", "")

SYMBOLS = ["HOOD"]


def fetch_price(symbol: str) -> dict:
    url = f"{BASE_URL}/v1/{API_KEY}/price/{symbol}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def print_quote(data: dict) -> None:
    sym   = data.get("symbol", "?")
    price = data.get("price")
    chg   = data.get("change")
    pct   = data.get("changePct")
    src   = data.get("source", "?")
    sess  = data.get("session", "?")
    ts    = data.get("updatedAtUtc")

    print(f"\n{'='*50}")
    print(f"  {sym}  ${price}  ({'+' if chg and chg >= 0 else ''}{chg}  {'+' if pct and pct >= 0 else ''}{pct}%)")
    print(f"  source: {src}  |  session: {sess}  |  updatedAtUtc: {ts}")

    for seg in ("preMarket", "regular", "afterHours", "overnight"):
        val = data.get(seg)
        if val is None:
            print(f"  {seg:12s}: null")
        else:
            print(f"  {seg:12s}: {json.dumps(val)}")


if __name__ == "__main__":
    if not API_KEY:
        raise SystemExit("DAILYIQ_API_KEY not set in .env")

    for sym in SYMBOLS:
        try:
            data = fetch_price(sym)
            print_quote(data)
        except requests.HTTPError as e:
            print(f"\n[{sym}] HTTP {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            print(f"\n[{sym}] Error: {e}")

    print()
