"""Commodity Fundamental Analyzer — futures curve, seasonals, USD correlation."""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger


@dataclass
class CommodityFundamentalScore:
    """Result of commodity fundamental analysis."""
    total: float  # 0-100
    breakdown: dict[str, float]
    rationale: str


class CommodityFundamentals:
    """Analyze commodity fundamentals."""

    def analyze(
        self,
        spot_price: float = 0,
        futures_price: float = 0,
        price_vs_200sma_pct: float = 0,
        usd_index_change_pct: float = 0,
        inventory_trend: str = "stable",
        seasonal_score: float = 50,
    ) -> CommodityFundamentalScore:
        """Score commodity fundamentals.

        Args:
            spot_price: Current spot price.
            futures_price: Nearest futures contract price.
            price_vs_200sma_pct: Current price relative to 200-day SMA (%).
            usd_index_change_pct: DXY change (inverse corr with commodities).
            inventory_trend: "building", "stable", or "drawing".
            seasonal_score: Historical seasonal strength (0-100).
        """
        breakdown: dict[str, float] = {}

        # Futures curve (contango/backwardation)
        breakdown["futures_curve"] = self._score_futures_curve(spot_price, futures_price)

        # Price vs SMA200 (trend)
        breakdown["trend"] = self._score_trend(price_vs_200sma_pct)

        # USD inverse correlation
        breakdown["usd_correlation"] = self._score_usd(usd_index_change_pct)

        # Inventory levels
        breakdown["inventories"] = self._score_inventory(inventory_trend)

        # Seasonal patterns
        breakdown["seasonal"] = max(0, min(100, seasonal_score))

        weights = {
            "futures_curve": 0.25,
            "trend": 0.25,
            "usd_correlation": 0.20,
            "inventories": 0.15,
            "seasonal": 0.15,
        }
        total = sum(breakdown[k] * weights[k] for k in weights)
        total = round(max(0, min(100, total)), 1)

        rationale = f"Commodity score {total}/100. "
        if breakdown["futures_curve"] > 65:
            rationale += "Backwardation = supply tightness. "
        if breakdown["usd_correlation"] > 65:
            rationale += "Weak USD supports prices. "

        return CommodityFundamentalScore(
            total=total, breakdown=breakdown, rationale=rationale,
        )

    def _score_futures_curve(self, spot: float, futures: float) -> float:
        if spot <= 0 or futures <= 0:
            return 50.0
        spread_pct = ((futures - spot) / spot) * 100
        # Backwardation (futures < spot) = supply shortage = bullish
        if spread_pct < -3:
            return 90
        if spread_pct < -1:
            return 75
        if spread_pct < 1:
            return 50  # Flat
        if spread_pct < 3:
            return 35  # Normal contango
        return 15  # Deep contango = oversupply

    def _score_trend(self, vs_sma200_pct: float) -> float:
        if vs_sma200_pct > 10:
            return 80
        if vs_sma200_pct > 0:
            return 65
        if vs_sma200_pct > -5:
            return 45
        if vs_sma200_pct > -15:
            return 25
        return 10

    def _score_usd(self, dxy_change_pct: float) -> float:
        # Inverse: USD weak = commodities strong
        if dxy_change_pct < -3:
            return 85
        if dxy_change_pct < -1:
            return 70
        if dxy_change_pct < 1:
            return 50
        if dxy_change_pct < 3:
            return 30
        return 15

    def _score_inventory(self, trend: str) -> float:
        mapping = {"drawing": 80, "stable": 50, "building": 25}
        return mapping.get(trend.lower(), 50)
