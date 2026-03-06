from abc import ABC, abstractmethod
from models import Market, MarketSnapshot


class BaseScraper(ABC):
    source: str

    @abstractmethod
    def fetch_markets(self) -> list[Market]:
        """Fetch all active markets from the platform."""

    @abstractmethod
    def fetch_snapshots(self, markets: list[Market]) -> list[MarketSnapshot]:
        """Fetch current price/volume snapshots for the given markets."""

    def scrape(self) -> tuple[list[Market], list[MarketSnapshot]]:
        markets = self.fetch_markets()
        snapshots = self.fetch_snapshots(markets)
        return markets, snapshots
