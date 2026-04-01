"""Market Posture Analyzer — determines how much capital to deploy NOW.

Runs BEFORE any individual asset analysis. Answers:
"What percentage of portfolio should be invested vs cash?"

Output: exposure_ceiling (0-100%) and posture classification.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from loguru import logger


class Posture(str, Enum):
    NEW_ENTRY_ALLOWED = "NEW_ENTRY_ALLOWED"   # 80-100%: full deployment ok
    SELECTIVE_ENTRY = "SELECTIVE_ENTRY"         # 50-79%: only high-score entries
    REDUCE_ONLY = "REDUCE_ONLY"                # 20-49%: trim, no new buys
    CASH_PRIORITY = "CASH_PRIORITY"            # 0-19%: maximize cash


@dataclass
class MarketPosture:
    """Result of market posture analysis."""
    exposure_ceiling: float  # 0-100%
    posture: Posture
    confidence: str  # HIGH, MEDIUM, LOW
    rationale: str
    recommended_allocation: dict[str, float]  # asset_class -> %
    components: dict[str, float]  # component_name -> score 0-100


class PostureAnalyzer:
    """Calculate overall market posture / exposure ceiling.

    Components and weights:
    - Macro Regime Score: 25%
    - Market Breadth Health: 20%
    - Bubble Risk Score: 20% (inverted)
    - Volatility Regime: 15%
    - Sentiment Extremes: 10% (contrarian)
    - Momentum Breadth: 10%
    """

    WEIGHTS = {
        "macro_regime": 0.25,
        "market_breadth": 0.20,
        "bubble_risk": 0.20,
        "volatility": 0.15,
        "sentiment": 0.10,
        "momentum_breadth": 0.10,
    }

    # Regime → base score mapping
    REGIME_SCORES = {
        "Goldilocks": 90,
        "Reflation": 70,
        "Deflation": 40,
        "Stagflation": 20,
    }

    def analyze(
        self,
        regime: str = "Goldilocks",
        regime_confidence: float = 0.5,
        pct_above_sma200: float = 60.0,
        advance_decline_ratio: float = 1.0,
        bubble_score: float = 3.0,
        vix: float = 18.0,
        vix_term_contango: bool = True,
        fear_greed_value: int = 50,
        prediction_market_divergence: float = 0.0,
        pct_rsi_above_50: float = 55.0,
    ) -> MarketPosture:
        """Calculate market posture from all components.

        Args:
            regime: Current Dalio regime name.
            regime_confidence: Confidence in regime detection (0-1).
            pct_above_sma200: % of S&P500 stocks above 200-day SMA.
            advance_decline_ratio: Advance/Decline ratio.
            bubble_score: Minsky/Kindleberger score (0-15).
            vix: Current VIX level.
            vix_term_contango: True if VIX futures in contango (normal).
            fear_greed_value: Fear & Greed index (0=extreme fear, 100=extreme greed).
            prediction_market_divergence: Avg divergence from prediction markets.
            pct_rsi_above_50: % of assets with RSI > 50.
        """
        components: dict[str, float] = {}

        # 1. Macro Regime Score (25%)
        base_regime = self.REGIME_SCORES.get(regime, 50)
        components["macro_regime"] = base_regime * max(0.5, min(1.0, regime_confidence))

        # 2. Market Breadth Health (20%)
        breadth = self._score_breadth(pct_above_sma200, advance_decline_ratio)
        components["market_breadth"] = breadth

        # 3. Bubble Risk Score (20%) — INVERTED
        bubble_inverted = self._score_bubble_risk(bubble_score)
        components["bubble_risk"] = bubble_inverted

        # 4. Volatility Regime (15%)
        vol_score = self._score_volatility(vix, vix_term_contango)
        components["volatility"] = vol_score

        # 5. Sentiment Extremes (10%) — CONTRARIAN
        sentiment_score = self._score_sentiment_contrarian(
            fear_greed_value, prediction_market_divergence
        )
        components["sentiment"] = sentiment_score

        # 6. Momentum Breadth (10%)
        components["momentum_breadth"] = min(100, max(0, pct_rsi_above_50))

        # Weighted average
        exposure_ceiling = sum(
            components[k] * self.WEIGHTS[k] for k in self.WEIGHTS
        )
        exposure_ceiling = round(max(0, min(100, exposure_ceiling)), 1)

        # Classify posture
        posture = self._classify_posture(exposure_ceiling)

        # Confidence based on component agreement
        scores = list(components.values())
        spread = max(scores) - min(scores)
        if spread < 30:
            confidence = "HIGH"
        elif spread < 50:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        # Recommended allocation
        allocation = self._recommend_allocation(posture, regime)

        rationale = self._build_rationale(components, posture, exposure_ceiling)

        logger.info(
            f"Market Posture: {posture.value} — "
            f"ceiling={exposure_ceiling:.1f}%, confidence={confidence}"
        )

        return MarketPosture(
            exposure_ceiling=exposure_ceiling,
            posture=posture,
            confidence=confidence,
            rationale=rationale,
            recommended_allocation=allocation,
            components=components,
        )

    def _score_breadth(self, pct_above_sma200: float, ad_ratio: float) -> float:
        # % above SMA200: 70%+ = healthy, 30%- = unhealthy
        breadth_score = min(100, max(0, pct_above_sma200 * 1.2))
        # A/D ratio bonus: >1.5 = strong, <0.5 = weak
        if ad_ratio >= 1.5:
            breadth_score = min(100, breadth_score + 15)
        elif ad_ratio < 0.5:
            breadth_score = max(0, breadth_score - 20)
        return breadth_score

    def _score_bubble_risk(self, bubble_score: float) -> float:
        """Invert bubble score: high bubble risk → low posture score."""
        # Bubble score 0-15 → posture 100-0
        # Normal(0-4)=90, Caution(5-7)=60, Elevated(8-9)=40,
        # Euphoria(10-12)=20, Critical(13-15)=5
        if bubble_score <= 4:
            return 90
        elif bubble_score <= 7:
            return 60
        elif bubble_score <= 9:
            return 40
        elif bubble_score <= 12:
            return 20
        return 5

    def _score_volatility(self, vix: float, contango: bool) -> float:
        if vix < 15:
            score = 90.0
        elif vix < 20:
            score = 75.0
        elif vix < 25:
            score = 60.0
        elif vix < 30:
            score = 35.0
        elif vix < 35:
            score = 15.0
        else:
            score = 5.0

        # VIX in backwardation = fear premium = more cautious
        if not contango:
            score = max(0, score - 15)
        return score

    def _score_sentiment_contrarian(
        self, fear_greed: int, market_divergence: float
    ) -> float:
        """Contrarian: extreme fear = opportunity, extreme greed = danger."""
        if fear_greed <= 10:
            score = 90  # Extreme fear = buy opportunity
        elif fear_greed <= 25:
            score = 80
        elif fear_greed <= 40:
            score = 60
        elif fear_greed <= 60:
            score = 50  # Neutral
        elif fear_greed <= 75:
            score = 35
        elif fear_greed <= 90:
            score = 20
        else:
            score = 10  # Extreme greed = danger

        # Prediction market divergence amplifies signal
        if abs(market_divergence) > 10:
            score = min(100, score + 10)

        return score

    def _classify_posture(self, ceiling: float) -> Posture:
        if ceiling >= 80:
            return Posture.NEW_ENTRY_ALLOWED
        elif ceiling >= 50:
            return Posture.SELECTIVE_ENTRY
        elif ceiling >= 20:
            return Posture.REDUCE_ONLY
        return Posture.CASH_PRIORITY

    def _recommend_allocation(self, posture: Posture, regime: str) -> dict[str, float]:
        """Recommend asset class allocation based on posture and regime."""
        base = {
            Posture.NEW_ENTRY_ALLOWED: {"stocks": 45, "crypto": 25, "commodities": 15, "cash": 15},
            Posture.SELECTIVE_ENTRY: {"stocks": 35, "crypto": 15, "commodities": 10, "cash": 40},
            Posture.REDUCE_ONLY: {"stocks": 20, "crypto": 5, "commodities": 10, "cash": 65},
            Posture.CASH_PRIORITY: {"stocks": 5, "crypto": 0, "commodities": 5, "cash": 90},
        }
        alloc = base.get(posture, base[Posture.SELECTIVE_ENTRY]).copy()

        # Adjust for regime
        if regime == "Stagflation":
            alloc["commodities"] = min(30, alloc["commodities"] + 10)
            alloc["stocks"] = max(0, alloc["stocks"] - 10)
        elif regime == "Reflation":
            alloc["commodities"] = min(25, alloc["commodities"] + 5)
        elif regime == "Deflation":
            alloc["crypto"] = max(0, alloc["crypto"] - 5)

        return alloc

    def _build_rationale(
        self, components: dict, posture: Posture, ceiling: float
    ) -> str:
        parts = [f"Exposure ceiling: {ceiling:.1f}% ({posture.value})."]
        strongest = max(components, key=components.get)  # type: ignore[arg-type]
        weakest = min(components, key=components.get)  # type: ignore[arg-type]
        parts.append(f"Strongest: {strongest} ({components[strongest]:.0f}).")
        parts.append(f"Weakest: {weakest} ({components[weakest]:.0f}).")
        return " ".join(parts)
