"""
Diagnostic script: inspect the entire technical scoring pipeline.

Run from the backend/ directory:
    python tests/test_tech_scores.py

By default this uses the same app-data database as the desktop app
(`%APPDATA%\\com.dailyiq.app\\market.db` on Windows) when it exists.
Set `DAILYIQ_DATA_DIR` to override.

Checks:
  1. S&P 500 universe size (from tickers.json)
  2. ohlcv_1d coverage (how many symbols have daily bars, how many are scorable)
  3. technical_scores table (how many have real scores vs NULLs)
  4. Cross-reference: scorable but not scored
  5. Live scoring test (call score_symbols inline)
  6. Summary
"""

import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db_utils import DB_PATH

TICKERS_PATH = Path(__file__).parent.parent.parent / "data" / "tickers.json"
MIN_BARS = 60


# ── Helpers ───────────────────────────────────────────────────────────

def load_sp500_symbols() -> list[str]:
    with open(TICKERS_PATH) as f:
        data = json.load(f)
    return [
        c["symbol"]
        for c in data.get("companies", [])
        if c.get("enabled", True) and float(c.get("sp500_weight", 0) or 0) > 0
    ]


def pct(n: int, total: int) -> str:
    return f"{n / total * 100:.1f}%" if total else "N/A"


# ── 1. Universe size ─────────────────────────────────────────────────

def check_universe(symbols: list[str]) -> None:
    print(f"\n{'='*60}")
    print(f"  [1] S&P 500 UNIVERSE")
    print(f"{'='*60}")
    print(f"  tickers.json path : {TICKERS_PATH}")
    print(f"  Enabled w/ sp500_weight > 0 : {len(symbols)} symbols")
    if len(symbols) < 10:
        print(f"  WARNING: Only {len(symbols)} symbols — tickers.json may be incomplete")


# ── 2. ohlcv_1d coverage ─────────────────────────────────────────────

def check_ohlcv_coverage(conn: sqlite3.Connection, symbols: list[str]) -> dict[str, int]:
    print(f"\n{'='*60}")
    print(f"  [2] ohlcv_1d COVERAGE")
    print(f"{'='*60}")

    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='ohlcv_1d'"
    ).fetchall()]
    if not tables:
        print("  TABLE ohlcv_1d DOES NOT EXIST — no daily bars at all")
        return {s: 0 for s in symbols}

    bar_counts: dict[str, int] = {}
    for sym in symbols:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM ohlcv_1d WHERE symbol = ?", (sym,)
        ).fetchone()[0]
        bar_counts[sym] = cnt

    zero = sorted(s for s, c in bar_counts.items() if c == 0)
    partial = sorted(s for s, c in bar_counts.items() if 0 < c < MIN_BARS)
    scorable = sorted(s for s, c in bar_counts.items() if c >= MIN_BARS)

    print(f"\n  0 bars (no data)          : {len(zero)}")
    print(f"  1-{MIN_BARS - 1} bars (below MIN_BARS) : {len(partial)}")
    print(f"  {MIN_BARS}+ bars (scorable)       : {len(scorable)}")

    if zero:
        preview = zero[:20]
        print(f"\n  Symbols with 0 bars ({len(zero)} total):")
        print(f"    {', '.join(preview)}{'...' if len(zero) > 20 else ''}")
    if partial:
        details = [(s, bar_counts[s]) for s in partial[:15]]
        print(f"\n  Symbols with 1-{MIN_BARS - 1} bars ({len(partial)} total):")
        for s, c in details:
            print(f"    {s:6} -> {c} bars")
        if len(partial) > 15:
            print(f"    ... and {len(partial) - 15} more")
    if scorable:
        top = [(s, bar_counts[s]) for s in scorable[:10]]
        print(f"\n  Scorable symbols ({len(scorable)} total, showing top 10):")
        for s, c in top:
            print(f"    {s:6} -> {c} bars")

    return bar_counts


# ── 3. technical_scores table ─────────────────────────────────────────

