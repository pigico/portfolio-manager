"""Override Manager — logs and controls AI overrides.

Tracks all overrides with full rationale. Auto-disables AI overrides
after 5 consecutive bad results for 7 days.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from loguru import logger


@dataclass
class OverrideRecord:
    """A logged AI override."""
    asset: str
    original_score: float
    override_points: float
    final_score: float
    rationale: str
    confidence: str
    timestamp: datetime
    outcome: str | None = None  # "good" or "bad", set later
    outcome_score: float | None = None


class OverrideManager:
    """Manage AI override lifecycle: apply, log, evaluate, and auto-disable.

    Rules:
    - Max override: ±20 points
    - Final score clamped to 0-100
    - Every override logged with timestamp, context, rationale
    - If last 5 overrides worsened results → disable for 7 days
    """

    def __init__(
        self,
        max_override: float = 20.0,
        bad_override_threshold: int = 5,
        disable_days: int = 7,
    ) -> None:
        self._max_override = max_override
        self._bad_threshold = bad_override_threshold
        self._disable_days = disable_days
        self._records: list[OverrideRecord] = []
        self._disabled_until: datetime | None = None

    @property
    def is_enabled(self) -> bool:
        """Whether AI overrides are currently allowed."""
        if self._disabled_until is None:
            return True
        if datetime.now(tz=UTC) >= self._disabled_until:
            self._disabled_until = None
            logger.info("AI override auto-disable period expired — re-enabled.")
            return True
        return False

    @property
    def records(self) -> list[OverrideRecord]:
        return list(self._records)

    def apply_override(
        self,
        asset: str,
        original_score: float,
        override_points: float,
        rationale: str,
        confidence: str = "MEDIUM",
    ) -> tuple[float, bool]:
        """Apply an AI override to a score.

        Args:
            asset: Asset ticker.
            original_score: Score before override.
            override_points: Points to add (-20 to +20).
            rationale: Explanation for the override.
            confidence: AI confidence level.

        Returns:
            Tuple of (final_score, was_applied).
        """
        if not self.is_enabled:
            remaining = (self._disabled_until - datetime.now(tz=UTC)).days if self._disabled_until else 0
            logger.warning(
                f"AI override DISABLED — {remaining} days remaining. "
                "Returning original score."
            )
            return original_score, False

        # Clamp override
        clamped = max(-self._max_override, min(self._max_override, override_points))
        if clamped != override_points:
            logger.warning(f"Override clamped from {override_points} to {clamped}")

        if clamped == 0:
            return original_score, False

        final = max(0, min(100, original_score + clamped))

        record = OverrideRecord(
            asset=asset,
            original_score=original_score,
            override_points=clamped,
            final_score=final,
            rationale=rationale,
            confidence=confidence,
            timestamp=datetime.now(tz=UTC),
        )
        self._records.append(record)

        logger.info(
            f"AI OVERRIDE: {asset} {original_score:.1f} → {final:.1f} "
            f"({clamped:+.0f}pts, {confidence}). Reason: {rationale[:100]}"
        )

        return final, True

    def record_outcome(
        self,
        asset: str,
        actual_score_after: float,
    ) -> None:
        """Record the outcome of an override for quality tracking.

        A "good" override is one where the adjustment moved the score
        closer to what the actual future score turned out to be.
        """
        # Find the most recent override for this asset
        for record in reversed(self._records):
            if record.asset == asset and record.outcome is None:
                record.outcome_score = actual_score_after

                # Was the override directionally correct?
                original_error = abs(actual_score_after - record.original_score)
                override_error = abs(actual_score_after - record.final_score)

                if override_error < original_error:
                    record.outcome = "good"
                else:
                    record.outcome = "bad"

                logger.debug(
                    f"Override outcome for {asset}: {record.outcome} "
                    f"(original_err={original_error:.1f}, override_err={override_error:.1f})"
                )

                # Check for auto-disable
                self._check_auto_disable()
                break

    def _check_auto_disable(self) -> None:
        """Disable overrides if last N were all bad."""
        recent = [r for r in self._records if r.outcome is not None]
        if len(recent) < self._bad_threshold:
            return

        last_n = recent[-self._bad_threshold:]
        if all(r.outcome == "bad" for r in last_n):
            self._disabled_until = datetime.now(tz=UTC) + timedelta(days=self._disable_days)
            logger.warning(
                f"AI OVERRIDE AUTO-DISABLED for {self._disable_days} days — "
                f"last {self._bad_threshold} overrides were all bad."
            )

    def get_status(self) -> dict:
        """Return override manager status."""
        recent = [r for r in self._records if r.outcome is not None]
        good = sum(1 for r in recent if r.outcome == "good")
        bad = sum(1 for r in recent if r.outcome == "bad")
        return {
            "enabled": self.is_enabled,
            "disabled_until": self._disabled_until.isoformat() if self._disabled_until else None,
            "total_overrides": len(self._records),
            "good_outcomes": good,
            "bad_outcomes": bad,
            "success_rate": good / (good + bad) if (good + bad) > 0 else None,
        }
