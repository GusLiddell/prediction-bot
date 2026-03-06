from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Market:
    source: str          # "polymarket" | "kalshi"
    market_id: str       # platform-native ID
    title: str
    category: str
    end_date: Optional[datetime]
    is_active: bool
    url: str


@dataclass
class MarketSnapshot:
    market_id: str       # FK -> markets.market_id
    source: str
    timestamp: datetime
    yes_price: Optional[float]   # probability 0-1
    no_price: Optional[float]
    volume: Optional[float]
    liquidity: Optional[float]
    extra: dict = field(default_factory=dict)  # source-specific fields
