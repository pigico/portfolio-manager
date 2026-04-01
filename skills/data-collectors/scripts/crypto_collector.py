"""Crypto Collector — Binance WS (real-time) + CoinGecko (enrichment)."""

from __future__ import annotations

from loguru import logger

from base_collector import BaseCollector, cache_key


class CryptoCollector(BaseCollector):
    """Collect crypto data from CoinGecko + Binance WebSocket buffer."""

    PROVIDER = "coingecko"
    DEFAULT_TTL = 300.0

    COINGECKO_BASE = "https://api.coingecko.com/api/v3"

    # Map common symbols to CoinGecko IDs
    SYMBOL_TO_ID = {
        "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
        "BNB": "binancecoin", "XRP": "ripple", "ADA": "cardano",
        "AVAX": "avalanche-2", "DOT": "polkadot", "MATIC": "matic-network",
        "LINK": "chainlink", "DOGE": "dogecoin", "SHIB": "shiba-inu",
        "ATOM": "cosmos", "LTC": "litecoin", "UNI": "uniswap",
        "NEAR": "near", "APT": "aptos", "OP": "optimism",
        "ARB": "arbitrum", "SUI": "sui",
    }

    def collect(self, symbol: str) -> dict | None:
        """Collect crypto price + market data."""
        cached = self._get_cached(cache_key("crypto_price", symbol))
        if cached:
            return cached
        data = self._fetch_coingecko_price(symbol)
        if data:
            self._set_cached(cache_key("crypto_price", symbol), data)
        return data

    def collect_market_data(self, symbol: str) -> dict | None:
        """Collect detailed market data (mcap, volume, supply, etc.)."""
        cached = self._get_cached(cache_key("crypto_market", symbol))
        if cached:
            return cached
        data = self._fetch_coingecko_detail(symbol)
        if data:
            self._set_cached(cache_key("crypto_market", symbol), data, ttl=600)
        return data

    def collect_historical(self, symbol: str, days: int = 365) -> list[dict] | None:
        """Collect historical price data."""
        cached = self._get_cached(cache_key("crypto_hist", symbol, days))
        if cached:
            return cached

        coin_id = self.SYMBOL_TO_ID.get(symbol.upper(), symbol.lower())
        data = self._fetch_with_retry(
            f"{self.COINGECKO_BASE}/coins/{coin_id}/market_chart",
            params={"vs_currency": "usd", "days": days},
        )
        if not data or "prices" not in data:
            return None

        result = []
        for ts_ms, price in data["prices"]:
            result.append({"timestamp": ts_ms, "price": price})
        self._set_cached(cache_key("crypto_hist", symbol, days), result, ttl=3600)
        return result

    def collect_global(self) -> dict | None:
        """Collect global crypto market data."""
        cached = self._get_cached("crypto_global")
        if cached:
            return cached
        data = self._fetch_with_retry(f"{self.COINGECKO_BASE}/global")
        if not data or "data" not in data:
            return None
        g = data["data"]
        result = {
            "total_market_cap_usd": g.get("total_market_cap", {}).get("usd", 0),
            "total_volume_usd": g.get("total_volume", {}).get("usd", 0),
            "btc_dominance": g.get("market_cap_percentage", {}).get("btc", 0),
            "eth_dominance": g.get("market_cap_percentage", {}).get("eth", 0),
            "active_cryptocurrencies": g.get("active_cryptocurrencies", 0),
        }
        self._set_cached("crypto_global", result, ttl=600)
        return result

    def collect_defi_tvl(self) -> dict | None:
        """Collect DeFi TVL data from CoinGecko."""
        cached = self._get_cached("defi_tvl")
        if cached:
            return cached
        data = self._fetch_with_retry(f"{self.COINGECKO_BASE}/global/decentralized_finance_defi")
        if not data or "data" not in data:
            return None
        d = data["data"]
        result = {
            "defi_market_cap": float(d.get("defi_market_cap", "0").replace(",", "")),
            "defi_to_eth_ratio": float(d.get("defi_to_eth_ratio", "0")),
            "trading_volume_24h": float(d.get("trading_volume_24h", "0").replace(",", "")),
            "defi_dominance": float(d.get("defi_dominance", "0")),
            "top_coin_name": d.get("top_coin_name", ""),
        }
        self._set_cached("defi_tvl", result, ttl=3600)
        return result

    # ── CoinGecko ────────────────────────────────────────

    def _fetch_coingecko_price(self, symbol: str) -> dict | None:
        coin_id = self.SYMBOL_TO_ID.get(symbol.upper(), symbol.lower())
        data = self._fetch_with_retry(
            f"{self.COINGECKO_BASE}/simple/price",
            params={
                "ids": coin_id,
                "vs_currencies": "usd",
                "include_24hr_change": "true",
                "include_24hr_vol": "true",
                "include_market_cap": "true",
            },
        )
        if not data or not isinstance(data, dict) or coin_id not in data:
            return None
        p = data[coin_id]
        return {
            "symbol": symbol.upper(),
            "price": _safe_float(p.get("usd", 0)),
            "change_24h_pct": _safe_float(p.get("usd_24h_change", 0)),
            "volume_24h": _safe_float(p.get("usd_24h_vol", 0)),
            "market_cap": _safe_float(p.get("usd_market_cap", 0)),
            "source": "coingecko",
        }

    def _fetch_coingecko_detail(self, symbol: str) -> dict | None:
        coin_id = self.SYMBOL_TO_ID.get(symbol.upper(), symbol.lower())
        data = self._fetch_with_retry(
            f"{self.COINGECKO_BASE}/coins/{coin_id}",
            params={
                "localization": "false",
                "tickers": "false",
                "community_data": "false",
                "developer_data": "false",
            },
        )
        if not data:
            return None
        md = data.get("market_data", {})
        return {
            "symbol": symbol.upper(),
            "name": data.get("name", ""),
            "price": float(md.get("current_price", {}).get("usd", 0)),
            "market_cap": float(md.get("market_cap", {}).get("usd", 0)),
            "total_volume": float(md.get("total_volume", {}).get("usd", 0)),
            "circulating_supply": float(md.get("circulating_supply", 0) or 0),
            "total_supply": float(md.get("total_supply", 0) or 0),
            "max_supply": float(md.get("max_supply", 0) or 0),
            "ath": float(md.get("ath", {}).get("usd", 0)),
            "atl": float(md.get("atl", {}).get("usd", 0)),
            "price_change_7d": float(md.get("price_change_percentage_7d", 0) or 0),
            "price_change_30d": float(md.get("price_change_percentage_30d", 0) or 0),
            "price_change_1y": float(md.get("price_change_percentage_1y", 0) or 0),
            "source": "coingecko",
        }


def _safe_float(value) -> float:
    """Convert to float safely."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0
