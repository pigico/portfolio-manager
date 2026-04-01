"""Commodity Collector — Alpha Vantage + Twelve Data."""

from __future__ import annotations

from loguru import logger

from base_collector import BaseCollector, cache_key


class CommodityCollector(BaseCollector):
    """Collect commodity data from Alpha Vantage and Twelve Data."""

    PROVIDER = "alpha_vantage"
    DEFAULT_TTL = 600.0  # 10 min

    # Commodity symbol mappings
    COMMODITY_SYMBOLS = {
        "GOLD": {"av": "XAU", "td": "XAU/USD", "yahoo": "GC=F"},
        "SILVER": {"av": "XAG", "td": "XAG/USD", "yahoo": "SI=F"},
        "OIL": {"av": None, "td": "WTI/USD", "yahoo": "CL=F"},
        "NATGAS": {"av": None, "td": "NG/USD", "yahoo": "NG=F"},
        "COPPER": {"av": None, "td": "HG/USD", "yahoo": "HG=F"},
    }

    def __init__(
        self,
        alpha_vantage_key: str = "",
        twelve_data_key: str = "",
    ) -> None:
        super().__init__()
        self._av_key = alpha_vantage_key
        self._td_key = twelve_data_key

    def collect(self, symbol: str) -> dict | None:
        """Collect commodity price data."""
        cached = self._get_cached(cache_key("commodity", symbol))
        if cached:
            return cached

        data = self._fetch_twelve_data(symbol)
        if not data:
            data = self._fetch_yfinance(symbol)
        if data:
            self._set_cached(cache_key("commodity", symbol), data)
        return data

    def collect_historical(self, symbol: str, outputsize: int = 365) -> list[dict] | None:
        """Collect historical commodity prices."""
        cached = self._get_cached(cache_key("commodity_hist", symbol))
        if cached:
            return cached

        data = self._fetch_td_timeseries(symbol, outputsize)
        if not data:
            data = self._fetch_yfinance_history(symbol)
        if data:
            self._set_cached(cache_key("commodity_hist", symbol), data, ttl=3600)
        return data

    # ── Twelve Data ──────────────────────────────────────

    def _fetch_twelve_data(self, symbol: str) -> dict | None:
        if not self._td_key:
            return None
        self.PROVIDER = "twelve_data"
        mapping = self.COMMODITY_SYMBOLS.get(symbol.upper(), {})
        td_symbol = mapping.get("td", symbol)
        if not td_symbol:
            return None

        data = self._fetch_with_retry(
            "https://api.twelvedata.com/price",
            params={"symbol": td_symbol, "apikey": self._td_key},
        )
        if not data or "price" not in data:
            return None

        return {
            "symbol": symbol.upper(),
            "price": float(data["price"]),
            "source": "twelve_data",
        }

    def _fetch_td_timeseries(self, symbol: str, outputsize: int) -> list[dict] | None:
        if not self._td_key:
            return None
        self.PROVIDER = "twelve_data"
        mapping = self.COMMODITY_SYMBOLS.get(symbol.upper(), {})
        td_symbol = mapping.get("td", symbol)
        if not td_symbol:
            return None

        data = self._fetch_with_retry(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": td_symbol,
                "interval": "1day",
                "outputsize": outputsize,
                "apikey": self._td_key,
            },
        )
        if not data or "values" not in data:
            return None

        result = []
        for v in reversed(data["values"]):
            result.append({
                "date": v["datetime"],
                "open": float(v["open"]),
                "high": float(v["high"]),
                "low": float(v["low"]),
                "close": float(v["close"]),
                "volume": int(v.get("volume", 0)),
            })
        return result

    # ── yfinance fallback ────────────────────────────────

    def _fetch_yfinance(self, symbol: str) -> dict | None:
        try:
            import yfinance as yf
        except ImportError:
            return None

        mapping = self.COMMODITY_SYMBOLS.get(symbol.upper(), {})
        yahoo_sym = mapping.get("yahoo", symbol)

        try:
            ticker = yf.Ticker(yahoo_sym)
            info = ticker.info
            if not info:
                return None
            price = info.get("regularMarketPrice") or info.get("previousClose", 0)
            return {
                "symbol": symbol.upper(),
                "price": float(price),
                "source": "yfinance",
            }
        except Exception as e:
            logger.debug(f"yfinance commodity error for {symbol}: {e}")
            return None

    def _fetch_yfinance_history(self, symbol: str) -> list[dict] | None:
        try:
            import yfinance as yf
        except ImportError:
            return None

        mapping = self.COMMODITY_SYMBOLS.get(symbol.upper(), {})
        yahoo_sym = mapping.get("yahoo", symbol)

        try:
            df = yf.Ticker(yahoo_sym).history(period="1y")
            if df.empty:
                return None
            return [
                {
                    "date": str(d.date()),
                    "open": float(r["Open"]),
                    "high": float(r["High"]),
                    "low": float(r["Low"]),
                    "close": float(r["Close"]),
                    "volume": int(r["Volume"]),
                }
                for d, r in df.iterrows()
            ]
        except Exception:
            return None
