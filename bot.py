"""
Main bot loop:
  1. Scrape fresh market data (Polymarket + Kalshi)
  2. Ask Claude to identify opportunities
  3. Execute recommended trades on Kalshi
  4. Repeat on schedule
"""
import os
import sys
import time
import schedule
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

from db.database    import init_db, upsert_markets, insert_snapshots, get_conn
from scrapers.polymarket import PolymarketScraper
from scrapers.kalshi     import KalshiScraper
import strategy
import executor

POLL_INTERVAL        = int(os.getenv("POLL_INTERVAL",        "300"))   # scrape every 5 min
TRADE_INTERVAL       = int(os.getenv("TRADE_INTERVAL",       "900"))   # trade every 15 min
KALSHI_RESCRAPE_MINS = int(os.getenv("KALSHI_RESCRAPE_MINS", "240"))   # re-scrape Kalshi every 4h
DRY_RUN              = os.getenv("DRY_RUN", "true").lower() == "true"


def _kalshi_data_is_fresh() -> bool:
    """Returns True if Kalshi was scraped within KALSHI_RESCRAPE_MINS."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT MAX(timestamp) FROM snapshots WHERE source='kalshi'"
        ).fetchone()
    if not row or not row[0]:
        return False
    last = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    age_mins = (datetime.now(timezone.utc) - last).total_seconds() / 60
    print(f"[bot] Kalshi data age: {age_mins:.0f} min (rescrape after {KALSHI_RESCRAPE_MINS} min)")
    return age_mins < KALSHI_RESCRAPE_MINS


def scrape_all():
    # Always scrape Polymarket (fast, ~30s)
    try:
        s = PolymarketScraper()
        markets, snapshots = s.scrape()
        upsert_markets(markets)
        insert_snapshots(snapshots)
        print(f"[bot] Scraped polymarket: {len(markets)} markets, {len(snapshots)} snapshots")
        s.close()
    except Exception as e:
        print(f"[bot] Polymarket error: {e}")

    # Only scrape Kalshi if data is stale
    if not os.getenv("KALSHI_API_KEY"):
        return
    if _kalshi_data_is_fresh():
        print("[bot] Kalshi data is fresh — skipping rescrape")
        return
    try:
        s = KalshiScraper()
        markets, snapshots = s.scrape()
        upsert_markets(markets)
        insert_snapshots(snapshots)
        print(f"[bot] Scraped kalshi: {len(markets)} markets, {len(snapshots)} snapshots")
        s.close()
    except Exception as e:
        print(f"[bot] Kalshi error: {e}")


def trade_cycle():
    print("\n[bot] -- Trade cycle --")

    # Prefer Kalshi (we can actually trade there); fall back to Polymarket for analysis
    source = "kalshi" if os.getenv("KALSHI_API_KEY") else "polymarket"

    trades = strategy.run(source=source)

    if trades:
        print(f"[bot] Recommendations:")
        for t in trades:
            print(f"  [{t['confidence'].upper()}] {t['side'].upper()} {t['market_id']} — {t['title']}")
            print(f"         {t['reasoning']}")
        executor.execute(trades)
    else:
        print("[bot] No trades recommended this cycle.")

    print("[bot] ----------------------------------\n")


def main():
    print(f"[bot] Starting — DRY_RUN={DRY_RUN}")
    if DRY_RUN:
        print("[bot] Running in DRY RUN mode. Set DRY_RUN=false in .env to place real orders.")

    init_db()

    # Run immediately on startup
    scrape_all()
    trade_cycle()

    # Schedule recurring runs
    schedule.every(POLL_INTERVAL).seconds.do(scrape_all)
    schedule.every(TRADE_INTERVAL).seconds.do(trade_cycle)

    print(f"[bot] Scraping every {POLL_INTERVAL}s | Trading every {TRADE_INTERVAL}s")
    print("[bot] Press Ctrl+C to stop.\n")

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[bot] Shut down.")


if __name__ == "__main__":
    main()
