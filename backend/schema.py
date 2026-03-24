"""Shared SQLite schema initialization helpers."""

from __future__ import annotations

import sqlite3


def ensure_base_schema(conn: sqlite3.Connection) -> None:
    """Create tables that must exist before the app starts serving requests."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS technical_scores (
            symbol           TEXT PRIMARY KEY,
            score_1m         INTEGER,
            score_5m         INTEGER,
            score_15m        INTEGER,
            score_1h         INTEGER,
            score_4h         INTEGER,
            score_1d         INTEGER,
            score_1w         INTEGER,
            last_updated_utc TEXT
        )
    """)
    for col in ("score_15m", "score_1d", "score_1w"):
        try:
            conn.execute(f"ALTER TABLE technical_scores ADD COLUMN {col} INTEGER")
        except Exception:
            pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS watchlist_symbols (
            position INTEGER PRIMARY KEY,
            symbol   TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS watchlist_quotes (
            symbol      TEXT PRIMARY KEY,
            last        REAL,
            bid         REAL,
            ask         REAL,
            mid         REAL,
            open        REAL,
            high        REAL,
            low         REAL,
            prev_close  REAL,
            change      REAL,
            change_pct  REAL,
            volume      REAL,
            spread      REAL,
            trailing_pe REAL,
            forward_pe  REAL,
            market_cap  REAL,
            valuation_updated_at INTEGER,
            source      TEXT,
            updated_at  INTEGER
        )
    """)
    for col_def in (
        "trailing_pe REAL",
        "forward_pe REAL",
        "market_cap REAL",
        "valuation_updated_at INTEGER",
    ):
        try:
            conn.execute(f"ALTER TABLE watchlist_quotes ADD COLUMN {col_def}")
        except Exception:
            pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS watchlist_status (
            symbol      TEXT PRIMARY KEY,
            state       TEXT NOT NULL,
            detail      TEXT,
            updated_at  INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS market_snapshots (
            symbol              TEXT PRIMARY KEY,
            last                REAL,
            open                REAL,
            high                REAL,
            low                 REAL,
            prev_close          REAL,
            change              REAL,
            change_pct          REAL,
            volume              REAL,
            bid                 REAL,
            ask                 REAL,
            mid                 REAL,
            spread              REAL,
            source              TEXT,
            status              TEXT,
            quote_updated_at    INTEGER,
            intraday_updated_at INTEGER,
            daily_updated_at    INTEGER,
            updated_at          INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS active_symbols (
            symbol        TEXT PRIMARY KEY,
            last_requested INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ibkr_client_leases (
            client_id  INTEGER PRIMARY KEY,
            owner      TEXT NOT NULL,
            role       TEXT NOT NULL,
            leased_at  INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_manual_accounts (
            id         TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_manual_positions (
            id               TEXT PRIMARY KEY,
            account_id       TEXT NOT NULL,
            symbol           TEXT NOT NULL,
            name             TEXT,
            currency         TEXT NOT NULL DEFAULT 'USD',
            exchange         TEXT NOT NULL DEFAULT '',
            primary_exchange TEXT,
            sec_type         TEXT NOT NULL DEFAULT 'STK',
            quantity         REAL NOT NULL,
            avg_cost         REAL NOT NULL,
            created_at       INTEGER NOT NULL,
            updated_at       INTEGER NOT NULL,
            FOREIGN KEY (account_id) REFERENCES portfolio_manual_accounts(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_portfolio_manual_positions_account_symbol
        ON portfolio_manual_positions (account_id, symbol)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_manual_cash_balances (
            id         TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            currency   TEXT NOT NULL,
            balance    REAL NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            FOREIGN KEY (account_id) REFERENCES portfolio_manual_accounts(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_portfolio_manual_cash_account_currency
        ON portfolio_manual_cash_balances (account_id, currency)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_groups (
            id         TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_portfolio_groups_name
        ON portfolio_groups (name)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_group_memberships (
            group_id    TEXT NOT NULL,
            account_ref TEXT NOT NULL,
            created_at  INTEGER NOT NULL,
            PRIMARY KEY (group_id, account_ref),
            FOREIGN KEY (group_id) REFERENCES portfolio_groups(id) ON DELETE CASCADE
        )
    """)


