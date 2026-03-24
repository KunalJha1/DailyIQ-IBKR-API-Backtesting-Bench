"""Background worker: fetches option chain data from Yahoo Finance,
computes Black-Scholes Greeks locally, and stores results in SQLite.

Standalone process (like worker_watchlist.py). Runs hourly by default.

Usage:
    python worker_options.py
    python worker_options.py --interval 60        # 1-minute cycle for testing
    python worker_options.py --include-universe   # also process tickers.json symbols
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from yahooquery import Ticker as YahooTicker

from db_utils import execute_many_with_retry, sync_db_session
from runtime_paths import data_dir, resource_path

# ── Constants ────────────────────────────────────────────────────────────────

INTERVAL_S = 3600           # seconds between full cycles (1 hour)
SYMBOL_DELAY_S = 2.0        # delay between symbols to respect Yahoo rate limits
MAX_SYMBOLS_PER_CYCLE = 50  # cap per cycle; portfolio+watchlist take priority
DEFAULT_RISK_FREE_RATE = 0.04  # fallback if ^TNX fetch fails
RISK_FREE_RATE_CACHE_S = 3600  # re-fetch ^TNX at most once per hour

TICKERS_PATH = resource_path("data", "tickers.json")

logger = logging.getLogger("options-worker")


# ── Black-Scholes Greeks (numpy only, no scipy) ──────────────────────────────


def _norm_cdf(x: np.ndarray) -> np.ndarray:
    """Standard normal CDF via Abramowitz & Stegun approximation (7.1.26).
    Max absolute error < 7.5e-8."""
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911
    sign = np.sign(x)
    ax = np.abs(x)
    t = 1.0 / (1.0 + p * ax)
    poly = ((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t
    y = 1.0 - poly * np.exp(-ax * ax / 2.0)
    return 0.5 * (1.0 + sign * y)


def _norm_pdf(x: np.ndarray) -> np.ndarray:
    """Standard normal PDF."""
    return np.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def compute_greeks_vectorized(
    S: np.ndarray,
    K: np.ndarray,
    T: np.ndarray,
    r: float,
    sigma: np.ndarray,
    option_type: np.ndarray,  # array of 'call' or 'put'
) -> dict[str, np.ndarray]:
    """Vectorized Black-Scholes Greeks.

    Theta is daily (÷365). Vega is per 1% IV move. Rho is per 1% rate move.
    Returns NaN for any row where T ≤ 0, sigma ≤ 0, S ≤ 0, or K ≤ 0.
    """
    n = len(S)
    out = {g: np.full(n, np.nan) for g in ("delta", "gamma", "theta", "vega", "rho")}

    valid = (T > 1e-6) & (sigma > 1e-6) & (S > 0) & (K > 0)
    if not valid.any():
        return out

    s = S[valid].astype(float)
    k = K[valid].astype(float)
    t = T[valid].astype(float)
    sig = sigma[valid].astype(float)
    is_call = option_type[valid] == "call"

    sqrt_t = np.sqrt(t)
    d1 = (np.log(s / k) + (r + 0.5 * sig**2) * t) / (sig * sqrt_t)
    d2 = d1 - sig * sqrt_t

    nd1 = _norm_cdf(d1)
    nd2 = _norm_cdf(d2)
    nd1_neg = _norm_cdf(-d1)
    nd2_neg = _norm_cdf(-d2)
    phi_d1 = _norm_pdf(d1)
    disc = np.exp(-r * t)

    delta = np.where(is_call, nd1, nd1 - 1.0)
    gamma = phi_d1 / (s * sig * sqrt_t)

    theta_common = -(s * phi_d1 * sig) / (2.0 * sqrt_t)
    theta_call = (theta_common - r * k * disc * nd2) / 365.0
    theta_put = (theta_common + r * k * disc * nd2_neg) / 365.0
    theta = np.where(is_call, theta_call, theta_put)

    vega = s * phi_d1 * sqrt_t / 100.0

    rho_call = k * t * disc * nd2 / 100.0
    rho_put = -k * t * disc * nd2_neg / 100.0
    rho = np.where(is_call, rho_call, rho_put)

    out["delta"][valid] = delta
    out["gamma"][valid] = gamma
    out["theta"][valid] = theta
    out["vega"][valid] = vega
    out["rho"][valid] = rho
    return out


# ── Risk-free rate ────────────────────────────────────────────────────────────

_rfr_cache: tuple[float, float] = (0.0, DEFAULT_RISK_FREE_RATE)  # (fetched_at, rate)


def fetch_risk_free_rate() -> float:
    """Return 10-year treasury yield from ^TNX as risk-free rate proxy.
    Cached for RISK_FREE_RATE_CACHE_S seconds."""
    global _rfr_cache
    now = time.time()
    if now - _rfr_cache[0] < RISK_FREE_RATE_CACHE_S:
        return _rfr_cache[1]
    try:
        t = YahooTicker("^TNX")
        price_data = t.price
        if isinstance(price_data, dict) and "^TNX" in price_data:
            last = price_data["^TNX"].get("regularMarketPrice")
            if isinstance(last, (int, float)) and last > 0:
                rate = last / 100.0
                _rfr_cache = (now, rate)
                logger.info(f"Risk-free rate: {rate:.4f} (10yr treasury)")
                return rate
    except Exception as exc:
        logger.warning(f"^TNX fetch failed: {exc}; using {_rfr_cache[1]:.4f}")
    return _rfr_cache[1]


# ── Symbol gathering ──────────────────────────────────────────────────────────


def _load_universe_symbols() -> list[str]:
    """Load enabled symbols from tickers.json."""
    try:
        with open(TICKERS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        logger.warning(f"Failed to load tickers.json: {exc}")
        return []
    seen: set[str] = set()
    symbols: list[str] = []
    for company in data.get("companies", []):
        if not company.get("enabled", True):
            continue
        sym = str(company.get("symbol") or "").strip().upper()
        if sym and sym not in seen:
            seen.add(sym)
            symbols.append(sym)
    return symbols


def gather_symbols(include_universe: bool = False) -> list[str]:
    """Build prioritized, deduplicated symbol list.

    Priority: manual portfolio → watchlist → universe (opt-in).
    Capped at MAX_SYMBOLS_PER_CYCLE.
    """
    seen: set[str] = set()
    ordered: list[str] = []

    def _add(syms: list[str]) -> None:
        for s in syms:
            s = s.strip().upper()
            if s and s not in seen:
                seen.add(s)
                ordered.append(s)

    with sync_db_session() as conn:
        rows = conn.execute(
            "SELECT DISTINCT symbol FROM portfolio_manual_positions"
        ).fetchall()
        _add([r[0] for r in rows])

        rows = conn.execute(
            "SELECT symbol FROM watchlist_symbols ORDER BY position"
        ).fetchall()
        _add([r[0] for r in rows])

    if include_universe:
        _add(_load_universe_symbols())

    result = ordered[:MAX_SYMBOLS_PER_CYCLE]
    logger.info(f"Symbol list: {len(result)} symbols (universe={'yes' if include_universe else 'no'})")
    return result


# ── Spot price lookup ─────────────────────────────────────────────────────────


def _get_spot_price(symbol: str) -> Optional[float]:
    """3-tier fallback: watchlist_quotes → market_snapshots → Yahoo live."""
    sym = symbol.upper()
    with sync_db_session() as conn:
        row = conn.execute(
            "SELECT last FROM watchlist_quotes WHERE symbol = ?", (sym,)
        ).fetchone()
        if row and row[0]:
            return float(row[0])
        row = conn.execute(
            "SELECT last FROM market_snapshots WHERE symbol = ?", (sym,)
        ).fetchone()
        if row and row[0]:
            return float(row[0])
    try:
        t = YahooTicker(symbol)
        price_data = t.price
        if isinstance(price_data, dict) and sym in price_data:
            last = price_data[sym].get("regularMarketPrice")
            if isinstance(last, (int, float)) and last > 0:
                return float(last)
    except Exception as exc:
        logger.debug(f"{symbol}: spot price Yahoo fallback failed: {exc}")
    return None


# ── Yahoo fetch ───────────────────────────────────────────────────────────────


def fetch_option_chain(symbol: str) -> Optional[pd.DataFrame]:
    """Fetch full option chain for all expirations from Yahoo.
    Returns flat DataFrame (reset_index applied) or None on failure."""
    try:
        chain = YahooTicker(symbol).option_chain
        if isinstance(chain, pd.DataFrame) and not chain.empty:
            return chain.reset_index()
        logger.debug(f"{symbol}: empty option chain response")
        return None
    except Exception as exc:
        logger.warning(f"{symbol}: option_chain fetch error: {exc}")
        return None


# ── Parse + store ─────────────────────────────────────────────────────────────


def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _safe_int(v) -> Optional[int]:
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else int(f)
    except (TypeError, ValueError):
        return None


def parse_and_store_chain(
    symbol: str,
    df: pd.DataFrame,
    rfr: float,
    now_epoch: int,
) -> tuple[int, int]:
    """Parse Yahoo chain DataFrame, compute Greeks, write to SQLite.

    Returns (contract_count, expiration_count).
    """
    if df.empty:
        return 0, 0

    spot = _get_spot_price(symbol)
    n = len(df)

    # ── Build arrays for vectorized computation ──
    S = np.full(n, spot if spot else np.nan)
    K = pd.to_numeric(df.get("strike", pd.Series(dtype=float)), errors="coerce").values

    # Time to expiry in years
    exp_col = df.get("expiration")
    exp_dt = pd.to_datetime(exp_col, errors="coerce", utc=True)
    exp_epoch = (exp_dt.astype(np.int64) // 10**9).values
    T = np.maximum((exp_epoch - now_epoch) / (365.25 * 86400.0), 0.0)
    DTE = (exp_epoch - now_epoch) / 86400.0  # days_to_expiration (may be negative for expired)

    sigma = pd.to_numeric(df.get("impliedVolatility", pd.Series(dtype=float)), errors="coerce").values
    opt_types = df.get("optionType", pd.Series(dtype=str)).str.lower().values

    greeks = compute_greeks_vectorized(S, K, T, rfr, sigma, opt_types)

    # ── Intrinsic / extrinsic ──
    bid_arr = pd.to_numeric(df.get("bid", pd.Series(dtype=float)), errors="coerce").values
    ask_arr = pd.to_numeric(df.get("ask", pd.Series(dtype=float)), errors="coerce").values
    last_arr = pd.to_numeric(df.get("lastPrice", pd.Series(dtype=float)), errors="coerce").values

    mid_arr = np.where(
        ~np.isnan(bid_arr) & ~np.isnan(ask_arr),
        (bid_arr + ask_arr) / 2.0,
        np.nan,
    )
    # Use mid if available, else last price for extrinsic calc
    price_for_ext = np.where(~np.isnan(mid_arr), mid_arr, last_arr)

    intrinsic = np.where(
        opt_types == "call",
        np.maximum(S - K, 0.0),
        np.maximum(K - S, 0.0),
    )
    extrinsic = np.where(
        ~np.isnan(price_for_ext),
        np.maximum(price_for_ext - intrinsic, 0.0),
        np.nan,
    )

    # ── Build rows ──
    contract_rows: list[tuple] = []
    snapshot_rows: list[tuple] = []
    expiration_set: set[int] = set()

    for i in range(n):
        contract_id = str(df["contractSymbol"].iloc[i]) if "contractSymbol" in df.columns else ""
        if not contract_id:
            continue

        exp_ep = int(exp_epoch[i]) if not math.isnan(float(exp_epoch[i])) else None
        if exp_ep is None:
            continue
        expiration_set.add(exp_ep)

        opt_type = str(opt_types[i]) if opt_types[i] else ""
        if opt_type not in ("call", "put"):
            continue

        contract_rows.append((
            contract_id,
            symbol.upper(),
            exp_ep,
            float(K[i]) if not math.isnan(float(K[i])) else 0.0,
            opt_type,
            str(df["contractSize"].iloc[i]) if "contractSize" in df.columns else "REGULAR",
            str(df["currency"].iloc[i]) if "currency" in df.columns else "USD",
            None,   # exchange — not provided by Yahoo
            None,   # exercise_style — not provided by Yahoo
            now_epoch,
            now_epoch,
        ))

        # Greeks: None if NaN
        delta = _safe_float(greeks["delta"][i])
        gamma = _safe_float(greeks["gamma"][i])
        theta = _safe_float(greeks["theta"][i])
        vega = _safe_float(greeks["vega"][i])
        rho = _safe_float(greeks["rho"][i])

        # calc_error: explain why Greeks are None
        calc_error: Optional[str] = None
        if delta is None:
            if float(T[i]) <= 1e-6:
                calc_error = "expired"
            elif math.isnan(float(sigma[i])) or float(sigma[i]) <= 1e-6:
                calc_error = "iv_zero_or_missing"
            elif spot is None:
                calc_error = "spot_price_unavailable"
            else:
                calc_error = "bs_computation_failed"

        ltd_epoch: Optional[int] = None
        if "lastTradeDate" in df.columns:
            ltd = df["lastTradeDate"].iloc[i]
            if pd.notna(ltd):
                try:
                    ltd_epoch = int(pd.to_datetime(ltd).timestamp())
                except Exception:
                    pass

        snapshot_rows.append((
            contract_id,
            now_epoch,
            _safe_float(spot),
            _safe_float(bid_arr[i]),
            _safe_float(ask_arr[i]),
            None,  # bid_size — not provided by Yahoo
            None,  # ask_size — not provided by Yahoo
            _safe_float(mid_arr[i]),
            _safe_float(last_arr[i]),
            _safe_float(df["change"].iloc[i]) if "change" in df.columns else None,
            _safe_float(df["percentChange"].iloc[i]) if "percentChange" in df.columns else None,
            _safe_int(df["volume"].iloc[i]) if "volume" in df.columns else None,
            _safe_int(df["openInterest"].iloc[i]) if "openInterest" in df.columns else None,
            _safe_float(sigma[i]),
            1 if df["inTheMoney"].iloc[i] else 0 if "inTheMoney" in df.columns else None,
            ltd_epoch,
            delta,
            gamma,
            theta,
            vega,
            rho,
            _safe_float(intrinsic[i]),
            _safe_float(extrinsic[i]),
            _safe_float(DTE[i]),
            rfr,
            "black-scholes" if delta is not None else None,
            "yahoo",
            calc_error,
            "yahoo",
        ))

    _upsert_contracts(contract_rows)
    _insert_snapshots(snapshot_rows)

    return len(contract_rows), len(expiration_set)


# ── DB helpers ────────────────────────────────────────────────────────────────


def _upsert_contracts(rows: list[tuple]) -> None:
    if not rows:
        return
    with sync_db_session() as conn:
        execute_many_with_retry(
            conn,
            """
            INSERT INTO option_contracts
                (contract_id, underlying, expiration, strike, option_type,
                 contract_size, currency, exchange, exercise_style,
                 created_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(contract_id) DO UPDATE SET
                last_seen_at   = excluded.last_seen_at,
                contract_size  = excluded.contract_size,
                currency       = excluded.currency
            """,
            rows,
        )


def _insert_snapshots(rows: list[tuple]) -> None:
    if not rows:
        return
    with sync_db_session() as conn:
        execute_many_with_retry(
            conn,
            """
            INSERT INTO option_snapshots
                (contract_id, captured_at, underlying_price,
                 bid, ask, bid_size, ask_size, mid,
                 last_price, change, change_pct, volume, open_interest,
                 implied_volatility, in_the_money, last_trade_date,
                 delta, gamma, theta, vega, rho,
                 intrinsic_value, extrinsic_value, days_to_expiration,
                 risk_free_rate, greeks_source, iv_source, calc_error, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(contract_id, captured_at) DO UPDATE SET
                underlying_price   = excluded.underlying_price,
                bid                = excluded.bid,
                ask                = excluded.ask,
                mid                = excluded.mid,
                last_price         = excluded.last_price,
                volume             = excluded.volume,
                open_interest      = excluded.open_interest,
                implied_volatility = excluded.implied_volatility,
                in_the_money       = excluded.in_the_money,
                delta              = excluded.delta,
                gamma              = excluded.gamma,
                theta              = excluded.theta,
                vega               = excluded.vega,
                rho                = excluded.rho,
                intrinsic_value    = excluded.intrinsic_value,
                extrinsic_value    = excluded.extrinsic_value,
                days_to_expiration = excluded.days_to_expiration,
                risk_free_rate     = excluded.risk_free_rate,
                greeks_source      = excluded.greeks_source,
                calc_error         = excluded.calc_error
            """,
            rows,
        )


def _update_fetch_meta(
    symbol: str,
    now_epoch: int,
    exp_count: int,
    contract_count: int,
    success: bool,
    error_message: Optional[str],
    duration_ms: int,
) -> None:
    with sync_db_session() as conn:
        conn.execute(
            """
            INSERT INTO option_chain_fetch_meta
                (underlying, source, fetched_at, expiration_count, contract_count,
                 success, error_message, duration_ms)
            VALUES (?, 'yahoo', ?, ?, ?, ?, ?, ?)
            ON CONFLICT(underlying, source) DO UPDATE SET
                fetched_at       = excluded.fetched_at,
                expiration_count = excluded.expiration_count,
                contract_count   = excluded.contract_count,
                success          = excluded.success,
                error_message    = excluded.error_message,
                duration_ms      = excluded.duration_ms
            """,
            (
                symbol.upper(),
                now_epoch,
                exp_count,
                contract_count,
                1 if success else 0,
                error_message,
                duration_ms,
            ),
        )


# ── Main loop ─────────────────────────────────────────────────────────────────


async def worker_loop(interval_s: int = INTERVAL_S, include_universe: bool = False) -> None:
    """Main async loop: one full cycle per interval_s seconds."""
    logger.info(f"Options chain worker started — interval={interval_s}s, universe={include_universe}")
    loop = asyncio.get_event_loop()

    while True:
        cycle_start = time.time()
        now_epoch = int(cycle_start)

        try:
            symbols = gather_symbols(include_universe=include_universe)

            if not symbols:
                logger.info("No symbols to process; sleeping")
                await asyncio.sleep(interval_s)
                continue

            rfr = await loop.run_in_executor(None, fetch_risk_free_rate)

            total_contracts = 0
            total_ok = 0

            for idx, symbol in enumerate(symbols):
                sym_start = time.time()
                try:
                    df = await loop.run_in_executor(None, fetch_option_chain, symbol)
                    if df is not None:
                        contracts, expirations = await loop.run_in_executor(
                            None, parse_and_store_chain, symbol, df, rfr, now_epoch
                        )
                        duration_ms = int((time.time() - sym_start) * 1000)
                        _update_fetch_meta(symbol, now_epoch, expirations, contracts, True, None, duration_ms)
                        total_contracts += contracts
                        total_ok += 1
                        logger.info(
                            f"[{idx + 1}/{len(symbols)}] {symbol}: "
                            f"{contracts} contracts across {expirations} expirations ({duration_ms}ms)"
                        )
                    else:
                        duration_ms = int((time.time() - sym_start) * 1000)
                        _update_fetch_meta(symbol, now_epoch, 0, 0, False, "empty_chain", duration_ms)
                        logger.info(f"[{idx + 1}/{len(symbols)}] {symbol}: no chain data")
                except Exception as exc:
                    duration_ms = int((time.time() - sym_start) * 1000)
                    err = str(exc)[:200]
                    _update_fetch_meta(symbol, now_epoch, 0, 0, False, err, duration_ms)
                    logger.warning(f"[{idx + 1}/{len(symbols)}] {symbol}: error — {exc}")

                if idx < len(symbols) - 1:
                    await asyncio.sleep(SYMBOL_DELAY_S)

            elapsed = time.time() - cycle_start
            logger.info(
                f"Cycle complete — {total_ok}/{len(symbols)} symbols ok, "
                f"{total_contracts} total contracts, {elapsed:.1f}s elapsed"
            )

        except Exception as exc:
            logger.error(f"Cycle-level error: {exc}", exc_info=True)

        elapsed = time.time() - cycle_start
        sleep_for = max(0.0, interval_s - elapsed)
        if sleep_for > 0:
            logger.info(f"Next cycle in {sleep_for:.0f}s")
            await asyncio.sleep(sleep_for)


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Options chain worker")
    parser.add_argument(
        "--interval",
        type=int,
        default=INTERVAL_S,
        help=f"Seconds between full cycles (default: {INTERVAL_S})",
    )
    parser.add_argument(
        "--include-universe",
        action="store_true",
        help="Also fetch chains for all enabled symbols in tickers.json",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    asyncio.run(worker_loop(interval_s=args.interval, include_universe=args.include_universe))


if __name__ == "__main__":
    main()
