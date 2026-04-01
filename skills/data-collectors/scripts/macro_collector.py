"""Macro Collector — FRED API for economic indicators."""

from __future__ import annotations

from loguru import logger

from base_collector import BaseCollector, cache_key


class MacroCollector(BaseCollector):
    """Collect macroeconomic data from FRED API."""

    PROVIDER = "fred"
    DEFAULT_TTL = 86400.0  # 24 hours

    FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

    # Key FRED series IDs
    SERIES = {
        "gdp": "GDP",
        "cpi": "CPIAUCSL",
        "core_cpi": "CPILFESL",
        "ppi": "PPIACO",
        "fed_funds": "FEDFUNDS",
        "yield_spread_10y2y": "T10Y2Y",
        "yield_10y": "DGS10",
        "yield_2y": "DGS2",
        "junk_bond_spread": "BAMLH0A0HYM2",
        "unemployment_claims": "ICSA",
        "unemployment_rate": "UNRATE",
        "m2_money_supply": "M2SL",
        "ism_pmi": "MANEMP",  # Manufacturing employment as proxy
        "vix": "VIXCLS",
        "wilshire_5000": "WILL5000IND",
    }

    def __init__(self, fred_api_key: str = "") -> None:
        super().__init__()
        self._api_key = fred_api_key

    def collect(self, symbol: str) -> dict | None:
        """Collect a single FRED series."""
        series_id = self.SERIES.get(symbol.lower(), symbol)
        return self.collect_series(series_id)

    def collect_series(
        self,
        series_id: str,
        limit: int = 120,
        sort_order: str = "desc",
    ) -> dict | None:
        """Fetch observations for a FRED series.

        Args:
            series_id: FRED series ID (e.g., 'GDP', 'CPIAUCSL').
            limit: Max number of observations.
            sort_order: 'asc' or 'desc'.

        Returns:
            Dict with series_id, observations (list of date/value), and metadata.
        """
        if not self._api_key:
            logger.warning("FRED API key not set — macro data unavailable.")
            return None

        ck = cache_key("fred", series_id, limit)
        cached = self._get_cached(ck)
        if cached:
            return cached

        data = self._fetch_with_retry(
            self.FRED_BASE,
            params={
                "series_id": series_id,
                "api_key": self._api_key,
                "file_type": "json",
                "limit": limit,
                "sort_order": sort_order,
            },
        )
        if not data or "observations" not in data:
            return None

        observations = []
        for obs in data["observations"]:
            val = obs.get("value", ".")
            if val == ".":
                continue
            try:
                observations.append({
                    "date": obs["date"],
                    "value": float(val),
                })
            except (ValueError, KeyError):
                continue

        result = {
            "series_id": series_id,
            "observations": observations,
            "count": len(observations),
            "latest_value": observations[0]["value"] if observations else None,
            "latest_date": observations[0]["date"] if observations else None,
        }
        self._set_cached(ck, result)
        return result

    def collect_all_macro(self) -> dict[str, dict | None]:
        """Collect all key macro indicators."""
        results = {}
        for name, series_id in self.SERIES.items():
            results[name] = self.collect_series(series_id)
        return results

    def get_latest_values(self) -> dict[str, float | None]:
        """Get latest value for each macro indicator."""
        result = {}
        for name, series_id in self.SERIES.items():
            data = self.collect_series(series_id, limit=1)
            result[name] = data["latest_value"] if data else None
        return result
