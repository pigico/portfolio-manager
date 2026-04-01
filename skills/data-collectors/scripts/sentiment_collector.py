"""Sentiment Collector — Finnhub news + Alternative.me Fear & Greed."""

from __future__ import annotations

from loguru import logger

from base_collector import BaseCollector, cache_key


class SentimentCollector(BaseCollector):
    """Collect sentiment data from multiple sources."""

    PROVIDER = "finnhub"
    DEFAULT_TTL = 900.0  # 15 min

    def __init__(self, finnhub_key: str = "") -> None:
        super().__init__()
        self._finnhub_key = finnhub_key

    def collect(self, symbol: str) -> dict | None:
        """Collect news sentiment for a symbol."""
        return self.collect_news_sentiment(symbol)

    def collect_news_sentiment(self, symbol: str) -> dict | None:
        """Get NLP-based news sentiment from Finnhub."""
        if not self._finnhub_key:
            return None

        ck = cache_key("news_sentiment", symbol)
        cached = self._get_cached(ck)
        if cached:
            return cached

        data = self._fetch_with_retry(
            "https://finnhub.io/api/v1/news-sentiment",
            params={"symbol": symbol, "token": self._finnhub_key},
        )
        if not data or "sentiment" not in data:
            return None

        s = data["sentiment"]
        result = {
            "symbol": symbol,
            "buzz_articles": data.get("buzz", {}).get("articlesInLastWeek", 0),
            "buzz_weekly_avg": data.get("buzz", {}).get("weeklyAverage", 0),
            "sentiment_score": s.get("companyNewsScore", 0),
            "sector_avg_score": s.get("sectorAverageNewsScore", 0),
            "bearish_pct": s.get("bearishPercent", 0),
            "bullish_pct": s.get("bullishPercent", 0),
            "source": "finnhub",
        }
        self._set_cached(ck, result)
        return result

    def collect_fear_greed_crypto(self) -> dict | None:
        """Get Crypto Fear & Greed Index from Alternative.me."""
        self.PROVIDER = "alternative_me"
        ck = "fear_greed_crypto"
        cached = self._get_cached(ck)
        if cached:
            return cached

        data = self._fetch_with_retry(
            "https://api.alternative.me/fng/",
            params={"limit": 30, "format": "json"},
        )
        if not data or "data" not in data:
            return None

        entries = data["data"]
        latest = entries[0] if entries else {}
        result = {
            "value": int(latest.get("value", 50)),
            "classification": latest.get("value_classification", "Neutral"),
            "timestamp": latest.get("timestamp", ""),
            "history": [
                {"value": int(e["value"]), "date": e.get("timestamp", "")}
                for e in entries[:30]
            ],
            "source": "alternative_me",
        }
        self._set_cached(ck, result)
        return result

    def collect_insider_trading(self, symbol: str) -> list[dict] | None:
        """Get insider trading data from Finnhub."""
        if not self._finnhub_key:
            return None

        ck = cache_key("insider", symbol)
        cached = self._get_cached(ck)
        if cached:
            return cached

        data = self._fetch_with_retry(
            "https://finnhub.io/api/v1/stock/insider-transactions",
            params={"symbol": symbol, "token": self._finnhub_key},
        )
        if not data or "data" not in data:
            return None

        result = [
            {
                "name": t.get("name", ""),
                "share": t.get("share", 0),
                "change": t.get("change", 0),
                "transaction_type": t.get("transactionType", ""),
                "filing_date": t.get("filingDate", ""),
            }
            for t in data["data"][:20]
        ]
        self._set_cached(ck, result, ttl=3600)
        return result

    def collect_analyst_recommendations(self, symbol: str) -> dict | None:
        """Get analyst recommendations from Finnhub."""
        if not self._finnhub_key:
            return None

        ck = cache_key("analyst_rec", symbol)
        cached = self._get_cached(ck)
        if cached:
            return cached

        data = self._fetch_with_retry(
            "https://finnhub.io/api/v1/stock/recommendation",
            params={"symbol": symbol, "token": self._finnhub_key},
        )
        if not data or not isinstance(data, list) or len(data) == 0:
            return None

        latest = data[0]
        result = {
            "symbol": symbol,
            "period": latest.get("period", ""),
            "strong_buy": latest.get("strongBuy", 0),
            "buy": latest.get("buy", 0),
            "hold": latest.get("hold", 0),
            "sell": latest.get("sell", 0),
            "strong_sell": latest.get("strongSell", 0),
            "source": "finnhub",
        }
        self._set_cached(ck, result, ttl=3600)
        return result