def check_scores_table(conn: sqlite3.Connection, symbols: list[str]) -> dict[str, tuple]:
    print(f"\n{'='*60}")
    print(f"  [3] technical_scores TABLE")
    print(f"{'='*60}")

    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='technical_scores'"
    ).fetchall()]
    if not tables:
        print("  TABLE technical_scores DOES NOT EXIST")
        return {}

    total_rows = conn.execute("SELECT COUNT(*) FROM technical_scores").fetchone()[0]
    print(f"  Total rows in table: {total_rows}")

    score_map: dict[str, tuple] = {}
    sym_set = set(s.upper() for s in symbols)
    rows = conn.execute(
        "SELECT symbol, score_1d, score_1w, last_updated_utc FROM technical_scores"
    ).fetchall()
    for r in rows:
        score_map[r[0]] = (r[1], r[2], r[3])

    sp500_with_row = [s for s in symbols if s in score_map]
    has_1d = [s for s in sp500_with_row if score_map[s][0] is not None]
    has_1w = [s for s in sp500_with_row if score_map[s][1] is not None]
    both_null = [s for s in sp500_with_row if score_map[s][0] is None and score_map[s][1] is None]
    no_row = [s for s in symbols if s not in score_map]

    print(f"\n  S&P 500 symbols with a row    : {len(sp500_with_row)}")
    print(f"  S&P 500 symbols with NO row   : {len(no_row)}")
    print(f"  Non-NULL score_1d             : {len(has_1d)}")
    print(f"  Non-NULL score_1w             : {len(has_1w)}")
    print(f"  Both score_1d & 1w are NULL   : {len(both_null)}")

    timestamps = [score_map[s][2] for s in sp500_with_row if score_map[s][2]]
    if timestamps:
        print(f"\n  Oldest last_updated_utc : {min(timestamps)}")
        print(f"  Newest last_updated_utc : {max(timestamps)}")
    else:
        print(f"\n  No timestamps found — scorer may have never run")

    if no_row:
        preview = sorted(no_row)[:20]
        print(f"\n  Symbols with NO row in technical_scores ({len(no_row)} total):")
        print(f"    {', '.join(preview)}{'...' if len(no_row) > 20 else ''}")

    if has_1d:
        sample = has_1d[:8]
        print(f"\n  Sample scored symbols:")
        for s in sample:
            s1d, s1w, ts = score_map[s]
            print(f"    {s:6}  1d={s1d:>3}  1w={s1w if s1w is not None else 'N/A':>3}  updated={ts}")

    return score_map


# ── 4. Cross-reference: scorable but not scored ──────────────────────

def check_gap(
    symbols: list[str],
    bar_counts: dict[str, int],
    score_map: dict[str, tuple],
) -> list[str]:
    print(f"\n{'='*60}")
    print(f"  [4] SCORABLE BUT NOT SCORED (the gap)")
    print(f"{'='*60}")

    scorable = [s for s in symbols if bar_counts.get(s, 0) >= MIN_BARS]
    scored = [s for s in scorable if s in score_map and score_map[s][0] is not None]
    gap = [s for s in scorable if s not in score_map or score_map[s][0] is None]

    print(f"  Scorable (>= {MIN_BARS} daily bars) : {len(scorable)}")
    print(f"  Actually scored (1d != NULL)  : {len(scored)}")
    print(f"  GAP (scorable but not scored) : {len(gap)}")

    if gap:
        details = [(s, bar_counts[s]) for s in sorted(gap)[:25]]
        print(f"\n  These symbols HAVE enough data but NO score:")
        for s, c in details:
            row_status = "no row" if s not in score_map else "row exists, score_1d=NULL"
            print(f"    {s:6}  {c:>4} bars  ({row_status})")
        if len(gap) > 25:
            print(f"    ... and {len(gap) - 25} more")
    else:
        print(f"\n  No gap -- every scorable symbol has a score.")

    return gap


# ── 5. Live scoring test ─────────────────────────────────────────────

