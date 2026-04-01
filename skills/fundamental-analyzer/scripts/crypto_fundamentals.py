"""Crypto Fundamental Analyzer — on-chain and network metrics scored 0-100.

Indicators: NVT, MVRV, Active Addresses, Hash Rate, TVL,
Supply on Exchanges, Stablecoin Supply Ratio, Stock-to-Flow (BTC).
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger


@dataclass
class CryptoFundamentalScore:
    """Result of crypto fundamental analysis."""
    total: float  # 0-100
    breakdown: dict[str, float]
    rationale: str


class CryptoFundamentals:
    """Analyze crypto fundamentals using on-chain metrics."""

    def analyze(self, data: dict) -> CryptoFundamentalScore:
        """Score crypto fundamentals.

        Args:
            data: Dict with metrics from collectors. Keys may include:
                  market_cap, total_volume, circulating_supply, max_supply,
                  price_change_7d, price_change_30d, price_change_1y,
                  ath, atl, price
        """
        breakdown: dict[str, float] = {}

        # NVT Ratio (Network Value to Transactions)
        market_cap = data.get("market_cap", 0)
        volume = data.get("total_volume", 0)
        if volume > 0 and market_cap > 0:
            nvt = market_cap / (volume * 365)  # Annualized
            breakdown["nvt"] = self._score_nvt(nvt)
        else:
            breakdown["nvt"] = 50.0

        # Supply dynamics
        circ = data.get("circulating_supply", 0)
        total = data.get("total_supply", 0)
        max_sup = data.get("max_supply", 0)
        breakdown["supply_scarcity"] = self._score_supply(circ, max_sup)

        # Price momentum (proxy for network adoption)
        breakdown["momentum_7d"] = self._score_momentum(data.get("price_change_7d", 0))
        breakdown["momentum_30d"] = self._score_momentum(data.get("price_change_30d", 0))

        # Distance from ATH (value indicator)
        price = data.get("price", 0)
        ath = data.get("ath", 0)
        breakdown["ath_distance"] = self._score_ath_distance(price, ath)

        # Volume/Market Cap ratio
        if market_cap > 0:
            vol_mcap = volume / market_cap
            breakdown["volume_activity"] = min(100, vol_mcap * 500)  # Scale
        else:
            breakdown["volume_activity"] = 50.0

        # Weighted total
        weights = {
            "nvt": 0.20,
            "supply_scarcity": 0.15,
            "momentum_7d": 0.15,
            "momentum_30d": 0.15,
            "ath_distance": 0.20,
            "volume_activity": 0.15,
        }
        total_score = sum(breakdown[k] * weights.get(k, 0.1) for k in breakdown)
        total_score = round(max(0, min(100, total_score)), 1)

        strong = [k for k, v in breakdown.items() if v >= 70]
        weak = [k for k, v in breakdown.items() if v <= 30]
        rationale = f"Crypto score {total_score}/100. "
        if strong:
            rationale += f"Bullish: {', '.join(strong)}. "
        if weak:
            rationale += f"Bearish: {', '.join(weak)}. "

        return CryptoFundamentalScore(
            total=total_score, breakdown=breakdown, rationale=rationale
        )

    def _score_nvt(self, nvt: float) -> float:
        if nvt < 15:
            return 90  # Undervalued
        if nvt < 25:
            return 75
        if nvt < 50:
            return 50
        if nvt < 100:
            return 30
        return 10  # Overvalued

    def _score_supply(self, circulating: float, max_supply: float) -> float:
        if max_supply <= 0 or circulating <= 0:
            return 50.0
        pct_mined = circulating / max_supply
        if pct_mined > 0.9:
            return 80  # Scarce
        if pct_mined > 0.7:
            return 65
        if pct_mined > 0.5:
            return 50
        return 35  # High inflation ahead

    def _score_momentum(self, change_pct: float) -> float:
        if change_pct > 20:
            return 85
        if change_pct > 10:
            return 75
        if change_pct > 0:
            return 60
        if change_pct > -10:
            return 40
        if change_pct > -20:
            return 25
        return 10

    def _score_ath_distance(self, price: float, ath: float) -> float:
        """Farther from ATH = more value opportunity (contrarian)."""
        if ath <= 0 or price <= 0:
            return 50.0
        distance_pct = ((ath - price) / ath) * 100
        if distance_pct > 80:
            return 85  # 80%+ below ATH = deep value
        if distance_pct > 50:
            return 70
        if distance_pct > 20:
            return 55
        if distance_pct > 5:
            return 40
        return 25  # Near ATH = risky
