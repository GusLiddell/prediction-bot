import os
import sys
import time
import schedule
from dotenv import load_dotenv

load_dotenv()

from db.database import init_db, upsert_markets, insert_snapshots
from scrapers.polymarket import PolymarketScraper
from scrapers.kalshi import KalshiScraper

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))


def run_scraper(scraper):
    name = scraper.source
    try:
        markets, snapshots = scraper.scrape()
        upsert_markets(markets)
        insert_snapshots(snapshots)
        print(f"[{name}] Saved {len(markets)} markets, {len(snapshots)} snapshots")
    except Exception as e:
        print(f"[{name}] ERROR: {e}", file=sys.stderr)


def build_scrapers() -> list:
    scrapers = []

    scrapers.append(PolymarketScraper())
    print("[main] Polymarket scraper ready")

    if os.getenv("KALSHI_API_KEY"):
        try:
            scrapers.append(KalshiScraper())
            print("[main] Kalshi scraper ready")
        except ValueError as e:
            print(f"[main] Skipping Kalshi: {e}")
    else:
        print("[main] KALSHI_API_KEY not set — skipping Kalshi")

    return scrapers


def main():
    init_db()
    scrapers = build_scrapers()

    if not scrapers:
        print("No scrapers configured. Exiting.")
        sys.exit(1)

    # Run immediately on startup
    for scraper in scrapers:
        run_scraper(scraper)

    # Then schedule recurring polls
    for scraper in scrapers:
        schedule.every(POLL_INTERVAL).seconds.do(run_scraper, scraper)

    print(f"[main] Polling every {POLL_INTERVAL}s. Press Ctrl+C to stop.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[main] Shutting down.")
    finally:
        for scraper in scrapers:
            scraper.close()


if __name__ == "__main__":
    main()
