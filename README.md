<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="public/dailyiq-brand-resources/daily-iq-topbar-logo.svg">
  <source media="(prefers-color-scheme: light)" srcset="public/dailyiq-brand-resources/daily-iq-topbar-logo-black.svg">
  <img src="public/dailyiq-brand-resources/daily-iq-topbar-logo-black.svg" alt="DailyIQ" width="320" />
</picture>

**Desktop trading research workspace for users with live watchlists, technical scoring, options analytics, historical caching, and a modular Tauri-based UI.**

![Python](https://img.shields.io/badge/Python-3.11--3.12-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Sidecar-009688?style=flat&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?style=flat&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=flat&logo=typescript&logoColor=white)
![Tauri](https://img.shields.io/badge/Tauri-Desktop-FFC131?style=flat&logo=tauri&logoColor=black)
![SQLite](https://img.shields.io/badge/SQLite-Local_Cache-003B57?style=flat&logo=sqlite&logoColor=white)
![IBKR](https://img.shields.io/badge/IBKR-TWS%2FGateway-111111?style=flat)
![Yahoo Finance](https://img.shields.io/badge/Yahoo-Fallback_Data-5F01D1?style=flat)
![Finnhub](https://img.shields.io/badge/Finnhub-Optional_Fallback-00B386?style=flat)
![Supabase](https://img.shields.io/badge/Supabase-Auth-3ECF8E?style=flat&logo=supabase&logoColor=white)

</div>

---

<img src="public/dailyiq-brand-resources/dashboard-preview-v-0.2.0.png" alt="DailyIQ platform preview" width="100%" />

---

## Platform at a Glance

| Coverage | API Surface | Chart Engine | App Model |
|:---:|:---:|:---:|:---:|
| **850 enabled equities** | **30 FastAPI endpoints** | **41 indicators / strategies** | **Tauri desktop + Python sidecar** |

---

## What This Project Is

DailyIQ is a desktop-first market research and trading workspace built around IBKR connectivity (along with backups). The application combines a React/TypeScript frontend, a Tauri desktop shell, and a FastAPI sidecar backed by local SQLite storage.

It is designed to give traders a fast local workspace for:

- live watchlists and quote monitoring
- historical charting and indicator analysis
- technical scoring across multiple timeframes
- options chain inspection with computed Greeks
- portfolio review for both IBKR and manual accounts
- sector heatmaps and screener workflows

---

## System Architecture

```mermaid
graph TD
    A[Tauri Desktop Host<br/>windowing + OAuth callback + backend supervisor]
    B[React 18 + TypeScript UI<br/>dashboard, charting, heatmap, options, portfolio]
    C[Local UI State<br/>workspace.diq + watchlist.json + localStorage]
    D[FastAPI Sidecar<br/>localhost HTTP API]
    E[TechnicalsScorer<br/>in-process background task]
    F[OptionsCollectorWorker<br/>in-process background task]
    G[Watchlist Worker<br/>live quotes + snapshots + realtime bars]
    H[Valuation Worker<br/>daily enrichment scheduler]
    I[(SQLite App Data Store<br/>market.db WAL)]
    J[IBKR TWS / Gateway]
    K[Yahoo Finance]
    L[Finnhub]
    M[DailyIQ API]
    N[Supabase Auth]

    A -->|spawns, probes, restarts| D
    A -->|spawns, watches| G
    A -->|spawns, watches| H
    A -->|Tauri commands| B
    A -->|OAuth token relay| N

    B -->|localhost fetch| D
    B -->|persist workspace/settings/watchlist cache| C
    B -->|session storage| N

    D --> E
    D --> F
    D --> I
    G --> I
    H --> I
    B -. reads/writes .-> I

    D -->|portfolio reads / historical API| J
    G -->|streaming quotes + realtime bars| J
    D -->|historical/options fallback paths| K
    G -->|quote + valuation fallback| K
    G -->|optional quote fallback| L
    D -->|historical fallback| M
    G -->|quote + fundamentals fallback| M
```

- The Rust/Tauri host is the process supervisor. It auto-starts the sidecar, watchlist worker, and valuation worker, exposes Tauri commands to the frontend, and watchdog-restarts the stack when health checks fail.
- The React frontend does not talk to Python through IPC for market data. It uses direct `http://127.0.0.1:<port>` requests to the FastAPI sidecar, and separately uses Tauri APIs for window management, filesystem access, and desktop OAuth flow.
- SQLite is the shared system of record for watchlists, snapshots, historical OHLCV caches, technical scores, options chains, manual portfolio data, and local response caches. Workspace/session settings are also mirrored in app-data files and browser storage for resilience.

---

## Core Features

### Modular desktop workspace

- Multi-tab workspace with dedicated views for Dashboard, Charting, Heatmap, Screener, Options Analysis, and additional in-progress research tabs.
- Drag-resizable dashboard layout with lock/unlock controls for stable trading layouts.
- Link channels let components share symbol context across quote cards, watchlists, charts, portfolio panels, and mini heatmaps.
- Workspace state persists locally and can be exported/imported as `.diq` workspace files.
- Tauri window controls, native desktop packaging, and built-in app update support.

### Live data with layered fallbacks

- Primary market data path is Interactive Brokers TWS / Gateway.
- Watchlist and active symbol management use lease-style tracking so the backend only keeps relevant symbols warm.
- When IBKR is unavailable, the app can fall back to Yahoo Finance and optionally Finnhub depending on market session and configuration.
- Market snapshots are written into SQLite so the UI can keep rendering from cached state even when live connectivity degrades.
- Background loops also maintain broader universe snapshots for heatmap and screener views.

### Watchlists and market monitoring

- Persistent watchlist storage in SQLite.
- Quote cards and watchlist panels show last, bid, ask, spread, percent move, volume, and valuation fields.
- Watchlist rows can include technical score columns across multiple timeframes.
- Custom watchlist columns support indicator values, score rules, crossovers, and expression-based logic.
- Diagnostics endpoints exist for watchlist health and quote status inspection.

### Professional charting engine

- Custom chart engine implemented in TypeScript rather than wrapping a hosted chart dependency.
- Supports candlestick, line, area, bar, Heikin-Ashi, and volume-weighted views.
- Includes pan/zoom, crosshair, tooltip, sub-panes, indicator legends, and detached indicator pane workflows.
- Historical bars are cached locally in SQLite across intraday and daily tables.
- Chart data can come from live IBKR flow or local cached history populated through the sidecar workers.

<img src="public/dailyiq-brand-resources/chart-preview-v-0.2.0.png" alt="DailyIQ charting preview" width="100%" />

### Technical analysis and scoring

- Technical scoring pipeline computes normalized 0-100 scores for `5m`, `15m`, `1h`, `4h`, `1d`, and `1w`.
- Backend scoring is built on pandas/numpy over locally cached OHLCV data.
- The chart engine exposes 41 registered indicators and strategies, including overlays, oscillators, volume studies, technical score views, and signal strategies.
- The screener and heatmap surface cached daily/weekly scores, while watchlist-centric views can pull intraday horizons as well.

### Options analytics

- Options chain worker fetches full chains from Yahoo Finance and Interactive Brokers TWS, storing both contract metadata and point-in-time snapshots.
- All five Black-Scholes Greeks — delta, gamma, theta, vega, and rho — are computed locally via a vectorized numpy implementation against live spot and cached chain data.
- Implied volatility is solved per-contract using Brent's method (scipy) with a bisection fallback, converging to 1e-8 tolerance across up to 200 iterations. The risk-free rate is pulled live from the 10-year treasury (^TNX) and cached hourly.
- Greek computation follows a priority cascade: TWS provider Greeks are used when complete; otherwise all five are derived locally through Black-Scholes, with an error field explaining any fallback.
- The options UI groups expirations by month and displays calls and puts side-by-side by strike with all computed Greeks, IV, intrinsic and extrinsic values, volume, and open interest visible inline.
- Symbol prioritization favors manual portfolio holdings and watchlist symbols before optional broader-universe collection.

### Strategy simulations

- A TypeScript `SimulationEngine` drives step-by-step bar replay: it aggregates 1-minute OHLCV bars into any requested timeframe, applies session filtering (regular, extended, or all-hours), and evaluates strategy signals bar-by-bar.
- Supports 12+ built-in preset strategies including EMA crossovers (9/14, 5/20), RSI momentum, MACD crossover, Supertrend, DailyIQ technical score signal, and liquidity sweep detection.
- A custom strategy builder lets users define multi-condition entry/exit logic across 30+ indicator sources (RSI, MACD, EMA, Supertrend, VWAP, OBV, ATR, Stochastic, and more) using a visual condition editor with AND semantics.
- A Pine-like scripting DSL with a full lexer, parser, and AST interpreter allows writing arbitrary signal logic directly against indicator series, with support for `plot`, `shape`, `hline`, and `fill` directives.
- Per-simulation performance metrics include total PnL, win rate, Sharpe ratio (annualized, trade-based), maximum drawdown, profit factor, and average trade PnL.
- The simulation UI supports running up to 36 parallel simulations simultaneously across different symbols or strategy configurations, with adjustable playback speed and a per-sim trade log.
- A dedicated backtesting page is in progress, extending the simulation engine toward batch historical runs with persistent result storage.

### Portfolio workflows

- Native portfolio view supports connected IBKR accounts.
- Manual portfolio manager supports local accounts, positions, cash balances, and grouping.
- Portfolio tables can be sorted and customized, and can mix price fields with technical score columns.
- Position views are designed to work even when the user is not actively connected to IBKR by relying on cached quotes and manual account data.

### Heatmap and screener research views

- S&P 500-style heatmap layout sized by market cap and grouped by sector.
- Hover detail panels expose price move, sector, industry, valuation, and technical score context.
- Screener view supports search, symbol drill-in, market-cap sorting, valuation sorting, technical timeframe toggles, and verdict labels.
- Filters include watchlist, MAG 7, movers, bullish, and bearish sets.

<img src="public/dailyiq-brand-resources/heatmap-preview-v-0.2.0.png" alt="DailyIQ heatmap preview" width="100%" />

### Authentication and local-first storage

- Desktop sign-in supports Google OAuth via Supabase.
- Session persistence uses local storage on device.
- Market cache, workspace state, and operational data are stored locally in SQLite and app-managed files.

---

## Data Model

The backend persists application state in local SQLite tables, including:

- `watchlist_symbols`, `watchlist_quotes`, and `watchlist_status`
- `market_snapshots` and `active_symbols`
- `technical_scores`
- `ohlcv_5s`, `ohlcv_1m`, `ohlcv_1d`, plus bid/ask historical variants
- `option_contracts`, `option_snapshots`, and `option_chain_fetch_meta`
- manual portfolio accounts, positions, cash balances, and groups

This design keeps the UI responsive, reduces repeated external fetches, and allows the desktop app to continue working from cached state when upstream providers are slow or temporarily unavailable.

---

## API Overview

The FastAPI sidecar exposes REST endpoints covering:

- health and provider status
- Finnhub validation
- IBKR and manual portfolio operations
- watchlist read/write flows
- quotes and market snapshots (single and bulk)
- S&P 500 heatmap data
- options summary and option chain retrieval
- active-symbol registration
- technical scores and indicator reads
- historical bar delivery

### Key routes

| Method | Route | Description |
|---|---|---|
| `GET` | `/health` | Sidecar liveness + provider status |
| `GET` | `/portfolio` | Unified IBKR + manual portfolio snapshot |
| `GET` | `/watchlist` | Watchlist symbols and metadata |
| `GET` | `/quotes?symbols=AAPL,MSFT` | Per-symbol quotes from local cache |
| `POST` | `/quotes/bulk` | **Bulk quote snapshot** — accepts `{"symbols": [...]}` body; same response as `/quotes` but avoids URL-length limits for 100+ symbol lists; deduplicates symbols server-side |
| `GET` | `/market/snapshots` | Full market snapshot payloads including technicals, sentiment, and valuations |
| `GET` | `/heatmap/sp500` | S&P 500 heatmap data |
| `GET` | `/options/summary` | Options summary for a symbol |
| `GET` | `/options/chain` | Full options chain with computed Greeks |
| `GET` | `/technicals/scores` | Cached 0-100 technical scores per timeframe |
| `GET` | `/technicals/indicators` | Raw indicator values for custom specs |
| `GET` | `/historical` | Historical OHLCV bars from local cache |

### `/quotes/bulk` — bulk quote snapshot

Use this instead of `GET /quotes` when fetching quotes for large symbol lists (e.g. a terminal watchlist or screener result set). Sending 100+ symbols as a query string risks URL truncation and is slow to re-encode.

```http
POST /quotes/bulk
Content-Type: application/json

{"symbols": ["AAPL", "MSFT", "NVDA", "TSLA", "META"]}
```

Response shape is identical to `GET /quotes`:

```json
{
  "quotes": [
    {
      "symbol": "AAPL",
      "last": 189.45,
      "bid": 189.40,
      "ask": 189.50,
      "mid": 189.45,
      "open": 188.10,
      "high": 190.20,
      "low": 187.80,
      "prevClose": 188.00,
      "change": 1.45,
      "changePct": 0.77,
      "volume": 42000000,
      "spread": 0.10,
      "trailingPE": 29.1,
      "forwardPE": 26.4,
      "marketCap": 2950000000000,
      "valuationUpdatedAt": 1714000000000,
      "week52High": 198.23,
      "week52Low": 143.90,
      "source": "ibkr",
      "updatedAt": 1714050000000
    }
  ]
}
```

Fields `bid`, `ask`, `week52High`, `week52Low` are filled from `ohlcv_1m_bid/ask` and `ohlcv_1d` when the primary quote row is incomplete. Symbols not found in the cache are omitted from the response.

### `/technicals/scores` — technical scores with optional raw indicators

By default returns cached 0-100 scores per timeframe. Add `include_indicators=true` to also receive the full raw indicator values and per-indicator signal classification used to compute the score — useful for terminal dashboards that want to display RSI, MACD histogram, BB position, etc. without a separate `/technicals/indicators` round-trip.

```
GET /technicals/scores?symbols=AAPL,MSFT&timeframes=1h,1d&include_indicators=true
```

With `include_indicators=true`, each row gains an `indicators` key:

```json
[
  {
    "symbol": "AAPL",
    "score_1h": 68,
    "score_1d": 72,
    "last_updated_utc": "2026-04-26T14:30:00",
    "indicators": {
      "1h": {
        "available": true,
        "last_close": 189.45,
        "score": 68,
        "avg_signal": 0.36,
        "indicators": {
          "RSI":   {"value": 58.3},
          "%K":    {"k": 63.1},
          "STRSI": {"k": 61.4},
          "CCI":   {"value": 112.5},
          "BB":    {"upper": 192.0, "mid": 187.5, "lower": 183.0, "close": 189.45},
          "BBP":   {"value": 0.71},
          "MA":    {"value": 186.2},
          "VWAP":  {"value": 188.9},
          "ST":    {"direction": "BULL"},
          "REG":   {"slope": 0.04},
          "MS":    {"value": 0.12}
        }
      },
      "1d": {"available": true, "last_close": 189.45, "score": 72, ...}
    }
  }
]
```

Timeframes where insufficient OHLCV history exists return `{"available": false}`.

---

## Tech Stack

| Layer | Technologies |
|---|---|
| **Desktop Shell** | Tauri 1 |
| **Frontend** | React 18, TypeScript 5, Vite, React Router |
| **Backend** | Python 3.11-3.12, FastAPI, Uvicorn |
| **Data / Analytics** | pandas, numpy, scipy |
| **Broker / Market Data** | Interactive Brokers, Yahoo Finance, Finnhub |
| **Database** | SQLite |
| **Auth** | Supabase OAuth |

---

## Repository Structure

```text
src/         React frontend, pages, hooks, dashboard components, chart engine
src-tauri/   Tauri shell, native bootstrap, updater, bundling config
backend/     FastAPI sidecar, data workers, SQLite helpers, regression tests
data/        Static ticker metadata and local runtime settings
public/      Brand assets and symbol logos
```

---

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.12 recommended
- Interactive Brokers TWS or IB Gateway for live broker connectivity
- Optional: Finnhub API key
- Supabase project credentials for desktop authentication (not required for .exe download)

### Install

```bash
npm install
```

For backend setup, the repo includes an automated bootstrap script:

```bash
npm run setup:backend
```

That script installs `uv`, provisions Python 3.12, creates `backend/.venv`, and installs backend dependencies.

### Run the frontend

```bash
npm run dev
```

### Run the desktop app

```bash
npm run tauri dev
```

### Run the FastAPI sidecar directly

```bash
python3 backend/main.py --port 18100
```

### Run background workers directly

```bash
python3 backend/worker_watchlist.py
python3 backend/worker_options.py
```

---

## Validation

Frontend:

```bash
npm run build
```

Backend syntax check:

```bash
python3 -m py_compile backend/main.py backend/worker_watchlist.py backend/db_utils.py
```

Backend regression tests live under `backend/tests/`.

---