def live_scoring_test(
    gap: list[str],
    bar_counts: dict[str, int],
    symbols: list[str],
) -> None:
    print(f"\n{'='*60}")
    print(f"  [5] LIVE SCORING TEST")
    print(f"{'='*60}")

    candidates = gap[:5] if gap else [
        s for s in symbols if bar_counts.get(s, 0) >= MIN_BARS
    ][:5]

    if not candidates:
        print("  No symbols with enough data to test scoring.")
        return

    print(f"  Testing score_symbols() on: {', '.join(candidates)}")
    print()

    try:
        from technicals import score_symbols
        result = score_symbols(candidates, ["1d", "1w"])
        for sym in candidates:
            scores = result.get(sym, {})
            s1d = scores.get("1d")
            s1w = scores.get("1w")
            bars = bar_counts.get(sym, 0)
            status = "OK" if s1d is not None else "FAILED (returned None)"
            print(f"    {sym:6}  bars={bars:>4}  1d={s1d!s:>4}  1w={s1w!s:>4}  {status}")
    except Exception as e:
        print(f"  ERROR running score_symbols: {e}")
        import traceback
        traceback.print_exc()


# ── 6. Summary ────────────────────────────────────────────────────────

def print_summary(
    symbols: list[str],
    bar_counts: dict[str, int],
    score_map: dict[str, tuple],
    gap: list[str],
) -> None:
    total = len(symbols)
    have_bars = sum(1 for s in symbols if bar_counts.get(s, 0) > 0)
    scorable = sum(1 for s in symbols if bar_counts.get(s, 0) >= MIN_BARS)
    scored_1d = sum(
        1 for s in symbols
        if s in score_map and score_map[s][0] is not None
    )

    print(f"\n{'='*60}")
    print(f"  [6] SUMMARY")
    print(f"{'='*60}")
    print(f"  Universe             : {total} symbols")
    print(f"  Have daily bars      : {have_bars:>4}  ({pct(have_bars, total)})")
    print(f"  Scorable (>={MIN_BARS} bars) : {scorable:>4}  ({pct(scorable, total)})")
    print(f"  Actually scored (1d) : {scored_1d:>4}  ({pct(scored_1d, total)})")
    print(f"  Scorable but NOT scored: {len(gap)}")

    print()
    if len(gap) == 0 and scored_1d > 0:
        print("  VERDICT: Scoring pipeline is healthy. All scorable symbols have scores.")
    elif scored_1d == 0 and scorable > 0:
        print("  VERDICT: SCORER IS NOT PRODUCING ANY RESULTS.")
        print("           There are scorable symbols but zero scores in the DB.")
        print("           The TechnicalsScorer._loop() may not be running, or it's")
        print("           erroring silently. Check the sidecar console for:")
        print('             "TechnicalsScorer started"')
        print('             "Universe tech scores (1d/1w) updated for N symbol(s)"')
    elif len(gap) > 0:
        print(f"  VERDICT: PARTIAL GAP — {len(gap)} symbols have enough daily bars")
        print(f"           but still show NULL scores. The scorer may be:")
        print(f"           (a) Not including these symbols in its universe list")
        print(f"           (b) Erroring on these specific symbols")
        print(f"           (c) Overwriting scores with NULL due to a bug in _compute_and_upsert_universe")
    elif scorable == 0:
        print("  VERDICT: NO SYMBOLS HAVE ENOUGH DATA.")
        print(f"           0 out of {total} S&P 500 symbols have >={MIN_BARS} daily bars.")
        print("           The backfill_loop (worker_watchlist.py) has not populated")
        print("           ohlcv_1d yet. Wait for it to finish, or check if TWS is connected.")
    else:
        print("  VERDICT: Unable to determine status.")


# ── Main ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Technical Scoring Pipeline Diagnostic")
    print(f"DB path: {DB_PATH}")
    print(f"DATA dir: {DB_PATH.parent}")
    print(f"Tickers: {TICKERS_PATH}")
    print(f"Time   : {datetime.now(timezone.utc).isoformat()}")

    symbols = load_sp500_symbols()
    check_universe(symbols)

    if not DB_PATH.exists():
        print(f"\n  DB file does not exist at {DB_PATH}")
        print("  The sidecar has never run or data_dir is misconfigured.")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")

    bar_counts = check_ohlcv_coverage(conn, symbols)
    score_map = check_scores_table(conn, symbols)
    gap = check_gap(symbols, bar_counts, score_map)
    conn.close()

    live_scoring_test(gap, bar_counts, symbols)
    print_summary(symbols, bar_counts, score_map, gap)
