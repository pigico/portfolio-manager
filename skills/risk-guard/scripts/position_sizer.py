"""Position Sizer — Kelly Criterion (fractional) based sizing.

Uses 1/4 fractional Kelly by default (conservative).
Adjusts based on confidence level and circuit breaker state.
"""

from __future__ import annotations

import math

from loguru import logger

from models import Confidence


class PositionSizer:
    """Calculate optimal position size using fractional Kelly Criterion.

    Kelly formula: f* = (b*p - q) / b
    Where:
        b = odds (expected win/loss ratio)
        p = probability of winning
        q = 1 - p

    We use FRACTIONAL Kelly (1/4 by default) because:
    - Full Kelly is too aggressive and assumes perfect edge estimation
    - 1/4 Kelly provides ~75% of the growth with much lower volatility
    - This is the same approach used by the 0x8dxd Claude bot on Polymarket
    """

    def __init__(
        self,
        default_fraction: float = 0.25,
        max_position_pct: float = 20.0,
        confidence_fractions: dict[str, float] | None = None,
    ) -> None:
        self._default_fraction = default_fraction
        self._max_position_pct = max_position_pct
        self._confidence_fractions = confidence_fractions or {
            Confidence.LOW.value: 0.125,    # 1/8 Kelly
            Confidence.MEDIUM.value: 0.25,  # 1/4 Kelly
            Confidence.HIGH.value: 0.333,   # 1/3 Kelly
        }

    def calculate_kelly(
        self,
        win_probability: float,
        win_loss_ratio: float,
    ) -> float:
        """Calculate raw Kelly fraction.

        Args:
            win_probability: Estimated probability of winning (0-1).
            win_loss_ratio: Expected average win / average loss.

        Returns:
            Raw Kelly fraction (can be negative = don't bet).
        """
        if win_loss_ratio <= 0:
            return 0.0

        p = max(0.0, min(1.0, win_probability))
        q = 1.0 - p
        b = win_loss_ratio

        kelly = (b * p - q) / b
        return kelly

    def calculate_position_size_pct(
        self,
        win_probability: float,
        win_loss_ratio: float,
        confidence: Confidence = Confidence.MEDIUM,
        circuit_breaker_multiplier: float = 1.0,
    ) -> float:
        """Calculate position size as percentage of portfolio.

        Args:
            win_probability: Estimated probability of winning (0-1).
            win_loss_ratio: Expected average win / average loss.
            confidence: Signal confidence level.
            circuit_breaker_multiplier: From circuit breaker (0.5 if half-size).

        Returns:
            Position size as percentage of portfolio (0 to max_position_pct).
        """
        raw_kelly = self.calculate_kelly(win_probability, win_loss_ratio)

        if raw_kelly <= 0:
            logger.debug(
                f"Kelly is negative ({raw_kelly:.4f}) — no bet recommended. "
                f"win_prob={win_probability:.2f}, w/l_ratio={win_loss_ratio:.2f}"
            )
            return 0.0

        # Apply confidence-based fraction
        fraction = self._confidence_fractions.get(
            confidence.value, self._default_fraction
        )
        fractional_kelly = raw_kelly * fraction

        # Convert to percentage
        size_pct = fractional_kelly * 100.0

        # Apply circuit breaker multiplier
        size_pct *= circuit_breaker_multiplier

        # Cap at maximum
        size_pct = min(size_pct, self._max_position_pct)

        # Floor at 0
        size_pct = max(0.0, size_pct)

        logger.debug(
            f"Position size: raw_kelly={raw_kelly:.4f}, "
            f"fraction={fraction}, size={size_pct:.2f}%, "
            f"confidence={confidence.value}, "
            f"cb_multiplier={circuit_breaker_multiplier}"
        )

        return round(size_pct, 2)

    def estimate_from_score(
        self,
        composite_score: float,
        confidence: Confidence = Confidence.MEDIUM,
        circuit_breaker_multiplier: float = 1.0,
    ) -> float:
        """Estimate position size from composite score (0-100).

        Maps score to win probability and uses historical average
        win/loss ratio as a reasonable estimate.

        Args:
            composite_score: Composite score 0-100.
            confidence: Signal confidence.
            circuit_breaker_multiplier: From circuit breaker.

        Returns:
            Position size as percentage of portfolio.
        """
        # Map score to win probability (sigmoid-like mapping)
        # Score 50 → ~50% win prob, Score 80 → ~72%, Score 100 → ~85%
        # Conservative: even a perfect score doesn't mean 100% win
        win_prob = 0.35 + (composite_score / 100.0) * 0.50
        win_prob = max(0.35, min(0.85, win_prob))

        # Assume average win/loss ratio based on score
        # Higher scores tend to produce better risk/reward
        if composite_score >= 80:
            win_loss_ratio = 2.5
        elif composite_score >= 65:
            win_loss_ratio = 2.0
        elif composite_score >= 50:
            win_loss_ratio = 1.5
        else:
            win_loss_ratio = 1.2

        return self.calculate_position_size_pct(
            win_probability=win_prob,
            win_loss_ratio=win_loss_ratio,
            confidence=confidence,
            circuit_breaker_multiplier=circuit_breaker_multiplier,
        )

    def get_status(self) -> dict:
        """Return sizer configuration for reporting."""
        return {
            "default_fraction": self._default_fraction,
            "max_position_pct": self._max_position_pct,
            "confidence_fractions": self._confidence_fractions,
        }
