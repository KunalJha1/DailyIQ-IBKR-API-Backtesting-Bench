# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**DailyIQ Backtesting Bench** — A Tauri desktop app for trading emulation, backtesting, and options analytics. Connects to Interactive Brokers TWS for live data and paper trading. Part of the DailyIQ ecosystem.

## Architecture (Three-Tier)

```
┌─────────────────────────────────────────────────────┐
│  Tauri Shell (Rust)                                 │
│  Native window, IPC, filesystem, system tray        │
├─────────────────────────────────────────────────────┤
│  Frontend: React + TypeScript + Tailwind CSS        │
│  All UI panels, charting (custom Canvas/WebGL),     │
│  strategy editor, settings                          │
├─────────────────────────────────────────────────────┤
│  Backend: Python / FastAPI + WebSocket              │
│  TWS connection (ib_insync), data pipeline,         │
│  ML training, backtesting execution                 │
├─────────────────────────────────────────────────────┤
│  Data: DuckDB (OHLCV time-series) +                │
│        SQLite (operational) +                       │
│        Supabase (auth ONLY)                         │
└─────────────────────────────────────────────────────┘
```

- **Frontend ↔ Backend**: Local WebSocket (streaming) + REST (CRUD)
- **Python sidecar**: Compiled with PyInstaller, spawned by Tauri
- **TWS data flow**: Real-time bars → write queue → DuckDB (1s batch commits)
- **ML jobs**: Async background tasks; progress streamed to frontend via WebSocket

## Data Layer Rules

- **DuckDB**: ALL market/OHLCV data. Columnar storage for fast resampling and analytics.
  - Primary table: `ohlcv_1m(symbol, ts, open, high, low, close, volume)`
  - Secondary: `ohlcv_5s` for active chart symbols only (30-day cache)
  - Higher timeframes resampled via `GROUP BY time_bucket()`
- **SQLite**: ALL operational data — strategies, backtest_runs, orders, positions, synthetic_datasets, watchlist, user_prefs
- **Supabase**: Auth ONLY. JWT-based SSO with DailyIQ.me. No OHLCV or operational data goes to Supabase.
  - Raw OHLCV and ML model weights are NEVER uploaded

## ML Stack (PyTorch)

- **RL Strategy Optimizer**: PPO via Stable-Baselines3 + PyTorch
- **Synthetic Data Generator**: Temporal VAE on windowed OHLCV sequences
- **Options Anomaly Detector**: Autoencoder, reconstruction error as anomaly score
- **Market Regime Classifier**: MLP, 5-class output (Strong Bull → Strong Bear)
- All ML runs locally. CPU fallback required; detect CUDA/MPS at runtime.

## Design System (Bloomberg × IBKR TWS × TradingView)

- **Dark-only**: bg-base `#0D1117`, bg-panel `#161B22`, bg-hover `#1C2128`
- **Semantic color only**: green `#00C853` (profit/buy), red `#FF3D71` (loss/sell), amber `#F59E0B` (warning), blue `#1A56DB` (interactive), purple `#8B5CF6` (ML features ONLY)
- **Typography**: JetBrains Mono for all numeric data (prices, P&L, quantities). Geist Sans (or Inter) for labels/UI text.
- **Spacing**: 4px base grid, strict multiples. Border-radius: 4px inputs, 6px buttons, 0px panels/tables.
- **No shadows, no gradients in chrome, no light mode.** Depth via bg color layering only.
- **Tables**: 32px row height, 11px data text, skeleton shimmer for loading (never spinners on tables)
- **Transitions**: 120ms ease-out on state changes. Zero transition on data updates (no flicker).

## Screen Map

| ID | Screen | Route Purpose |
|----|--------|--------------|
| S-01 | Dashboard | Portfolio health + market pulse (read-only) |
| S-02 | Chart & Trade | Multi-timeframe charting + order entry (primary screen) |
| S-03 | Portfolio | Full holdings + P&L + equity curve |
| S-04 | Order Manager | Live/historical order book |
| S-05 | Backtesting | Strategy editor + execution + results + chart replay |
| S-06 | ML Studio | RL optimizer, synthetic generator, anomaly model |
| S-07 | Options Dashboard | Chain viewer, unusual activity, GEX, IV rank |
| S-08 | Market Bias | Regime classifier, sector heatmap, VIX curve, econ calendar |
| S-09 | Settings | TWS connection, auth, data management |

## Environment & Configuration

- **Only use `.env`** — never `.env.local`, `.env.production`, `.env.something`, etc.
- Supabase credentials and connection strings go in the root `.env`
- The `init/` folder contains setup scripts for Supabase auth schema

## Init Folder

```bash
cd init/
python -m venv venv
source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
python setup_supabase.py
```

## Development Phases

1. **Foundation** (Phase 1): Tauri + Python sidecar + TWS + DuckDB + SQLite + Supabase auth + nav + Settings
2. **Charting & Portfolio** (Phase 2): Custom canvas charting + Portfolio + Order Manager
3. **Backtesting** (Phase 3): Strategy editor + engine + metrics + replay + Dashboard
4. **ML Studio** (Phase 4): RL optimizer + Temporal VAE + anomaly detector + regime classifier
5. **Options & Market Bias** (Phase 5): Options chain + GEX + unusual activity + market bias
6. **Polish** (Phase 6): Auto-updater, installers, cloud sync, perf profiling

## Key Constraints

- IBKR only (no multi-broker). Paper trading only in v1 (no live order routing).
- Charts are custom-built (Canvas/WebGL) — no third-party chart libraries.
- Target 10-20 actively monitored symbols. 5s bars only for active chart view.
- Python sidecar distributed via PyInstaller `--onedir`.
- Minimum window: 1280×800px. Optimal: 1440×900px+.
- Entitlement tiers: Free (limited), Pro (full), Admin (debug tools). Enforced via Supabase roles.
