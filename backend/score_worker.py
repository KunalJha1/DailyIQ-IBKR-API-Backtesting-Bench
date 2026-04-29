"""Background technical scoring service.

Runs every INTERVAL_S seconds, computes 0-100 scores for every symbol in the
watchlist across all timeframes (1m, 5m, 15m, 1h, 4h, 1d, 1w), and upserts
results into the `technical_scores` SQLite table.

A secondary "universe" tier continuously rotates through the full S&P 500 in
bounded batches across the same score timeframes.
"""

from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from db_utils import execute_many_with_retry, sync_db_session
from technicals import MIN_BARS, SUPPORTED_TIMEFRAMES, inspect_symbol_timeframe, score_symbols

logger = logging.getLogger(__name__)

TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]
UNIVERSE_TIMEFRAMES = list(TIMEFRAMES)
INTERVAL_S = 60
SCORE_STALE_AFTER_S = 300
_SCORE_FIELDS = ("1m", "5m", "15m", "1h", "4h", "1d", "1w")
# Write to DB after every N symbols so the frontend sees incremental updates
# rather than waiting for the entire batch to finish.
SCORE_BATCH_SIZE = 20
UNIVERSE_SCORE_BATCH_SIZE = max(1, int(os.getenv("DAILYIQ_UNIVERSE_SCORE_BATCH_SIZE", "25")))
SCORE_MAX_WORKERS = max(1, min(4, int(os.getenv("DAILYIQ_SCORE_WORKERS", "1"))))