def ensure_historical_schema(conn: sqlite3.Connection) -> None:
    """Create SQLite tables used for historical price caching."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ohlcv_1m (
            symbol   TEXT    NOT NULL,
            ts       INTEGER NOT NULL,
            open     REAL    NOT NULL,
            high     REAL    NOT NULL,
            low      REAL    NOT NULL,
            close    REAL    NOT NULL,
            volume   REAL    NOT NULL,
            PRIMARY KEY (symbol, ts)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ohlcv_1m_sym_ts
        ON ohlcv_1m (symbol, ts)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ohlcv_1m_bid (
            symbol   TEXT    NOT NULL,
            ts       INTEGER NOT NULL,
            open     REAL    NOT NULL,
            high     REAL    NOT NULL,
            low      REAL    NOT NULL,
            close    REAL    NOT NULL,
            volume   REAL    NOT NULL,
            PRIMARY KEY (symbol, ts)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ohlcv_1m_bid_sym_ts
        ON ohlcv_1m_bid (symbol, ts)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ohlcv_1m_ask (
            symbol   TEXT    NOT NULL,
            ts       INTEGER NOT NULL,
            open     REAL    NOT NULL,
            high     REAL    NOT NULL,
            low      REAL    NOT NULL,
            close    REAL    NOT NULL,
            volume   REAL    NOT NULL,
            PRIMARY KEY (symbol, ts)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ohlcv_1m_ask_sym_ts
        ON ohlcv_1m_ask (symbol, ts)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ohlcv_1d (
            symbol   TEXT    NOT NULL,
            ts       INTEGER NOT NULL,
            open     REAL    NOT NULL,
            high     REAL    NOT NULL,
            low      REAL    NOT NULL,
            close    REAL    NOT NULL,
            volume   REAL    NOT NULL,
            PRIMARY KEY (symbol, ts)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ohlcv_1d_sym_ts
        ON ohlcv_1d (symbol, ts)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ohlcv_1d_bid (
            symbol   TEXT    NOT NULL,
            ts       INTEGER NOT NULL,
            open     REAL    NOT NULL,
            high     REAL    NOT NULL,
            low      REAL    NOT NULL,
            close    REAL    NOT NULL,
            volume   REAL    NOT NULL,
            PRIMARY KEY (symbol, ts)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ohlcv_1d_bid_sym_ts
        ON ohlcv_1d_bid (symbol, ts)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ohlcv_1d_ask (
            symbol   TEXT    NOT NULL,
            ts       INTEGER NOT NULL,
            open     REAL    NOT NULL,
            high     REAL    NOT NULL,
            low      REAL    NOT NULL,
            close    REAL    NOT NULL,
            volume   REAL    NOT NULL,
            PRIMARY KEY (symbol, ts)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ohlcv_1d_ask_sym_ts
        ON ohlcv_1d_ask (symbol, ts)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ohlcv_5s (
            symbol   TEXT    NOT NULL,
            ts       INTEGER NOT NULL,
            open     REAL    NOT NULL,
            high     REAL    NOT NULL,
            low      REAL    NOT NULL,
            close    REAL    NOT NULL,
            volume   REAL    NOT NULL,
            PRIMARY KEY (symbol, ts)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ohlcv_5s_sym_ts
        ON ohlcv_5s (symbol, ts)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS historical_priority_queue (
            symbol        TEXT    NOT NULL,
            bar_size      TEXT    NOT NULL,
            what_to_show  TEXT    NOT NULL DEFAULT 'TRADES',
            duration      TEXT    NOT NULL,
            requested_at  INTEGER NOT NULL,
            PRIMARY KEY (symbol, bar_size, what_to_show)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_historical_priority_requested
        ON historical_priority_queue (requested_at DESC)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fetch_meta (
            symbol     TEXT    NOT NULL,
            bar_size   TEXT    NOT NULL,
            fetched_at INTEGER NOT NULL,
            source     TEXT    NOT NULL DEFAULT 'yahoo',
            PRIMARY KEY (symbol, bar_size)
        )
    """)


def ensure_all_schema(conn: sqlite3.Connection) -> None:
    """Create all SQLite tables used by the backend."""
    ensure_base_schema(conn)
    ensure_historical_schema(conn)
    conn.commit()
