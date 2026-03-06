import httpx
from datetime import datetime, timezone
from typing import Optional
from models import Market, MarketSnapshot
from scrapers.base import BaseScraper

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API  = "https://clob.polymarket.com"


class PolymarketScraper(BaseScraper):
    source = "polymarket"

    def __init__(self):
        self.client = httpx.Client(timeout=15)
        self._raw_cache: dict[str, dict] = {}  # market_id -> raw API dict

    def fetch_markets(self) -> list[Market]:
        markets = []
        self._raw_cache.clear()
        offset = 0
        limit = 100

        while True:
            resp = self.client.get(f"{GAMMA_API}/markets", params={
                "active": "true",
                "closed": "false",
                "limit": limit,
                "offset": offset,
            })
            resp.raise_for_status()
            data = resp.json()

            if not data:
                break

            for m in data:
                self._raw_cache[str(m["id"])] = m
                markets.append(self._parse_market(m))

            if len(data) < limit:
                break
            offset += limit

        print(f"[polymarket] Fetched {len(markets)} active markets")
        return markets

    def _parse_market(self, m: dict) -> Market:
        end_date = None
        if m.get("endDate"):
            try:
                end_date = datetime.fromisoformat(m["endDate"].replace("Z", "+00:00"))
            except ValueError:
                pass

        return Market(
            source=self.source,
            market_id=str(m["id"]),
            title=m.get("question") or m.get("title", ""),
            category=m.get("category", ""),
            end_date=end_date,
            is_active=bool(m.get("active", True)),
            url=f"https://polymarket.com/event/{m.get('slug', m['id'])}",
        )

    def fetch_snapshots(self, markets: list[Market]) -> list[MarketSnapshot]:
        now = datetime.now(timezone.utc)
        snapshots = []

        for market in markets:
            raw = self._raw_cache.get(market.market_id)
            if not raw:
                continue

            outcome_prices = raw.get("outcomePrices", [])
            yes_price, no_price = self._parse_prices(outcome_prices)

            snapshots.append(MarketSnapshot(
                market_id=market.market_id,
                source=self.source,
                timestamp=now,
                yes_price=yes_price,
                no_price=no_price,
                volume=self._to_float(raw.get("volume")),
                liquidity=self._to_float(raw.get("liquidity")),
                extra={
                    "outcomes": raw.get("outcomes", []),
                    "outcome_prices": outcome_prices,
                },
            ))

        print(f"[polymarket] Built {len(snapshots)} snapshots")
        return snapshots

    def _parse_prices(self, outcome_prices) -> tuple[Optional[float], Optional[float]]:
        if not outcome_prices:
            return None, None
        try:
            if isinstance(outcome_prices, str):
                import json
                outcome_prices = json.loads(outcome_prices)
            prices = [float(p) for p in outcome_prices]
            yes = prices[0] if len(prices) > 0 else None
            no  = prices[1] if len(prices) > 1 else (1 - yes if yes is not None else None)
            return yes, no
        except (ValueError, TypeError):
            return None, None

    def _to_float(self, val) -> Optional[float]:
        try:
            return float(val) if val is not None else None
        except (ValueError, TypeError):
            return None

    def close(self):
        self.client.close()
