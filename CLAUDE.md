# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup & Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Configure credentials
cp .env.example .env
# Edit .env — KALSHI_API_KEY is required for Kalshi; Polymarket needs no auth

# Run the scraper (polls on a loop)
python main.py

# One-shot run (Ctrl+C after first poll completes)
python main.py
```

## Architecture

**Entry point**: `main.py` — initializes the DB, builds scrapers, runs them once immediately, then schedules recurring polls via `schedule`.

**Scrapers** (`scrapers/`): each platform has its own class inheriting `BaseScraper`. The `scrape()` method returns `(markets, snapshots)`. Adding a new platform means adding a file here and registering it in `main.py:build_scrapers()`.

**Models** (`models.py`): two dataclasses — `Market` (static metadata, upserted on each run) and `MarketSnapshot` (time-series row, always inserted). Prices are normalized to 0–1 probability across both platforms.

**Database** (`db/database.py`): thin SQLite wrapper. Two tables: `markets` (upserted by `source+market_id`) and `snapshots` (append-only time series). `get_latest_snapshots()` is provided for downstream bot use.

## Platform Notes

- **Polymarket**: uses the public Gamma API (`gamma-api.polymarket.com`). `outcomePrices` are already in the market list response, so snapshots are built from the same paginated call as markets — no extra per-market requests.
- **Kalshi**: uses `trading-api.kalshi.com/trade-api/v2`. Requires `KALSHI_API_KEY`. Prices come in cents (0–99) and are converted to 0–1 in `_cents_to_prob()`. Snapshots require one HTTP call per market (no batch endpoint).

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `KALSHI_API_KEY` | — | Required for Kalshi |
| `POLL_INTERVAL` | `60` | Seconds between scrape runs |
