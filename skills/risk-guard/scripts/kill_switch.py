"""Kill Switch — Hard stop at -40% drawdown from peak.

CANNOT be disabled programmatically. Requires manual deletion of lock file.
This is the last line of defense against catastrophic losses.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from loguru import logger


class KillSwitch:
    """Hard stop mechanism that halts all trading at critical drawdown.

    When triggered:
    - Writes a lock file to disk
    - Rejects ALL subsequent trade proposals
    - Requires MANUAL file deletion to restart

    This class CANNOT disable itself. By design.
    """

    def __init__(
        self,
        max_drawdown_pct: float = -40.0,
        lock_file_path: Path | str = "data/.kill_switch_active",
    ) -> None:
        self._max_drawdown_pct = max_drawdown_pct
        self._lock_file = Path(lock_file_path)
        self._triggered_at: datetime | None = None
        self._trigger_drawdown: float | None = None

        # Check if already triggered from a previous run
        if self._lock_file.exists():
            logger.critical(
                "Kill switch lock file found on disk — system is HALTED. "
                f"Delete '{self._lock_file}' manually to restart."
            )

    @property
    def is_active(self) -> bool:
        """Check if the kill switch is currently engaged."""
        return self._lock_file.exists()

    @property
    def max_drawdown_pct(self) -> float:
        return self._max_drawdown_pct

    def check(self, current_drawdown_pct: float) -> bool:
        """Check drawdown and trigger if threshold breached.

        Args:
            current_drawdown_pct: Current drawdown from peak (negative number).

        Returns:
            True if system is OK to trade, False if kill switch is active.
        """
        if self.is_active:
            logger.warning("Kill switch is ACTIVE — all trading halted.")
            return False

        if current_drawdown_pct <= self._max_drawdown_pct:
            self._trigger(current_drawdown_pct)
            return False

        return True

    def _trigger(self, drawdown_pct: float) -> None:
        """Activate the kill switch. This CANNOT be undone programmatically."""
        self._triggered_at = datetime.now(tz=UTC)
        self._trigger_drawdown = drawdown_pct

        # Write lock file to disk
        self._lock_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock_file.write_text(
            f"KILL SWITCH ACTIVATED\n"
            f"Time: {self._triggered_at.isoformat()}\n"
            f"Drawdown: {drawdown_pct:.2f}%\n"
            f"Threshold: {self._max_drawdown_pct:.2f}%\n"
            f"\n"
            f"DELETE THIS FILE MANUALLY TO RESTART TRADING.\n"
        )

        logger.critical(
            f"KILL SWITCH TRIGGERED — Drawdown {drawdown_pct:.2f}% "
            f"exceeded threshold {self._max_drawdown_pct:.2f}%. "
            f"ALL TRADING HALTED. Delete '{self._lock_file}' to restart."
        )

    def get_status(self) -> dict:
        """Return current kill switch status for reporting."""
        return {
            "is_active": self.is_active,
            "max_drawdown_pct": self._max_drawdown_pct,
            "triggered_at": self._triggered_at.isoformat() if self._triggered_at else None,
            "trigger_drawdown": self._trigger_drawdown,
            "lock_file": str(self._lock_file),
        }
