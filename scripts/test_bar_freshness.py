"""
Bar Freshness Diagnostic
Checks every hop in the chain to find where the 15-20 min lag lives:
  1. DailyIQ cloud /price-bars  — what ts_utc does the DB actually have?
  2. DailyIQ cloud /price-bars/refresh — what does lastBarTsUtc come back as?
  3. Local sidecar /historical  — what does the chart actually get served?
"""

import os
import sys
import time
from datetime import datetime, timezone

import requests

# ── Config ────────────────────────────────────────────────────────────────────
API_KEY       = os.getenv("DAILYIQ_API_KEY", "diq_c08531d69205a9c07623accda1fe89b7b067e6549e583b5a")
DIQ_BASE      = f"https://dailyiq.me/v1/{API_KEY}"
LOCAL_BASE    = f"http://127.0.0.1:{os.getenv('SIDECAR_PORT', '18100')}"
SYMBOLS       = ["AAPL", "SPY", "TSLA"]
TIMEFRAME     = "1m"
NOW           = int(time.time())

RESET  = "\033[0m"
BOLD   = "\033[1m"
RED    = "\033[31m"
YELLOW = "\033[33m"
GREEN  = "\033[32m"
CYAN   = "\033[36m"
DIM    = "\033[2m"


def age_str(ts: int | None) -> str:
    if not ts:
        return f"{DIM}?{RESET}"
    age = NOW - int(ts)
    if age < 0:
        return f"{GREEN}future (+{-age}s){RESET}"
    color = GREEN if age < 90 else (YELLOW if age < 600 else RED)
    m, s = divmod(age, 60)
    label = f"{m}m {s}s ago" if m else f"{s}s ago"
    return f"{color}{label}{RESET}"


def ts_str(ts: int | None) -> str:
    if not ts:
        return f"{DIM}None{RESET}"
    dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
    return f"{YELLOW}{dt.strftime('%H:%M:%S')} UTC{RESET}"


def sep(title: str):
    print(f"\n{BOLD}{CYAN}{'─'*60}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'─'*60}{RESET}")


# ── 1. DailyIQ cloud /price-bars  ────────────────────────────────────────────
sep("1. DailyIQ cloud /price-bars (last 5 bars, desc)")
for sym in SYMBOLS:
    try:
        r = requests.get(
            f"{DIQ_BASE}/price-bars",
            params={"symbol": sym, "timeframe": TIMEFRAME, "limit": 50, "order": "desc"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        items = data.get("items", [])
        print(f"\n  {BOLD}{sym}{RESET}  ({len(items)} bars returned, showing last 5)")
        for item in items[-5:]:
            ts    = item.get("ts_utc")
            close = item.get("close")
            fetched = item.get("fetched_at_utc")
            print(f"    bar_ts={ts_str(ts)}  {age_str(ts)}  "
                  f"close={BOLD}{close}{RESET}  "
                  f"fetched_at={ts_str(fetched)}  (fetch lag: {age_str(fetched)})")
    except Exception as e:
        print(f"  {RED}ERROR {sym}: {e}{RESET}")


# ── 2. DailyIQ cloud /price-bars/refresh  ────────────────────────────────────
sep("2. DailyIQ cloud /price-bars/refresh (force refresh, wait 3s)")
for sym in SYMBOLS:
    try:
        r = requests.post(
            f"{DIQ_BASE}/price-bars/refresh",
            params={"symbol": sym, "timeframe": TIMEFRAME, "maxWaitMs": 3000},
            timeout=8,
        )
        r.raise_for_status()
        d = r.json()
        last_bar_ts     = d.get("lastBarTsUtc")
        last_fetched_ts = d.get("lastFetchedAtUtc")
        status          = d.get("status")
        rows            = d.get("rowsUpserted")
        ok              = d.get("ok")
        color = GREEN if ok else RED
        print(f"\n  {BOLD}{sym}{RESET}  status={YELLOW}{status}{RESET}  ok={color}{ok}{RESET}  rowsUpserted={rows}")
        print(f"    lastBarTsUtc    = {ts_str(last_bar_ts)}  {age_str(last_bar_ts)}")
        print(f"    lastFetchedAtUtc= {ts_str(last_fetched_ts)}  {age_str(last_fetched_ts)}")
        if last_bar_ts and last_fetched_ts:
            ibkr_lag = int(last_fetched_ts) - int(last_bar_ts)
            color2 = GREEN if ibkr_lag < 120 else (YELLOW if ibkr_lag < 600 else RED)
            print(f"    ibkr_lag (fetched - lastBar) = {color2}{ibkr_lag}s ({ibkr_lag//60}m {ibkr_lag%60}s){RESET}")
    except Exception as e:
        print(f"  {RED}ERROR {sym}: {e}{RESET}")


# ── 3. Local sidecar /historical  ────────────────────────────────────────────
sep("3. Local sidecar /historical (last 5 bars, prefer_live_refresh=1)")
for sym in SYMBOLS:
    try:
        r = requests.get(
            f"{LOCAL_BASE}/historical",
            params={
                "symbol": sym,
                "bar_size": "1 min",
                "limit": 5,
                "prefer_live_refresh": "1",
            },
            timeout=12,
        )
        r.raise_for_status()
        data = r.json()
        bars   = data.get("bars", [])
        source = data.get("source", "?")
        ts_max_raw = data.get("ts_max")
        ts_max = (ts_max_raw // 1000) if (ts_max_raw and ts_max_raw > 10**11) else ts_max_raw
        print(f"\n  {BOLD}{sym}{RESET}  source={YELLOW}{source}{RESET}  "
              f"ts_max={ts_str(ts_max)}  {age_str(ts_max)}  ({len(bars)} bars)")
        for bar in bars[-5:]:
            t  = bar.get("time")           # ms epoch from local backend
            ts = (t // 1000) if (t and t > 10**11) else t  # normalize ms → s
            c  = bar.get("close") or bar.get("c")
            print(f"    bar_ts={ts_str(ts)}  {age_str(ts)}  close={BOLD}{c}{RESET}")
    except requests.ConnectionError:
        print(f"  {YELLOW}sidecar not reachable at {LOCAL_BASE} — skipping{RESET}")
    except Exception as e:
        print(f"  {RED}ERROR {sym}: {e}{RESET}")


# ── Summary ───────────────────────────────────────────────────────────────────
sep("Summary")
print(f"  Test run at {ts_str(NOW)} ({datetime.fromtimestamp(NOW, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC)")
print(f"\n  {BOLD}What to look for:{RESET}")
print(f"  • Section 1 bar_ts age > 2m  → DailyIQ DB is stale (IBKR not writing fresh bars)")
print(f"  • Section 2 ibkr_lag > 2m    → IBKR returning bars that are already old")
print(f"  • Section 3 ts_max age > 2m  → local sidecar cache is behind DailyIQ cloud")
print(f"  • Sections 1+2 fresh, 3 stale → sidecar not pulling from DailyIQ correctly\n")
