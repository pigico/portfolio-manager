"""Bubble Detector — Minsky/Kindleberger quantitative framework.

Scores market bubble risk on a 0-15 scale:
- Normal: 0-4
- Caution: 5-7
- Elevated: 8-9
- Euphoria: 10-12
- Critical: 13-15
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger


@dataclass
class BubbleAssessment:
    """Result of bubble risk analysis."""
    total_score: int  # 0-15
    classification: str  # Normal, Caution, Elevated, Euphoria, Critical
    components: dict[str, int]
    rationale: str


class BubbleDetector:
    """Quantitative bubble detection using Minsky/Kindleberger framework."""

    def analyze(
        self,
        shiller_cape: float = 20.0,
        shiller_cape_historical_avg: float = 17.0,
        margin_debt_yoy_change_pct: float = 5.0,
        put_call_ratio: float = 0.9,
        vix: float = 18.0,
        ipo_first_day_avg_return_pct: float = 15.0,
        retail_sentiment_bullish_pct: float = 40.0,
    ) -> BubbleAssessment:
        """Assess bubble risk across multiple dimensions.

        Each component contributes 0-3 points to total score (0-15 max for 5 main +
        supplementary metrics, capped at 15).
        """
        components: dict[str, int] = {}

        # 1. Shiller CAPE percentile (0-3)
        cape_ratio = shiller_cape / shiller_cape_historical_avg if shiller_cape_historical_avg else 1
        if cape_ratio < 1.0:
            components["cape_valuation"] = 0
        elif cape_ratio < 1.3:
            components["cape_valuation"] = 1
        elif cape_ratio < 1.7:
            components["cape_valuation"] = 2
        else:
            components["cape_valuation"] = 3

        # 2. Margin debt growth (0-3)
        if margin_debt_yoy_change_pct < 5:
            components["margin_debt"] = 0
        elif margin_debt_yoy_change_pct < 15:
            components["margin_debt"] = 1
        elif margin_debt_yoy_change_pct < 30:
            components["margin_debt"] = 2
        else:
            components["margin_debt"] = 3

        # 3. Put/Call ratio — LOW = complacency = bubble risk (0-3)
        if put_call_ratio > 1.0:
            components["put_call"] = 0  # Fear = no bubble
        elif put_call_ratio > 0.7:
            components["put_call"] = 1
        elif put_call_ratio > 0.5:
            components["put_call"] = 2
        else:
            components["put_call"] = 3  # Extreme complacency

        # 4. VIX — very low VIX = complacency (0-3)
        if vix > 25:
            components["vix_complacency"] = 0
        elif vix > 18:
            components["vix_complacency"] = 1
        elif vix > 12:
            components["vix_complacency"] = 2
        else:
            components["vix_complacency"] = 3

        # 5. IPO first-day returns — high = speculation (0-3)
        if ipo_first_day_avg_return_pct < 10:
            components["ipo_speculation"] = 0
        elif ipo_first_day_avg_return_pct < 25:
            components["ipo_speculation"] = 1
        elif ipo_first_day_avg_return_pct < 50:
            components["ipo_speculation"] = 2
        else:
            components["ipo_speculation"] = 3

        total = min(15, sum(components.values()))

        classification = self._classify(total)

        rationale_parts = []
        for name, score in sorted(components.items(), key=lambda x: -x[1]):
            if score >= 2:
                rationale_parts.append(f"{name}={score}/3 (elevated)")
        rationale = f"Bubble score {total}/15 ({classification}). " + (
            "Drivers: " + ", ".join(rationale_parts) if rationale_parts
            else "No major bubble indicators."
        )

        logger.info(f"Bubble assessment: {total}/15 ({classification})")

        return BubbleAssessment(
            total_score=total,
            classification=classification,
            components=components,
            rationale=rationale,
        )

    def _classify(self, score: int) -> str:
        if score <= 4:
            return "Normal"
        elif score <= 7:
            return "Caution"
        elif score <= 9:
            return "Elevated"
        elif score <= 12:
            return "Euphoria"
        return "Critical"