def _score_symbols_parallel(symbols: list[str], timeframes: list[str]) -> dict[str, dict[str, int | None]]:
    """Score symbols concurrently with one SQLite connection per worker chunk."""
    if len(symbols) <= 1 or SCORE_MAX_WORKERS <= 1:
        return score_symbols(symbols, timeframes)

    result: dict[str, dict[str, int | None]] = {}
    with ThreadPoolExecutor(max_workers=min(SCORE_MAX_WORKERS, len(symbols))) as pool:
        worker_count = min(SCORE_MAX_WORKERS, len(symbols))
        chunk_size = max(1, (len(symbols) + worker_count - 1) // worker_count)
        chunks = [symbols[i:i + chunk_size] for i in range(0, len(symbols), chunk_size)]
        futures = {pool.submit(score_symbols, chunk, timeframes): tuple(chunk) for chunk in chunks}
        for future in as_completed(futures):
            chunk = futures[future]
            try:
                result.update(future.result())
            except Exception as exc:
                logger.warning("parallel score(%s): %s", ",".join(chunk), exc)
                for sym in chunk:
                    result[sym] = {tf: None for tf in timeframes}
    return result


def _upsert_scores(
    rows: list[tuple[str, int | None, int | None, int | None, int | None, int | None, int | None, int | None]],
    now_utc: datetime,
) -> None:
    """Write scored rows into technical_scores via upsert with retry."""
    if not rows:
        return
    with sync_db_session() as conn:
        execute_many_with_retry(
            conn,
            """
            INSERT INTO technical_scores
                (symbol, score_1m, score_5m, score_15m, score_1h, score_4h, score_1d, score_1w, last_updated_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (symbol) DO UPDATE SET
                score_1m         = excluded.score_1m,
                score_5m         = excluded.score_5m,
                score_15m        = excluded.score_15m,
                score_1h         = excluded.score_1h,
                score_4h         = excluded.score_4h,
                score_1d         = excluded.score_1d,
                score_1w         = excluded.score_1w,
                last_updated_utc = excluded.last_updated_utc
            """,
            [(sym, s1m, s5m, s15m, s1h, s4h, s1d, s1w, now_utc) for sym, s1m, s5m, s15m, s1h, s4h, s1d, s1w in rows],
        )


def _compute_and_upsert(symbols: list[str]) -> None:
    """Blocking: score symbols in batches and upsert after each batch.

    Writing incrementally means the DB is updated continuously — the frontend
    sees real data on its next poll rather than waiting for all symbols to finish.
    """
    if not symbols:
        return
    total = 0
    for i in range(0, len(symbols), SCORE_BATCH_SIZE):
        batch = symbols[i:i + SCORE_BATCH_SIZE]
        try:
            scored = _score_symbols_parallel(batch, TIMEFRAMES)
        except Exception as exc:
            logger.error("TechnicalsScorer batch score error (symbols %d-%d): %s", i, i + len(batch), exc)
            continue
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = [
            (
                sym,
                scores.get("1m"),
                scores.get("5m"),
                scores.get("15m"),
                scores.get("1h"),
                scores.get("4h"),
                scores.get("1d"),
                scores.get("1w"),
            )
            for sym, scores in scored.items()
        ]
        try:
            _upsert_scores(rows, now_utc)
        except Exception as exc:
            logger.error("TechnicalsScorer upsert error (symbols %d-%d): %s", i, i + len(batch), exc)
            continue
        total += len(rows)
    logger.info("Technical scores updated for %s symbol(s)", total)


def _fetch_existing_score_rows(
    conn,
    symbols: list[str],
) -> dict[str, dict[str, int | None]]:
    if not symbols:
        return {}
    placeholders = ", ".join("?" * len(symbols))
    rows = conn.execute(
        f"""
        SELECT symbol, score_1m, score_5m, score_15m, score_1h, score_4h,
               score_1d, score_1w, last_updated_utc
        FROM technical_scores
        WHERE symbol IN ({placeholders})
        """,
        symbols,
    ).fetchall()
    return {row[0]: _row_to_score_map(row) for row in rows}


def _compute_and_upsert_timeframes(symbols: list[str], timeframes: list[str] | None = None) -> None:
    """Blocking: score selected symbols/timeframes and preserve other cached scores."""
    normalized_symbols = _normalize_symbols(symbols)
    requested_timeframes = _normalize_timeframes(timeframes)
    if not normalized_symbols or not requested_timeframes:
        return

    total = 0
    for i in range(0, len(normalized_symbols), SCORE_BATCH_SIZE):
        batch = normalized_symbols[i:i + SCORE_BATCH_SIZE]
        try:
            scored = _score_symbols_parallel(batch, requested_timeframes)
        except Exception as exc:
            logger.error("Targeted scorer batch error (symbols %d-%d): %s", i, i + len(batch), exc)
            continue

        try:
            with sync_db_session() as conn:
                existing_rows = _fetch_existing_score_rows(conn, batch)
            rows = [
                _merge_score_row(
                    sym,
                    existing_rows.get(sym, {tf: None for tf in _SCORE_FIELDS}),
                    scores,
                )
                for sym, scores in scored.items()
            ]
            _upsert_scores(rows, datetime.now(timezone.utc).replace(tzinfo=None))
        except Exception as exc:
            logger.error("Targeted scorer upsert error (symbols %d-%d): %s", i, i + len(batch), exc)
            continue

        total += len(scored)
    logger.info(
        "Targeted technical scores updated for %s symbol(s), timeframes=%s",
        total,
        ",".join(requested_timeframes),
    )


def _compute_and_upsert_universe(symbols: list[str]) -> None:
    """Score universe symbols across all cached heatmap timeframes."""
    _compute_and_upsert_timeframes(symbols, UNIVERSE_TIMEFRAMES)


def _normalize_symbols(symbols: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in symbols:
        sym = (raw or "").strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        normalized.append(sym)
    return normalized


def _normalize_timeframes(timeframes: list[str] | None) -> list[str]:
    requested = timeframes or list(_SCORE_FIELDS)
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in requested:
        tf = (raw or "").strip().lower()
        if tf not in _SCORE_FIELDS or tf in seen:
            continue
        seen.add(tf)
        normalized.append(tf)
    return normalized or list(_SCORE_FIELDS)


def _parse_score_timestamp(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _score_is_stale(value, now_utc: datetime | None = None) -> bool:
    ts = _parse_score_timestamp(value)
    if ts is None:
        return True
    now = now_utc or datetime.now(timezone.utc).replace(tzinfo=None)
    return (now - ts).total_seconds() > SCORE_STALE_AFTER_S


def _row_to_score_map(row: tuple | None) -> dict[str, int | None]:
    if not row:
        return {tf: None for tf in _SCORE_FIELDS}
    return {
        "1m": row[1],
        "5m": row[2],
        "15m": row[3],
        "1h": row[4],
        "4h": row[5],
        "1d": row[6],
        "1w": row[7],
    }


def _merge_score_row(
    symbol: str,
    existing: dict[str, int | None],
    updates: dict[str, int | None],
) -> tuple[
    str,
    int | None,
    int | None,
    int | None,
    int | None,
    int | None,
    int | None,
    int | None,
]:
    merged = {
        tf: updates[tf] if tf in updates else existing.get(tf)
        for tf in _SCORE_FIELDS
    }
    return (
        symbol,
        merged["1m"],
        merged["5m"],
        merged["15m"],
        merged["1h"],
        merged["4h"],
        merged["1d"],
        merged["1w"],
    )


def read_scores(symbols: list[str]) -> list[dict]:
    """Backward-compatible cache read for all supported timeframes."""
    return read_scores_for_timeframes(symbols, list(_SCORE_FIELDS))


def read_scores_for_timeframes(
    symbols: list[str],
    timeframes: list[str] | None = None,
) -> list[dict]:
    """Read cached scores and surface coverage status without computing on demand."""
    normalized_symbols = _normalize_symbols(symbols)
    if not normalized_symbols:
        return []
    requested_timeframes = _normalize_timeframes(timeframes)
    placeholders = ", ".join("?" * len(normalized_symbols))

    with sync_db_session() as conn:
        rows = conn.execute(
            f"""
            SELECT symbol, score_1m, score_5m, score_15m, score_1h, score_4h,
                   score_1d, score_1w, last_updated_utc
            FROM technical_scores
            WHERE symbol IN ({placeholders})
            """,
            normalized_symbols,
        ).fetchall()
        row_map = {row[0]: row for row in rows}

        payloads: list[dict] = []
        for sym in normalized_symbols:
            row = row_map.get(sym)
            cached = _row_to_score_map(row)
            payload = {
                "symbol": sym,
                "last_updated_utc": row[8].isoformat() if row and hasattr(row[8], "isoformat") else (row[8] if row else None),
            }
            for tf in _SCORE_FIELDS:
                payload[tf] = cached.get(tf)
            for tf in requested_timeframes:
                score = cached.get(tf)
                if score is not None:
                    payload[f"status_{tf}"] = "ok"
                    payload[f"bars_{tf}"] = None
                    payload[f"required_bars_{tf}"] = MIN_BARS
                    continue

                inspection = inspect_symbol_timeframe(conn, sym, tf)
                status = inspection.get("status")
                payload[f"status_{tf}"] = "not_computed" if status == "scorable" else status
                payload[f"bars_{tf}"] = inspection.get("bar_count")
                payload[f"required_bars_{tf}"] = inspection.get("required_bars", MIN_BARS)
            payloads.append(payload)

    return payloads


def find_refresh_candidates(
    symbols: list[str],
    timeframes: list[str] | None = None,
    *,
    stale_after_s: int = SCORE_STALE_AFTER_S,
) -> dict[str, list[str]]:
    """Return scorable symbol/timeframe pairs that should be recomputed."""
    normalized_symbols = _normalize_symbols(symbols)
    requested_timeframes = _normalize_timeframes(timeframes)
    if not normalized_symbols or not requested_timeframes:
        return {}

    placeholders = ", ".join("?" * len(normalized_symbols))
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    candidates: dict[str, list[str]] = {}
    with sync_db_session() as conn:
        rows = conn.execute(
            f"""
            SELECT symbol, score_1m, score_5m, score_15m, score_1h, score_4h,
                   score_1d, score_1w, last_updated_utc
            FROM technical_scores
            WHERE symbol IN ({placeholders})
            """,
            normalized_symbols,
        ).fetchall()
        row_map = {row[0]: row for row in rows}
        for sym in normalized_symbols:
            row = row_map.get(sym)
            cached = _row_to_score_map(row)
            stale = True
            if row is not None:
                ts = _parse_score_timestamp(row[8])
                stale = ts is None or (now_utc - ts).total_seconds() > stale_after_s

            for tf in requested_timeframes:
                if cached.get(tf) is not None and not stale:
                    continue
                inspection = inspect_symbol_timeframe(conn, sym, tf)
                if inspection.get("status") == "scorable":
                    candidates.setdefault(sym, []).append(tf)
    return candidates


class TechnicalsScorer:
    """Continuous score service for watchlist, active, and universe symbols."""

    def __init__(self) -> None:
        self._symbols: list[str] = []
        self._active_symbols: list[str] = []
        self._universe: list[str] = []
        self._universe_cursor = 0
        self._task: asyncio.Task | None = None
        self._targeted_task: asyncio.Task | None = None
        self._pending_refreshes: dict[str, set[str]] = {}
        self._pending_lock: asyncio.Lock | None = None

    def set_symbols(self, symbols: list[str]) -> None:
        self._symbols = _normalize_symbols(symbols)

    def set_active_symbols(self, symbols: list[str]) -> None:
        self._active_symbols = _normalize_symbols(symbols)

    def set_universe(self, symbols: list[str]) -> None:
        """Set the broad universe (e.g. S&P 500) for continuous background scoring."""
        self._universe = _normalize_symbols(symbols)
        if self._universe_cursor >= len(self._universe):
            self._universe_cursor = 0

    def _priority_symbols(self) -> list[str]:
        return _normalize_symbols([*self._symbols, *self._active_symbols])

    def _next_universe_batch(self, excluded: set[str]) -> list[str]:
        eligible = [sym for sym in self._universe if sym not in excluded]
        if not eligible:
            self._universe_cursor = 0
            return []
        if self._universe_cursor >= len(eligible):
            self._universe_cursor = 0

        size = min(UNIVERSE_SCORE_BATCH_SIZE, len(eligible))
        end = self._universe_cursor + size
        if end <= len(eligible):
            batch = eligible[self._universe_cursor:end]
        else:
            batch = eligible[self._universe_cursor:] + eligible[:end - len(eligible)]
        self._universe_cursor = end % len(eligible)
        return batch

    def request_refresh(self, symbols: list[str], timeframes: list[str] | None = None) -> None:
        """Queue an immediate score refresh for requested symbol/timeframe pairs."""
        normalized_symbols = _normalize_symbols(symbols)
        requested_timeframes = _normalize_timeframes(timeframes)
        if not normalized_symbols or not requested_timeframes:
            return
        loop = asyncio.get_running_loop()
        if self._pending_lock is None:
            self._pending_lock = asyncio.Lock()
        for sym in normalized_symbols:
            self._pending_refreshes.setdefault(sym, set()).update(requested_timeframes)
        if self._targeted_task is None or self._targeted_task.done():
            self._targeted_task = loop.create_task(self._run_targeted_refreshes())

    async def _pop_pending_refreshes(self) -> dict[str, list[str]]:
        if self._pending_lock is None:
            return {}
        async with self._pending_lock:
            pending = {
                sym: sorted(tfs, key=_SCORE_FIELDS.index)
                for sym, tfs in self._pending_refreshes.items()
                if tfs
            }
            self._pending_refreshes.clear()
            return pending

    async def _run_targeted_refreshes(self) -> None:
        while True:
            pending = await self._pop_pending_refreshes()
            if not pending:
                return
            grouped: dict[tuple[str, ...], list[str]] = {}
            for sym, tfs in pending.items():
                grouped.setdefault(tuple(tfs), []).append(sym)
            loop = asyncio.get_event_loop()
            for tfs, symbols in grouped.items():
                try:
                    await loop.run_in_executor(None, _compute_and_upsert_timeframes, symbols, list(tfs))
                except Exception as exc:
                    logger.error("Targeted technical refresh error: %s", exc)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.get_running_loop().create_task(self._loop())

    def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        if self._targeted_task and not self._targeted_task.done():
            self._targeted_task.cancel()

    async def _loop(self) -> None:
        logger.info("TechnicalsScorer started")

        while True:
            loop = asyncio.get_event_loop()

            priority_symbols = self._priority_symbols()
            if priority_symbols:
                try:
                    await loop.run_in_executor(None, _compute_and_upsert, priority_symbols)
                except Exception as exc:
                    logger.error("TechnicalsScorer priority tier error: %s", exc)

            universe_batch = self._next_universe_batch(set(priority_symbols))
            if universe_batch:
                try:
                    await loop.run_in_executor(None, _compute_and_upsert_universe, universe_batch)
                except Exception as exc:
                    logger.error("TechnicalsScorer universe tier error: %s", exc)

            await asyncio.sleep(INTERVAL_S)
