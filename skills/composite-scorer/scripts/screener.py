"""Screener — discover new investment opportunities across the universe.

Pre-screens a large universe, then runs full composite scoring on top candidates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from loguru import logger


@dataclass
class ScreenerResult:
    """A screened candidate with scores and signal."""
    asset: str
    asset_type: str
    composite_score: float
    decision: str
    pre_screen_passed: bool
    catalyst: str  # Why this asset is interesting now
    timestamp: datetime


class Screener:
    """Screen a universe of assets for investment opportunities.

    Pre-screening (fast):
    - Price vs SMA200 (trend)
    - RSI (not overbought)
    - Volume trend (increasing)

    Full scoring on top candidates only.
    """

    def __init__(self, top_n: int = 20, min_score: float = 65.0) -> None:
        self._top_n = top_n
        self._min_score = min_score

    def pre_screen(
        self,
        asset: str,
        price: float,
        sma200: float,
        rsi: float,
        volume_trend: str = "stable",
    ) -> tuple[bool, str]:
        """Quick pre-screen to filter obviously bad candidates.

        Returns:
            (passed, reason)
        """
        reasons = []

        # Must be above SMA200 (uptrend)
        if sma200 > 0 and price < sma200 * 0.9:
            return False, f"Price {price:.2f} well below SMA200 {sma200:.2f}"

        # RSI not extremely overbought
        if rsi > 85:
            return False, f"RSI {rsi:.1f} — extremely overbought"

        # Catalysts
        if sma200 > 0 and price > sma200:
            reasons.append("above SMA200")
        if rsi < 35:
            reasons.append("oversold RSI")
        if volume_trend == "increasing":
            reasons.append("volume increasing")

        catalyst = ", ".join(reasons) if reasons else "standard candidate"
        return True, catalyst

    def rank_candidates(
        self, candidates: list[dict]
    ) -> list[ScreenerResult]:
        """Rank screened candidates by composite score.

        Args:
            candidates: List of dicts with keys:
                asset, asset_type, composite_score, decision, catalyst

        Returns:
            Top N sorted by score, descending.
        """
        results = []
        for c in candidates:
            results.append(ScreenerResult(
                asset=c["asset"],
                asset_type=c.get("asset_type", "stocks"),
                composite_score=c.get("composite_score", 0),
                decision=c.get("decision", "HOLD"),
                pre_screen_passed=True,
                catalyst=c.get("catalyst", ""),
                timestamp=datetime.now(tz=UTC),
            ))

        # Sort by score descending
        results.sort(key=lambda r: r.composite_score, reverse=True)

        # Filter by minimum score
        results = [r for r in results if r.composite_score >= self._min_score]

        # Top N
        top = results[:self._top_n]

        if top:
            logger.info(
                f"Screener: {len(top)} candidates above {self._min_score} score. "
                f"Top: {top[0].asset} ({top[0].composite_score:.1f})"
            )
        else:
            logger.info(f"Screener: no candidates above {self._min_score} score.")

        return top
