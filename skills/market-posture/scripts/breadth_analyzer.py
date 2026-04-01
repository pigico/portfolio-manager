"""Breadth Analyzer — McClellan Oscillator, A/D line, % above SMAs."""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger


@dataclass
class BreadthAssessment:
    """Market breadth health assessment."""
    health_score: float  # 0-100
    pct_above_sma50: float
    pct_above_sma200: float
    advance_decline_ratio: float
    mcclellan_oscillator: float
    classification: str  # Strong, Healthy, Weakening, Unhealthy, Critical
    rationale: str


class BreadthAnalyzer:
    """Analyze market breadth to gauge internal market health."""

    def analyze(
        self,
        pct_above_sma50: float = 55.0,
        pct_above_sma200: float = 60.0,
        advancing_issues: int = 250,
        declining_issues: int = 250,
        advancing_volume: float = 1.0,
        declining_volume: float = 1.0,
    ) -> BreadthAssessment:
        """Analyze market breadth indicators.

        Args:
            pct_above_sma50: % of index components above 50-day SMA.
            pct_above_sma200: % of index components above 200-day SMA.
            advancing_issues: Number of advancing stocks today.
            declining_issues: Number of declining stocks today.
            advancing_volume: Total volume in advancing stocks.
            declining_volume: Total volume in declining stocks.
        """
        # Advance/Decline ratio
        ad_ratio = (
            advancing_issues / declining_issues
            if declining_issues > 0 else 2.0
        )

        # McClellan Oscillator approximation
        # (simplified — real version uses EMA of net advances)
        net_advances = advancing_issues - declining_issues
        total_issues = advancing_issues + declining_issues
        if total_issues > 0:
            mcclellan = (net_advances / total_issues) * 100
        else:
            mcclellan = 0.0

        # Health score components
        # SMA200 breadth (most important — 40%)
        sma200_score = min(100, max(0, pct_above_sma200 * 1.3))

        # SMA50 breadth (30%)
        sma50_score = min(100, max(0, pct_above_sma50 * 1.2))

        # A/D ratio (20%)
        if ad_ratio >= 2.0:
            ad_score = 95
        elif ad_ratio >= 1.5:
            ad_score = 80
        elif ad_ratio >= 1.0:
            ad_score = 60
        elif ad_ratio >= 0.7:
            ad_score = 35
        else:
            ad_score = 15

        # McClellan (10%)
        mcl_score = min(100, max(0, 50 + mcclellan))

        health = (
            sma200_score * 0.40
            + sma50_score * 0.30
            + ad_score * 0.20
            + mcl_score * 0.10
        )
        health = round(max(0, min(100, health)), 1)

        classification = self._classify(health)
        rationale = (
            f"Breadth {health:.0f}/100 ({classification}). "
            f"{pct_above_sma200:.0f}% above SMA200, "
            f"{pct_above_sma50:.0f}% above SMA50, "
            f"A/D ratio {ad_ratio:.2f}."
        )

        logger.debug(f"Breadth: {health:.1f}/100 ({classification})")

        return BreadthAssessment(
            health_score=health,
            pct_above_sma50=pct_above_sma50,
            pct_above_sma200=pct_above_sma200,
            advance_decline_ratio=round(ad_ratio, 3),
            mcclellan_oscillator=round(mcclellan, 2),
            classification=classification,
            rationale=rationale,
        )

    def _classify(self, score: float) -> str:
        if score >= 80:
            return "Strong"
        elif score >= 60:
            return "Healthy"
        elif score >= 40:
            return "Weakening"
        elif score >= 20:
            return "Unhealthy"
        return "Critical"
