"""Stock Collector — Alpha Vantage → FMP → yfinance fallback chain."""

from __future__ import annotations

from loguru import logger

from base_collector import BaseCollector, cache_key


class StockCollector(BaseCollector):
    """Collect stock data with fallback chain: Alpha Vantage → FMP → yfinance."""

    PROVIDER = "alpha_vantage"
    DEFAULT_TTL = 300.0  # 5 min for prices

    def __init__(
        self,
        alpha_vantage_key: str = "",
        fmp_key: str = "",
    ) -> None:
        super().__init__()
        self._av_key = alpha_vantage_key
        self._fmp_key = fmp_key

    def collect(self, symbol: str) -> dict | None:
        """Collect stock price + fundamentals via fallback chain."""
        cached = self._get_cached(cache_key("stock_price", symbol))
        if cached:
            return cached

        data = self._fetch_alpha_vantage(symbol)
        if not data:
            data = self._fetch_fmp(symbol)
        if not data:
            data = self._fetch_yfinance(symbol)
        if data:
            self._set_cached(cache_key("stock_price", symbol), data)
        return data

    def collect_fundamentals(self, symbol: str) -> dict | None:
        """Collect fundamental data (income statement, balance sheet, ratios)."""
        cached = self._get_cached(cache_key("stock_fund", symbol))
        if cached:
            return cached

        data = self._fetch_fmp_fundamentals(symbol)
        if not data:
            data = self._fetch_av_fundamentals(symbol)
        if data:
            self._set_cached(cache_key("stock_fund", symbol), data, ttl=3600)
        return data

    def collect_historical(self, symbol: str, period: str = "1y") -> list[dict] | None:
        """Collect historical OHLCV data."""
        cached = self._get_cached(cache_key("stock_hist", symbol, period))
        if cached:
            return cached

        data = self._fetch_av_daily(symbol)
        if not data:
            data = self._fetch_yfinance_history(symbol, period)
        if data:
            self._set_cached(cache_key("stock_hist", symbol, period), data, ttl=3600)
        return data

    # ── Alpha Vantage ────────────────────────────────────

    def _fetch_alpha_vantage(self, symbol: str) -> dict | None:
        if not self._av_key:
            return None
        self.PROVIDER = "alpha_vantage"
        data = self._fetch_with_retry(
            "https://www.alphavantage.co/query",
            params={
                "function": "GLOBAL_QUOTE",
                "symbol": symbol,
                "apikey": self._av_key,
            },
        )
        if not data or "Global Quote" not in data:
            return None
        gq = data["Global Quote"]
        if not gq:
            return None
        return {
            "symbol": symbol,
            "price": float(gq.get("05. price", 0)),
            "open": float(gq.get("02. open", 0)),
            "high": float(gq.get("03. high", 0)),
            "low": float(gq.get("04. low", 0)),
            "volume": int(gq.get("06. volume", 0)),
            "change_pct": float(gq.get("10. change percent", "0").replace("%", "")),
            "source": "alpha_vantage",
        }

    def _fetch_av_daily(self, symbol: str) -> list[dict] | None:
        if not self._av_key:
            return None
        self.PROVIDER = "alpha_vantage"
        data = self._fetch_with_retry(
            "https://www.alphavantage.co/query",
            params={
                "function": "TIME_SERIES_DAILY_ADJUSTED",
                "symbol": symbol,
                "outputsize": "full",
                "apikey": self._av_key,
            },
        )
        if not data or "Time Series (Daily)" not in data:
            return None
        ts = data["Time Series (Daily)"]
        result = []
        for date_str, values in sorted(ts.items()):
            result.append({
                "date": date_str,
                "open": float(values["1. open"]),
                "high": float(values["2. high"]),
                "low": float(values["3. low"]),
                "close": float(values["4. close"]),
                "adj_close": float(values["5. adjusted close"]),
                "volume": int(values["6. volume"]),
            })
        return result

    def _fetch_av_fundamentals(self, symbol: str) -> dict | None:
        if not self._av_key:
            return None
        self.PROVIDER = "alpha_vantage"
        overview = self._fetch_with_retry(
            "https://www.alphavantage.co/query",
            params={"function": "OVERVIEW", "symbol": symbol, "apikey": self._av_key},
        )
        if not overview or "Symbol" not in overview:
            return None
        return {
            "symbol": symbol,
            "pe_ratio": _safe_float(overview.get("PERatio")),
            "pb_ratio": _safe_float(overview.get("PriceToBookRatio")),
            "ps_ratio": _safe_float(overview.get("PriceToSalesRatioTTM")),
            "ev_ebitda": _safe_float(overview.get("EVToEBITDA")),
            "roe": _safe_float(overview.get("ReturnOnEquityTTM")),
            "eps": _safe_float(overview.get("EPS")),
            "dividend_yield": _safe_float(overview.get("DividendYield")),
            "market_cap": _safe_float(overview.get("MarketCapitalization")),
            "beta": _safe_float(overview.get("Beta")),
            "52w_high": _safe_float(overview.get("52WeekHigh")),
            "52w_low": _safe_float(overview.get("52WeekLow")),
            "sector": overview.get("Sector", ""),
            "industry": overview.get("Industry", ""),
            "source": "alpha_vantage",
        }

    # ── FMP ───────────────────────────────────────────────

    def _fetch_fmp(self, symbol: str) -> dict | None:
        if not self._fmp_key:
            return None
        self.PROVIDER = "fmp"
        data = self._fetch_with_retry(
            f"https://financialmodelingprep.com/api/v3/quote/{symbol}",
            params={"apikey": self._fmp_key},
        )
        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        q = data[0]
        return {
            "symbol": symbol,
            "price": float(q.get("price", 0)),
            "open": float(q.get("open", 0)),
            "high": float(q.get("dayHigh", 0)),
            "low": float(q.get("dayLow", 0)),
            "volume": int(q.get("volume", 0)),
            "change_pct": float(q.get("changesPercentage", 0)),
            "source": "fmp",
        }

    def _fetch_fmp_fundamentals(self, symbol: str) -> dict | None:
        if not self._fmp_key:
            return None
        self.PROVIDER = "fmp"

        # Fetch ratios
        ratios = self._fetch_with_retry(
            f"https://financialmodelingprep.com/api/v3/ratios-ttm/{symbol}",
            params={"apikey": self._fmp_key},
        )
        # Fetch key metrics
        metrics = self._fetch_with_retry(
            f"https://financialmodelingprep.com/api/v3/key-metrics-ttm/{symbol}",
            params={"apikey": self._fmp_key},
        )
        # Fetch income statement
        income = self._fetch_with_retry(
            f"https://financialmodelingprep.com/api/v3/income-statement/{symbol}",
            params={"apikey": self._fmp_key, "limit": 5},
        )
        # Fetch balance sheet
        balance = self._fetch_with_retry(
            f"https://financialmodelingprep.com/api/v3/balance-sheet-statement/{symbol}",
            params={"apikey": self._fmp_key, "limit": 5},
        )
        # Fetch cash flow
        cashflow = self._fetch_with_retry(
            f"https://financialmodelingprep.com/api/v3/cash-flow-statement/{symbol}",
            params={"apikey": self._fmp_key, "limit": 5},
        )

        r = ratios[0] if ratios and isinstance(ratios, list) else {}
        m = metrics[0] if metrics and isinstance(metrics, list) else {}

        return {
            "symbol": symbol,
            "pe_ratio": _safe_float(r.get("peRatioTTM")),
            "pb_ratio": _safe_float(r.get("priceToBookRatioTTM")),
            "ps_ratio": _safe_float(r.get("priceToSalesRatioTTM")),
            "ev_ebitda": _safe_float(m.get("enterpriseValueOverEBITDATTM")),
            "roe": _safe_float(r.get("returnOnEquityTTM")),
            "roic": _safe_float(r.get("returnOnCapitalEmployedTTM")),
            "fcf_yield": _safe_float(m.get("freeCashFlowYieldTTM")),
            "debt_to_equity": _safe_float(r.get("debtEquityRatioTTM")),
            "dividend_yield": _safe_float(r.get("dividendYielTTM")),
            "payout_ratio": _safe_float(r.get("payoutRatioTTM")),
            "income_statements": income if isinstance(income, list) else [],
            "balance_sheets": balance if isinstance(balance, list) else [],
            "cash_flows": cashflow if isinstance(cashflow, list) else [],
            "source": "fmp",
        }

    # ── yfinance (fallback) ──────────────────────────────

    def _fetch_yfinance(self, symbol: str) -> dict | None:
        try:
            import yfinance as yf
        except ImportError:
            logger.debug("yfinance not installed — skipping fallback.")
            return None

        self.PROVIDER = "yfinance"
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            if not info or "regularMarketPrice" not in info:
                return None
            return {
                "symbol": symbol,
                "price": float(info.get("regularMarketPrice", 0)),
                "open": float(info.get("regularMarketOpen", 0)),
                "high": float(info.get("regularMarketDayHigh", 0)),
                "low": float(info.get("regularMarketDayLow", 0)),
                "volume": int(info.get("regularMarketVolume", 0)),
                "change_pct": float(info.get("regularMarketChangePercent", 0)),
                "source": "yfinance",
            }
        except Exception as e:
            logger.debug(f"yfinance error for {symbol}: {e}")
            return None

    def _fetch_yfinance_history(self, symbol: str, period: str) -> list[dict] | None:
        try:
            import yfinance as yf
        except ImportError:
            return None

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period)
            if df.empty:
                return None
            result = []
            for date, row in df.iterrows():
                result.append({
                    "date": str(date.date()),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                })
            return result
        except Exception as e:
            logger.debug(f"yfinance history error for {symbol}: {e}")
            return None


def _safe_float(value: Any) -> float | None:
    """Convert to float safely, returning None for invalid values."""
    if value is None or value == "" or value == "None":
        return None
    try:
        result = float(value)
        return result
    except (ValueError, TypeError):
        return None
