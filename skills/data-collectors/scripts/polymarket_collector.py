"""Polymarket Collector — Prediction market prices as signal source."""

from __future__ import annotations

from loguru import logger

from base_collector import BaseCollector, cache_key


class PolymarketCollector(BaseCollector):
    """Collect prediction market contract prices from Polymarket.

    Converts contract prices ($0-$1) to implied probabilities (0-100%).
    Focuses on macro-relevant events: Fed decisions, crypto regulation, elections.
    """

    PROVIDER = "polymarket"
    DEFAULT_TTL = 300.0

    POLYMARKET_API = "https://gamma-api.polymarket.com"

    # Keywords to find relevant macro markets
    MACRO_KEYWORDS = [
        "fed", "interest rate", "inflation", "bitcoin", "ethereum",
        "recession", "regulation", "crypto", "sec", "election",
    ]

    def collect(self, symbol: str) -> dict | None:
        """Collect prediction market data for a keyword/event."""
        return self.search_markets(symbol)

    def search_markets(self, query: str, limit: int = 10) -> dict | None:
        """Search Polymarket for markets matching a query."""
        ck = cache_key("poly_search", query)
        cached = self._get_cached(ck)
        if cached:
            return cached

        data = self._fetch_with_retry(
            f"{self.POLYMARKET_API}/markets",
            params={"tag": query, "limit": limit, "active": "true"},
        )
        if not data:
            # Try text search
            data = self._fetch_with_retry(
                f"{self.POLYMARKET_API}/markets",
                params={"limit": limit, "active": "true"},
            )
        if not data:
            return None

        markets = data if isinstance(data, list) else data.get("data", [])
        result = {
            "query": query,
            "markets": [
                self._parse_market(m) for m in markets if m
            ],
            "source": "polymarket",
        }
        self._set_cached(ck, result)
        return result

    def collect_macro_events(self) -> list[dict]:
        """Collect implied probabilities for key macro events."""
        ck = "poly_macro_events"
        cached = self._get_cached(ck)
        if cached:
            return cached

        events = []
        for keyword in self.MACRO_KEYWORDS:
            result = self.search_markets(keyword, limit=3)
            if result and result.get("markets"):
                events.extend(result["markets"])

        self._set_cached(ck, events, ttl=600)
        return events

    def get_implied_probability(self, market_id: str) -> dict | None:
        """Get implied probability for a specific market."""
        ck = cache_key("poly_prob", market_id)
        cached = self._get_cached(ck)
        if cached:
            return cached

        data = self._fetch_with_retry(f"{self.POLYMARKET_API}/markets/{market_id}")
        if not data:
            return None

        result = self._parse_market(data)
        self._set_cached(ck, result)
        return result

    def _parse_market(self, market: dict) -> dict:
        """Parse a Polymarket market into standardized format."""
        outcomes = market.get("outcomes", [])
        outcome_prices = market.get("outcomePrices", [])

        # Parse prices — they represent implied probabilities
        probabilities = {}
        if isinstance(outcome_prices, str):
            try:
                import json
                outcome_prices = json.loads(outcome_prices)
            except Exception:
                outcome_prices = []

        for i, outcome in enumerate(outcomes):
            price = 0.0
            if i < len(outcome_prices):
                try:
                    price = float(outcome_prices[i])
                except (ValueError, TypeError):
                    pass
            probabilities[outcome] = round(price * 100, 2)  # Convert to %

        return {
            "id": market.get("id", ""),
            "question": market.get("question", ""),
            "description": market.get("description", "")[:200],
            "outcomes": outcomes,
            "implied_probabilities": probabilities,
            "volume": float(market.get("volume", 0) or 0),
            "liquidity": float(market.get("liquidity", 0) or 0),
            "end_date": market.get("endDate", ""),
            "active": market.get("active", False),
        }
