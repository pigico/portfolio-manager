"""Confluence Scorer — multi-indicator alignment scoring.

Confluence rules:
- 1 indicator aligned = +1 (weak)
- 2-3 indicators aligned = +3 (moderate)
- 4+ indicators aligned = +5 (strong)
- MACD + RSI + BB aligned = +8 (high-confidence)
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from indicators import IndicatorResult, Signal


@dataclass
class TechnicalScore:
    """Final technical analysis score."""
    total: float  # 0-100
    confluence_level: str  # Weak, Moderate, Strong, High-Confidence
    dominant_direction: Signal
    bullish_count: int
    bearish_count: int
    neutral_count: int
    signals: list[IndicatorResult]
    rationale: str


class ConfluenceScorer:
    """Score technical indicators based on confluence (alignment)."""

    # Special triple-alignment bonus
    TRIPLE_BONUS_INDICATORS = {"MACD", "RSI", "BB"}

    def score(self, indicators: list[IndicatorResult]) -> TechnicalScore:
        """Calculate confluence-based technical score.

        Args:
            indicators: List of computed indicator results.

        Returns:
            TechnicalScore with total (0-100) and breakdown.
        """
        if not indicators:
            return TechnicalScore(
                total=50.0, confluence_level="None",
                dominant_direction=Signal.NEUTRAL,
                bullish_count=0, bearish_count=0, neutral_count=0,
                signals=[], rationale="No indicators computed.",
            )

        bullish = [i for i in indicators if i.signal == Signal.BULLISH]
        bearish = [i for i in indicators if i.signal == Signal.BEARISH]
        neutral = [i for i in indicators if i.signal == Signal.NEUTRAL]

        b_count = len(bullish)
        s_count = len(bearish)
        n_count = len(neutral)

        # Determine dominant direction
        if b_count > s_count:
            dominant = Signal.BULLISH
            aligned_count = b_count
        elif s_count > b_count:
            dominant = Signal.BEARISH
            aligned_count = s_count
        else:
            dominant = Signal.NEUTRAL
            aligned_count = 0

        # Base confluence score
        if aligned_count >= 4:
            confluence_points = 5
            confluence_level = "Strong"
        elif aligned_count >= 2:
            confluence_points = 3
            confluence_level = "Moderate"
        elif aligned_count >= 1:
            confluence_points = 1
            confluence_level = "Weak"
        else:
            confluence_points = 0
            confluence_level = "None"

        # Check for triple bonus (MACD + RSI + BB all aligned)
        triple_bonus = False
        triple_names = {i.name for i in indicators if i.signal == dominant}
        if self.TRIPLE_BONUS_INDICATORS.issubset(triple_names):
            confluence_points = 8
            confluence_level = "High-Confidence"
            triple_bonus = True

        # Convert to 0-100 score
        # Base: 50 (neutral). Each alignment point moves score.
        total = len(indicators)
        if total == 0:
            score = 50.0
        else:
            # Net bullish ratio: ranges from -1 (all bearish) to +1 (all bullish)
            net_ratio = (b_count - s_count) / total

            # Base score from direction (30-70 range without confluence)
            base_score = 50 + (net_ratio * 30)

            # Confluence bonus pushes towards extremes
            if dominant == Signal.BULLISH:
                base_score += confluence_points * 3
            elif dominant == Signal.BEARISH:
                base_score -= confluence_points * 3

            score = max(0, min(100, base_score))

        # Build rationale
        rationale_parts = [f"{b_count}B/{s_count}S/{n_count}N"]
        rationale_parts.append(f"confluence={confluence_level}")
        if triple_bonus:
            rationale_parts.append("MACD+RSI+BB triple alignment!")

        # Add top signals
        directional = bullish if dominant == Signal.BULLISH else bearish
        for ind in directional[:3]:
            rationale_parts.append(ind.detail)

        rationale = " | ".join(rationale_parts)

        logger.debug(
            f"Technical score: {score:.1f}/100, "
            f"{confluence_level} confluence, {dominant.value}"
        )

        return TechnicalScore(
            total=round(score, 1),
            confluence_level=confluence_level,
            dominant_direction=dominant,
            bullish_count=b_count,
            bearish_count=s_count,
            neutral_count=n_count,
            signals=indicators,
            rationale=rationale,
        )
