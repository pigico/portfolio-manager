"""Composite Scorer — weighted score combining all analyzers.

Weights per asset class:
  STOCKS:      Fundamental(35%) + Technical(30%) + Macro(20%) + Sentiment(15%)
  CRYPTO:      Fundamental(25%) + Technical(35%) + Macro(20%) + Sentiment(20%)
  COMMODITIES: Fundamental(25%) + Technical(25%) + Macro(30%) + Sentiment(20%)

Decision matrix:
  80-100 = STRONG_BUY | 65-79 = BUY | 45-64 = HOLD | 30-44 = REDUCE | 0-29 = SELL
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from loguru import logger


class Decision(str, Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    SELL = "SELL"


class AssetType(str, Enum):
    STOCKS = "stocks"
    CRYPTO = "crypto"
    COMMODITIES = "commodities"


@dataclass
class CompositeScore:
    """Full scoring result for an asset."""
    asset: str
    asset_type: AssetType
    total: float                     # 0-100
    decision: Decision
    confidence: str                  # HIGH / MEDIUM / LOW
    sub_scores: dict[str, float]     # fundamental, technical, macro, sentiment
    bonuses: dict[str, float]        # momentum, contrarian, divergence
    ai_override_applied: bool = False
    ai_override_points: float = 0.0
    ai_override_rationale: str = ""
    rationale: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


# Weights per asset type
WEIGHTS: dict[str, dict[str, float]] = {
    AssetType.STOCKS: {
        "fundamental": 0.35, "technical": 0.30,
        "macro": 0.20, "sentiment": 0.15,
    },
    AssetType.CRYPTO: {
        "fundamental": 0.25, "technical": 0.35,
        "macro": 0.20, "sentiment": 0.20,
    },
    AssetType.COMMODITIES: {
        "fundamental": 0.25, "technical": 0.25,
        "macro": 0.30, "sentiment": 0.20,
    },
}

# Decision thresholds
THRESHOLDS = [
    (80, Decision.STRONG_BUY),
    (65, Decision.BUY),
    (45, Decision.HOLD),
    (30, Decision.REDUCE),
    (0, Decision.SELL),
]


class CompositeScorer:
    """Combine sub-scores into a single weighted composite score."""

    def __init__(
        self,
        momentum_bonus: float = 5.0,
        contrarian_bonus: float = 5.0,
        divergence_bonus: float = 5.0,
        max_ai_override: float = 20.0,
    ) -> None:
        self._momentum_bonus = momentum_bonus
        self._contrarian_bonus = contrarian_bonus
        self._divergence_bonus = divergence_bonus
        self._max_ai_override = max_ai_override

    def score(
        self,
        asset: str,
        asset_type: AssetType,
        fundamental_score: float = 50.0,
        technical_score: float = 50.0,
        macro_score: float = 50.0,
        sentiment_score: float = 50.0,
        # Bonus conditions
        score_rising_periods: int = 0,
        fear_greed_extreme_fear: bool = False,
        divergence_confirmed: bool = False,
        # AI override
        ai_override_points: float = 0.0,
        ai_override_rationale: str = "",
    ) -> CompositeScore:
        """Calculate composite score for an asset.

        Args:
            asset: Ticker/symbol.
            asset_type: stocks, crypto, or commodities.
            fundamental_score: 0-100 from fundamental analyzer.
            technical_score: 0-100 from technical analyzer.
            macro_score: 0-100 from macro regime alignment.
            sentiment_score: 0-100 from sentiment analyzer.
            score_rising_periods: How many consecutive periods score has risen.
            fear_greed_extreme_fear: True if Fear&Greed in Extreme Fear zone.
            divergence_confirmed: True if cross-platform divergence detected.
            ai_override_points: AI reasoning override (-20 to +20).
            ai_override_rationale: Explanation for AI override.
        """
        sub_scores = {
            "fundamental": max(0, min(100, fundamental_score)),
            "technical": max(0, min(100, technical_score)),
            "macro": max(0, min(100, macro_score)),
            "sentiment": max(0, min(100, sentiment_score)),
        }

        # Weighted base score
        weights = WEIGHTS.get(asset_type, WEIGHTS[AssetType.STOCKS])
        base_score = sum(sub_scores[k] * weights[k] for k in weights)

        # Apply bonuses
        bonuses: dict[str, float] = {}

        if score_rising_periods >= 3:
            bonuses["momentum"] = self._momentum_bonus

        if fear_greed_extreme_fear and fundamental_score > 60:
            bonuses["contrarian"] = self._contrarian_bonus

        if divergence_confirmed:
            bonuses["divergence"] = self._divergence_bonus

        total_bonus = sum(bonuses.values())

        # Apply AI override (clamped to max)
        ai_points = max(-self._max_ai_override, min(self._max_ai_override, ai_override_points))
        ai_applied = ai_points != 0

        # Final score
        total = base_score + total_bonus + ai_points
        total = round(max(0, min(100, total)), 1)

        # Decision
        decision = Decision.SELL
        for threshold, dec in THRESHOLDS:
            if total >= threshold:
                decision = dec
                break

        # Confidence
        score_spread = max(sub_scores.values()) - min(sub_scores.values())
        if score_spread < 20:
            confidence = "HIGH"
        elif score_spread < 40:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        # Rationale
        rationale_parts = [f"{asset} ({asset_type.value}): {total}/100 -> {decision.value}."]
        top_sub = max(sub_scores, key=sub_scores.get)  # type: ignore[arg-type]
        weak_sub = min(sub_scores, key=sub_scores.get)  # type: ignore[arg-type]
        rationale_parts.append(f"Strongest: {top_sub}={sub_scores[top_sub]:.0f}.")
        rationale_parts.append(f"Weakest: {weak_sub}={sub_scores[weak_sub]:.0f}.")
        if bonuses:
            rationale_parts.append(f"Bonuses: {', '.join(bonuses.keys())} (+{total_bonus:.0f}).")
        if ai_applied:
            rationale_parts.append(f"AI override: {ai_points:+.0f}pts.")

        logger.info(f"Composite: {asset} = {total}/100 ({decision.value})")

        return CompositeScore(
            asset=asset,
            asset_type=asset_type,
            total=total,
            decision=decision,
            confidence=confidence,
            sub_scores=sub_scores,
            bonuses=bonuses,
            ai_override_applied=ai_applied,
            ai_override_points=ai_points,
            ai_override_rationale=ai_override_rationale,
            rationale=" ".join(rationale_parts),
        )
