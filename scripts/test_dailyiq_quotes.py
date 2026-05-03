"""
DailyIQ Quote Accuracy Test
Hits /snapshot, /price, and /price/batch for each symbol and prints a
side-by-side comparison so you can see which endpoint gives the "wrong" price.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

# ── Config ──────────────────────────────────────────────────────────────────
API_KEY = os.getenv("DAILYIQ_API_KEY", "diq_c08531d69205a9c07623accda1fe89b7b067e6549e583b5a")
BASE    = f"https://dailyiq.me/v1/{API_KEY}"

SYMBOLS = ["AAPL", "MSFT", "NVDA", "SPY", "TSLA"]

RESET  = "\033[0m"
BOLD   = "\033[1m"
RED    = "\033[31m"
YELLOW = "\033[33m"
GREEN  = "\033[32m"
CYAN   = "\033[36m"
DIM    = "\033[2m"


def fmt_price(p) -> str:
    if p is None:
        return f"{DIM}None{RESET}"
    return f"{GREEN}{p:.2f}{RESET}"


def fmt_ts(ts) -> str:
    if not ts:
        return "?"
    try:
        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        age_s = int(time.time()) - int(ts)
        age = f"{age_s}s ago" if age_s < 3600 else f"{age_s // 60}m ago"
        return f"{dt.strftime('%H:%M:%S')} UTC  ({age})"
    except Exception:
        return str(ts)


def get(path: str, params: dict | None = None) -> dict | None:
    try:
        r = requests.get(f"{BASE}/{path}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  {RED}ERROR{RESET} GET /{path}: {e}")
        return None


def post(path: str, body: dict) -> dict | None:
    try:
        r = requests.post(f"{BASE}/{path}", json=body, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  {RED}ERROR{RESET} POST /{path}: {e}")
        return None


def print_section(title: str):
    print(f"\n{BOLD}{CYAN}{'─' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'─' * 60}{RESET}")


def test_snapshot(symbol: str):
    """GET /snapshot/{symbol} — used by fetch_quote_from_dailyiq()"""
    d = get(f"snapshot/{symbol}")
    if not d:
        return
    print(f"  {BOLD}/snapshot{RESET}  price={fmt_price(d.get('price'))}  "
          f"change={d.get('change')}  changePct={d.get('changePct')}%  "
          f"asofDate={YELLOW}{d.get('asofDate')}{RESET}")
    # asofDate being yesterday = stale price, this is the most common cause of wrong price


def test_price(symbol: str):
    """GET /price/{symbol} — session-aware endpoint"""
    d = get(f"price/{symbol}")
    if not d:
        return

    top_price  = d.get("price")
    session    = d.get("session", "unknown")
    source     = d.get("source", "?")
    updated_ts = d.get("updatedAtUtc")
    change     = d.get("change")
    change_pct = d.get("changePct")

    print(f"  {BOLD}/price{RESET}     price={fmt_price(top_price)}  "
          f"session={YELLOW}{session}{RESET}  source={source}  "
          f"updated={fmt_ts(updated_ts)}")
    print(f"           change={change}  changePct={change_pct}%")

    for sess_name in ("preMarket", "regular", "afterHours"):
        sess = d.get(sess_name)
        if sess:
            print(f"           {DIM}{sess_name:12s}{RESET}  "
                  f"open={fmt_price(sess.get('open'))}  "
                  f"high={fmt_price(sess.get('high'))}  "
                  f"low={fmt_price(sess.get('low'))}  "
                  f"close={fmt_price(sess.get('close'))}  "
                  f"change={sess.get('change')}  "
                  f"changePct={sess.get('changePct')}%")
        else:
            print(f"           {DIM}{sess_name:12s}  null{RESET}")

    overnight = d.get("overnight")
    if overnight:
        print(f"           {DIM}overnight     {RESET}  "
              f"change={overnight.get('change')}  "
              f"changePct={overnight.get('changePct')}%")
    else:
        print(f"           {DIM}overnight       null{RESET}")

    # Flag staleness
    if updated_ts:
        age_s = int(time.time()) - int(updated_ts)
        if age_s > 300:
            print(f"  {YELLOW}⚠ Data is {age_s}s old — may be stale{RESET}")

    # Detect if top-level price disagrees with the active session close
    active_sess = d.get(session, {}) if session in ("preMarket", "regular", "afterHours") else None
    if active_sess:
        sess_close = active_sess.get("close")
        if sess_close is not None and top_price is not None:
            delta = abs(float(top_price) - float(sess_close))
            if delta > 0.05:
                print(f"  {RED}⚠ Top-level price ({top_price}) differs from "
                      f"{session}.close ({sess_close}) by {delta:.4f}{RESET}")


def test_batch(symbols: list[str]):
    """POST /price/batch — what the watchlist uses"""
    d = post("price/batch", {"symbols": symbols})
    if not d:
        return
    print(f"\n  {'Symbol':<8}  {'Price':>8}  {'Session':<12}  {'Source':<14}  {'Updated'}")
    print(f"  {'─'*8}  {'─'*8}  {'─'*12}  {'─'*14}  {'─'*24}")
    for sym in symbols:
        row = d.get(sym)
        if not row:
            print(f"  {sym:<8}  {RED}missing{RESET}")
            continue
        price    = row.get("price")
        session  = row.get("session", "?")
        source   = row.get("source", "?")
        ts       = row.get("updatedAtUtc")
        print(f"  {sym:<8}  {fmt_price(price):>8}  {YELLOW}{session:<12}{RESET}  "
              f"{source:<14}  {fmt_ts(ts)}")


def test_snapshot_vs_price(symbol: str):
    """Side-by-side diff: does snapshot.price == price.price?"""
    snap  = get(f"snapshot/{symbol}")
    price = get(f"price/{symbol}")
    if not snap or not price:
        return

    snap_price  = snap.get("price")
    price_price = price.get("price")
    delta = abs(float(snap_price or 0) - float(price_price or 0))
    match = delta < 0.01

    flag = f"{GREEN}✓ match{RESET}" if match else f"{RED}✗ mismatch  Δ={delta:.4f}{RESET}"
    print(f"  {symbol:<6}  snapshot={fmt_price(snap_price)}  "
          f"price={fmt_price(price_price)}  asofDate={YELLOW}{snap.get('asofDate')}{RESET}  {flag}")


def test_bar_vs_quote(symbol: str):
    """Compare latest price-bar close against the quote price for each timeframe.

    This confirms whether what the chart would render (bar.close) matches
    the price the watchlist/quote component shows.
    """
    price_data = get(f"price/{symbol}")
    if not price_data:
        return

    quote_price = float(price_data.get("price") or 0)
    session     = str(price_data.get("session") or "")
    # "post" is an alias for afterHours on DailyIQ
    session     = "afterHours" if session == "post" else session
    reg_close   = float((price_data.get("regular") or {}).get("close") or 0)

    print(f"\n  {BOLD}{symbol}{RESET}  quote_price={fmt_price(quote_price)}  "
          f"regular_close={fmt_price(reg_close)}  session={YELLOW}{session}{RESET}")

    for tf, limit in [("1d", 50), ("15m", 50), ("5m", 50)]:
        bars_data = get("price-bars", {"symbol": symbol, "timeframe": tf,
                                       "limit": limit, "order": "desc"})
        if not bars_data:
            continue
        items = bars_data.get("items", [])
        if not items:
            print(f"    {DIM}{tf:4s}  no bars returned{RESET}")
            continue

        latest     = items[0]
        bar_close  = float(latest.get("close") or 0)
        bar_date   = latest.get("date_utc", "?")
        delta      = abs(quote_price - bar_close)

        # During regular hours, bar close should track quote closely.
        # After hours, bar close will be the regular session close — delta is expected.
        if session == "regular":
            threshold = 0.50   # live bars should be within 50c
        else:
            threshold = 99999  # after/pre-market: just show the delta, don't flag

        flag = (f"{GREEN}✓{RESET}" if delta <= threshold
                else f"{RED}✗ Δ={delta:.2f}{RESET}")

        # Extra: how far is bar_close from regular close?
        reg_delta = abs(reg_close - bar_close) if reg_close else None

        reg_delta_str = f"{reg_delta:.2f}" if reg_delta is not None else "?"
        print(f"    {tf:4s}  bar_close={fmt_price(bar_close)}  "
              f"date={YELLOW}{bar_date}{RESET}  "
              f"Δ_vs_quote={delta:.2f}  "
              f"Δ_vs_reg_close={reg_delta_str}  {flag}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{BOLD}DailyIQ Quote Accuracy Test{RESET}")
    print(f"API key: {API_KEY[:12]}…")
    print(f"Time:    {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")

    # ── 1. Snapshot vs Price side-by-side for all symbols ───────────────────
    print_section("1. Snapshot vs Price — side-by-side")
    for sym in SYMBOLS:
        test_snapshot_vs_price(sym)

    # ── 2. Full /price breakdown for each symbol (session detail) ───────────
    print_section("2. /price session breakdown (per symbol)")
    for sym in SYMBOLS:
        print(f"\n  {BOLD}{sym}{RESET}")
        test_snapshot(sym)
        test_price(sym)

    # ── 3. Batch endpoint (mimics watchlist) ────────────────────────────────
    print_section("3. /price/batch (watchlist path)")
    test_batch(SYMBOLS)

    # ── 4. Bar close vs Quote price (confirms chart vs watchlist alignment) ──
    print_section("4. Price-bar close vs Quote price (chart vs watchlist)")
    for sym in SYMBOLS:
        test_bar_vs_quote(sym)

    print(f"\n{DIM}Done.{RESET}\n")


if __name__ == "__main__":
    main()
