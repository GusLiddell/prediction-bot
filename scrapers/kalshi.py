import os
import base64
import time
import httpx
import random
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from datetime import datetime, timezone
from typing import Optional
from models import Market, MarketSnapshot
from scrapers.base import BaseScraper

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"


def _load_private_key(path: str):
    key_path = Path(path)
    if not key_path.is_absolute():
        key_path = Path(__file__).parent.parent / path
    with open(key_path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def _sign(private_key, timestamp_ms: int, method: str, path: str) -> str:
    msg = f"{timestamp_ms}{method}{path}".encode()
    sig = private_key.sign(msg, padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode()


class KalshiScraper(BaseScraper):
    source = "kalshi"

    def __init__(self):
        api_key = os.getenv("KALSHI_API_KEY", "")
        key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH", "kalshi_private.pem")

        if not api_key:
            raise ValueError("KALSHI_API_KEY is not set.")

        self._api_key = api_key
        self._private_key = _load_private_key(key_path)
        self._client = httpx.Client(base_url=BASE_URL, timeout=15)
        self._raw_cache: dict[str, dict] = {}  # ticker -> raw API dict

    def _auth_headers(self, method: str, path: str) -> dict:
        ts = int(time.time() * 1000)
        sig = _sign(self._private_key, ts, method.upper(), path)
        return {
            "KALSHI-ACCESS-KEY": self._api_key,
            "KALSHI-ACCESS-TIMESTAMP": str(ts),
            "KALSHI-ACCESS-SIGNATURE": sig,
        }

    def _get(self, path: str, params: dict = None, retries: int = 3):
        full_path = f"/trade-api/v2{path}"
        for attempt in range(retries):
            headers = self._auth_headers("GET", full_path)
            resp = self._client.get(path, headers=headers, params=params)
            if resp.status_code == 429:
                wait = 3.0 + random.random()
                print(f"[kalshi] Rate limited, waiting {wait:.1f}s...")
                time.sleep(wait)
                continue
            return resp
        return resp  # return last response even if still 429

    def fetch_markets(self) -> list[Market]:
        markets = []
        self._raw_cache.clear()
        cursor = None

        while True:
            params: dict = {"limit": 200, "status": "open"}
            if cursor:
                params["cursor"] = cursor

            resp = self._get("/markets", params)
            resp.raise_for_status()
            data = resp.json()

            for m in data.get("markets", []):
                self._raw_cache[m["ticker"]] = m
                markets.append(self._parse_market(m))

            cursor = data.get("cursor")
            if not cursor:
                break
            time.sleep(2.0)

        print(f"[kalshi] Fetched {len(markets)} open markets")
        return markets

    def _parse_market(self, m: dict) -> Market:
        end_date = None
        if m.get("close_time"):
            try:
                end_date = datetime.fromisoformat(m["close_time"].replace("Z", "+00:00"))
            except ValueError:
                pass

        return Market(
            source=self.source,
            market_id=m["ticker"],
            title=m.get("title", ""),
            category=m.get("category", ""),
            end_date=end_date,
            is_active=m.get("status") in ("open", "active"),
            url=f"https://kalshi.com/markets/{m['ticker']}",
        )

    def fetch_snapshots(self, markets: list[Market]) -> list[MarketSnapshot]:
        now = datetime.now(timezone.utc)
        snapshots = []

        for market in markets:
            raw = self._raw_cache.get(market.market_id)
            if not raw:
                continue

            yes_price = self._cents_to_prob(raw.get("yes_ask") or raw.get("yes_bid"))
            no_price  = self._cents_to_prob(raw.get("no_ask")  or raw.get("no_bid"))

            snapshots.append(MarketSnapshot(
                market_id=market.market_id,
                source=self.source,
                timestamp=now,
                yes_price=yes_price,
                no_price=no_price,
                volume=self._to_float(raw.get("volume")),
                liquidity=self._to_float(raw.get("open_interest")),
                extra={
                    "yes_bid": raw.get("yes_bid"),
                    "yes_ask": raw.get("yes_ask"),
                    "no_bid": raw.get("no_bid"),
                    "no_ask": raw.get("no_ask"),
                    "last_price": raw.get("last_price"),
                },
            ))

        print(f"[kalshi] Built {len(snapshots)} snapshots")
        return snapshots

    def _cents_to_prob(self, cents) -> Optional[float]:
        try:
            return float(cents) / 100.0 if cents is not None else None
        except (ValueError, TypeError):
            return None

    def _to_float(self, val) -> Optional[float]:
        try:
            return float(val) if val is not None else None
        except (ValueError, TypeError):
            return None

    def close(self):
        self._client.close()
