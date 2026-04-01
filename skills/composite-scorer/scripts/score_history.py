"""Score History — track composite score evolution over time."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

from loguru import logger


@dataclass
class ScoreSnapshot:
    score: float
    decision: str
    timestamp: datetime


class ScoreHistory:
    """Track score evolution per asset for momentum detection and trend analysis."""

    def __init__(self, max_history: int = 100) -> None:
        self._history: dict[str, list[ScoreSnapshot]] = defaultdict(list)
        self._max = max_history

    def record(self, asset: str, score: float, decision: str) -> None:
        """Record a new score snapshot."""
        self._history[asset].append(
            ScoreSnapshot(score=score, decision=decision, timestamp=datetime.now(tz=UTC))
        )
        # Trim to max
        if len(self._history[asset]) > self._max:
            self._history[asset] = self._history[asset][-self._max:]

    def get_history(self, asset: str) -> list[ScoreSnapshot]:
        return list(self._history.get(asset, []))

    def consecutive_rising_periods(self, asset: str) -> int:
        """Count how many consecutive periods the score has been rising."""
        history = self._history.get(asset, [])
        if len(history) < 2:
            return 0
        count = 0
        for i in range(len(history) - 1, 0, -1):
            if history[i].score > history[i - 1].score:
                count += 1
            else:
                break
        return count

    def score_changed_significantly(
        self, asset: str, threshold: float = 10.0
    ) -> tuple[bool, float]:
        """Check if score changed significantly since last recording.

        Returns (changed, delta).
        """
        history = self._history.get(asset, [])
        if len(history) < 2:
            return False, 0.0
        delta = history[-1].score - history[-2].score
        return abs(delta) >= threshold, delta

    def get_all_latest(self) -> dict[str, ScoreSnapshot]:
        """Get the most recent score for each tracked asset."""
        return {
            asset: snapshots[-1]
            for asset, snapshots in self._history.items()
            if snapshots
        }
