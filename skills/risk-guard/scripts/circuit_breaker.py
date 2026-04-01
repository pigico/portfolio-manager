"""Circuit Breaker — Pauses trading after consecutive losses.

Prevents emotional/revenge trading and limits cascading losses.
Inspired by the 0x8dxd Polymarket bot risk management approach.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from loguru import logger


class CircuitBreaker:
    """Pauses trading after consecutive losses to prevent cascading damage.

    Thresholds:
    - 3 consecutive losses → 1 hour pause
    - 5 consecutive losses → 4 hour pause
    - 8 consecutive losses → 24 hour pause + manual review required
    - After any pause: position sizes halved for next N trades
    - Reset counter after 5 consecutive wins
    """

    def __init__(
        self,
        pause_1h_after: int = 3,
        pause_4h_after: int = 5,
        pause_24h_after: int = 8,
        half_size_trades: int = 10,
        reset_after_wins: int = 5,
    ) -> None:
        self._pause_1h_after = pause_1h_after
        self._pause_4h_after = pause_4h_after
        self._pause_24h_after = pause_24h_after
        self._half_size_trades = half_size_trades
        self._reset_after_wins = reset_after_wins

        # State
        self._consecutive_losses: int = 0
        self._consecutive_wins: int = 0
        self._paused_until: datetime | None = None
        self._half_size_remaining: int = 0
        self._total_pauses: int = 0
        self._last_trigger_time: datetime | None = None

    @property
    def is_paused(self) -> bool:
        """Check if circuit breaker pause is currently active."""
        if self._paused_until is None:
            return False
        if datetime.now(tz=UTC) >= self._paused_until:
            logger.info("Circuit breaker pause expired — trading resumed.")
            self._paused_until = None
            return False
        return True

    @property
    def consecutive_losses(self) -> int:
        return self._consecutive_losses

    @property
    def should_half_size(self) -> bool:
        """Whether current trades should be half-sized."""
        return self._half_size_remaining > 0

    @property
    def pause_remaining_seconds(self) -> float:
        """Seconds remaining in current pause, or 0."""
        if not self.is_paused or self._paused_until is None:
            return 0.0
        delta = (self._paused_until - datetime.now(tz=UTC)).total_seconds()
        return max(0.0, delta)

    def record_trade_result(self, is_win: bool) -> None:
        """Record a trade result and update circuit breaker state.

        Args:
            is_win: True if the trade was profitable, False otherwise.
        """
        if is_win:
            self._consecutive_wins += 1
            self._consecutive_losses = 0

            # Decrement half-size counter on wins too
            if self._half_size_remaining > 0:
                self._half_size_remaining -= 1

            # Reset after N consecutive wins
            if self._consecutive_wins >= self._reset_after_wins:
                logger.info(
                    f"{self._consecutive_wins} consecutive wins — "
                    "circuit breaker fully reset."
                )
                self._half_size_remaining = 0
                self._consecutive_wins = 0
        else:
            self._consecutive_losses += 1
            self._consecutive_wins = 0

            # Decrement half-size counter
            if self._half_size_remaining > 0:
                self._half_size_remaining -= 1

            # Check thresholds (highest first)
            if self._consecutive_losses >= self._pause_24h_after:
                self._trigger_pause(hours=24, level="CRITICAL")
            elif self._consecutive_losses >= self._pause_4h_after:
                self._trigger_pause(hours=4, level="HIGH")
            elif self._consecutive_losses >= self._pause_1h_after:
                self._trigger_pause(hours=1, level="MEDIUM")

    def check(self) -> tuple[bool, str]:
        """Check if trading is allowed.

        Returns:
            Tuple of (allowed: bool, reason: str).
        """
        if self.is_paused:
            remaining = self.pause_remaining_seconds
            minutes = remaining / 60
            return False, (
                f"Circuit breaker ACTIVE — {self._consecutive_losses} consecutive losses. "
                f"Trading paused for {minutes:.0f} more minutes."
            )
        return True, "OK"

    def get_size_multiplier(self) -> float:
        """Get position size multiplier (1.0 = full, 0.5 = half-size)."""
        if self.should_half_size:
            return 0.5
        return 1.0

    def _trigger_pause(self, hours: int, level: str) -> None:
        """Activate a trading pause."""
        self._paused_until = datetime.now(tz=UTC) + timedelta(hours=hours)
        self._half_size_remaining = self._half_size_trades
        self._total_pauses += 1
        self._last_trigger_time = datetime.now(tz=UTC)

        logger.warning(
            f"CIRCUIT BREAKER [{level}] — {self._consecutive_losses} consecutive losses. "
            f"Trading paused for {hours} hours (until {self._paused_until.isoformat()}). "
            f"Next {self._half_size_trades} trades will be half-sized."
        )

    def reset(self) -> None:
        """Manually reset the circuit breaker (for testing or manual override)."""
        self._consecutive_losses = 0
        self._consecutive_wins = 0
        self._paused_until = None
        self._half_size_remaining = 0
        logger.info("Circuit breaker manually reset.")

    def get_status(self) -> dict:
        """Return current circuit breaker status for reporting."""
        return {
            "is_paused": self.is_paused,
            "consecutive_losses": self._consecutive_losses,
            "consecutive_wins": self._consecutive_wins,
            "paused_until": self._paused_until.isoformat() if self._paused_until else None,
            "pause_remaining_seconds": self.pause_remaining_seconds,
            "should_half_size": self.should_half_size,
            "half_size_remaining": self._half_size_remaining,
            "total_pauses": self._total_pauses,
            "size_multiplier": self.get_size_multiplier(),
        }
