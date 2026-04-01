"""RiskGuard — Master gatekeeper that validates EVERY trade.

No trade — not even in paper mode — bypasses this layer.
This is the CORE of the system, inspired by the 0x8dxd Polymarket bot lesson:
same strategy, different risk management → one bot +1,322%, the other LIQUIDATED.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from circuit_breaker import CircuitBreaker
from correlation_checker import CorrelationChecker
from kill_switch import KillSwitch
from models import (
    AssetClass,
    PortfolioState,
    TradeAction,
    TradeProposal,
    TradeResult,
)
from position_sizer import PositionSizer


class RiskGuard:
    """Singleton master gatekeeper — validates every trade proposal.

    Validation pipeline (in order):
    1. Kill switch status
    2. Circuit breaker status
    3. Daily loss limit
    4. Daily trade count
    5. Position size vs max (20%)
    6. Asset class allocation vs max (60%)
    7. Cash reserve vs min (5%)
    8. Correlation check with existing positions (< 0.7)
    9. Portfolio heat vs exposure_ceiling (from market posture)
    10. Kelly sizing calculation and adjustment
    """

    _instance: RiskGuard | None = None

    def __new__(cls, *args, **kwargs) -> RiskGuard:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        max_position_pct: float = 20.0,
        max_asset_class_pct: float = 60.0,
        min_cash_reserve_pct: float = 5.0,
        daily_loss_limit_pct: float = -15.0,
        max_trades_per_day: int = 20,
        max_new_positions_per_day: int = 5,
        trailing_stop_pct: float = -8.0,
        kill_switch_drawdown_pct: float = -40.0,
        kill_switch_lock_file: Path | str = "data/.kill_switch_active",
    ) -> None:
        # Only initialize once (singleton)
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self._max_position_pct = max_position_pct
        self._max_asset_class_pct = max_asset_class_pct
        self._min_cash_reserve_pct = min_cash_reserve_pct
        self._daily_loss_limit_pct = daily_loss_limit_pct
        self._max_trades_per_day = max_trades_per_day
        self._max_new_positions_per_day = max_new_positions_per_day
        self._trailing_stop_pct = trailing_stop_pct

        # Sub-components
        self.kill_switch = KillSwitch(
            max_drawdown_pct=kill_switch_drawdown_pct,
            lock_file_path=kill_switch_lock_file,
        )
        self.circuit_breaker = CircuitBreaker()
        self.position_sizer = PositionSizer(max_position_pct=max_position_pct)
        self.correlation_checker = CorrelationChecker()

        # Exposure ceiling from market posture (default 100% = no restriction)
        self._exposure_ceiling: float = 100.0

        logger.info("RiskGuard initialized — all trades will be validated.")

    @classmethod
    def reset_singleton(cls) -> None:
        """Reset singleton instance (for testing only)."""
        cls._instance = None

    def set_exposure_ceiling(self, ceiling: float) -> None:
        """Update exposure ceiling from market posture module.

        Args:
            ceiling: Exposure ceiling 0-100%.
        """
        self._exposure_ceiling = max(0.0, min(100.0, ceiling))
        logger.info(f"Exposure ceiling updated to {self._exposure_ceiling:.1f}%")

    def validate_trade(
        self,
        proposal: TradeProposal,
        portfolio: PortfolioState,
    ) -> TradeResult:
        """Validate a trade proposal through the full risk pipeline.

        Args:
            proposal: The proposed trade.
            portfolio: Current portfolio state.

        Returns:
            TradeResult with approval status and any adjustments.
        """
        checks_passed: list[str] = []
        checks_failed: list[str] = []

        # --- CHECK 1: Kill Switch ---
        if not self.kill_switch.check(portfolio.drawdown_pct):
            checks_failed.append("KILL_SWITCH")
            return TradeResult(
                approved=False,
                proposal=proposal,
                rejection_reason="Kill switch is ACTIVE — all trading halted.",
                checks_passed=checks_passed,
                checks_failed=checks_failed,
            )
        checks_passed.append("KILL_SWITCH")

        # --- CHECK 2: Circuit Breaker ---
        cb_ok, cb_reason = self.circuit_breaker.check()
        if not cb_ok:
            checks_failed.append("CIRCUIT_BREAKER")
            return TradeResult(
                approved=False,
                proposal=proposal,
                rejection_reason=cb_reason,
                checks_passed=checks_passed,
                checks_failed=checks_failed,
            )
        checks_passed.append("CIRCUIT_BREAKER")

        # For SELL/REDUCE actions, we're less restrictive (allow exiting)
        is_exit_trade = proposal.action in (TradeAction.SELL, TradeAction.REDUCE)

        if not is_exit_trade:
            # --- CHECK 3: Daily Loss Limit ---
            if portfolio.daily_pnl_pct <= self._daily_loss_limit_pct:
                checks_failed.append("DAILY_LOSS_LIMIT")
                return TradeResult(
                    approved=False,
                    proposal=proposal,
                    rejection_reason=(
                        f"Daily loss {portfolio.daily_pnl_pct:.2f}% exceeds "
                        f"limit {self._daily_loss_limit_pct:.2f}%. Trading halted for today."
                    ),
                    checks_passed=checks_passed,
                    checks_failed=checks_failed,
                )
            checks_passed.append("DAILY_LOSS_LIMIT")

            # --- CHECK 4: Daily Trade Count ---
            if portfolio.daily_trades >= self._max_trades_per_day:
                checks_failed.append("MAX_DAILY_TRADES")
                return TradeResult(
                    approved=False,
                    proposal=proposal,
                    rejection_reason=(
                        f"Max daily trades ({self._max_trades_per_day}) reached."
                    ),
                    checks_passed=checks_passed,
                    checks_failed=checks_failed,
                )
            checks_passed.append("MAX_DAILY_TRADES")

            # Check new positions limit
            if proposal.asset not in portfolio.positions:
                if portfolio.daily_new_positions >= self._max_new_positions_per_day:
                    checks_failed.append("MAX_NEW_POSITIONS")
                    return TradeResult(
                        approved=False,
                        proposal=proposal,
                        rejection_reason=(
                            f"Max new positions per day ({self._max_new_positions_per_day}) reached."
                        ),
                        checks_passed=checks_passed,
                        checks_failed=checks_failed,
                    )
            checks_passed.append("MAX_NEW_POSITIONS")

            # --- CHECK 5: Position Size ---
            position_pct = (proposal.notional_value / portfolio.total_value) * 100.0
            if position_pct > self._max_position_pct:
                checks_failed.append("MAX_POSITION_SIZE")
                return TradeResult(
                    approved=False,
                    proposal=proposal,
                    rejection_reason=(
                        f"Position size {position_pct:.1f}% exceeds "
                        f"max {self._max_position_pct:.1f}%."
                    ),
                    checks_passed=checks_passed,
                    checks_failed=checks_failed,
                )
            checks_passed.append("MAX_POSITION_SIZE")

            # --- CHECK 6: Asset Class Allocation ---
            current_class_value = sum(
                pos.market_value
                for pos in portfolio.positions.values()
                if pos.asset_class == proposal.asset_class
            )
            new_class_pct = (
                (current_class_value + proposal.notional_value) / portfolio.total_value
            ) * 100.0
            if new_class_pct > self._max_asset_class_pct:
                checks_failed.append("MAX_ASSET_CLASS")
                return TradeResult(
                    approved=False,
                    proposal=proposal,
                    rejection_reason=(
                        f"Asset class {proposal.asset_class.value} would reach "
                        f"{new_class_pct:.1f}%, exceeding max {self._max_asset_class_pct:.1f}%."
                    ),
                    checks_passed=checks_passed,
                    checks_failed=checks_failed,
                )
            checks_passed.append("MAX_ASSET_CLASS")

            # --- CHECK 7: Cash Reserve ---
            cash_after = portfolio.cash - proposal.notional_value
            cash_pct_after = (cash_after / portfolio.total_value) * 100.0
            if cash_pct_after < self._min_cash_reserve_pct:
                checks_failed.append("MIN_CASH_RESERVE")
                return TradeResult(
                    approved=False,
                    proposal=proposal,
                    rejection_reason=(
                        f"Cash would drop to {cash_pct_after:.1f}%, "
                        f"below minimum {self._min_cash_reserve_pct:.1f}%."
                    ),
                    checks_passed=checks_passed,
                    checks_failed=checks_failed,
                )
            checks_passed.append("MIN_CASH_RESERVE")

            # --- CHECK 8: Correlation ---
            existing_assets = list(portfolio.positions.keys())
            corr_ok, corr_multiplier, corr_reason = self.correlation_checker.check(
                proposal.asset, existing_assets
            )
            if not corr_ok:
                checks_failed.append("CORRELATION")
                return TradeResult(
                    approved=False,
                    proposal=proposal,
                    rejection_reason=corr_reason,
                    checks_passed=checks_passed,
                    checks_failed=checks_failed,
                )
            checks_passed.append("CORRELATION")

            # --- CHECK 9: Portfolio Heat vs Exposure Ceiling ---
            total_invested_pct = 100.0 - portfolio.cash_pct
            if total_invested_pct + position_pct > self._exposure_ceiling:
                checks_failed.append("EXPOSURE_CEILING")
                return TradeResult(
                    approved=False,
                    proposal=proposal,
                    rejection_reason=(
                        f"Total exposure would reach {total_invested_pct + position_pct:.1f}%, "
                        f"exceeding ceiling {self._exposure_ceiling:.1f}%."
                    ),
                    checks_passed=checks_passed,
                    checks_failed=checks_failed,
                )
            checks_passed.append("EXPOSURE_CEILING")

            # --- CHECK 10: Kelly Sizing ---
            cb_multiplier = self.circuit_breaker.get_size_multiplier()
            kelly_pct = self.position_sizer.estimate_from_score(
                composite_score=proposal.score,
                confidence=proposal.confidence,
                circuit_breaker_multiplier=cb_multiplier * corr_multiplier,
            )

            # Adjust quantity based on Kelly sizing
            if kelly_pct > 0 and portfolio.total_value > 0:
                kelly_notional = portfolio.total_value * (kelly_pct / 100.0)
                kelly_quantity = kelly_notional / proposal.price if proposal.price > 0 else 0
                adjusted_quantity = min(proposal.quantity, kelly_quantity)
            else:
                adjusted_quantity = proposal.quantity

            checks_passed.append("KELLY_SIZING")
        else:
            # Exit trades: allow with original quantity
            adjusted_quantity = proposal.quantity
            kelly_pct = None
            checks_passed.append("EXIT_TRADE_ALLOWED")

        # ALL CHECKS PASSED
        logger.info(
            f"APPROVED: {proposal.action.value} {proposal.asset} — "
            f"qty={adjusted_quantity:.4f}, checks={len(checks_passed)} passed"
        )

        return TradeResult(
            approved=True,
            proposal=proposal,
            adjusted_quantity=adjusted_quantity,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            kelly_size_pct=kelly_pct,
        )

    def record_trade_result(self, is_win: bool) -> None:
        """Record a completed trade result for circuit breaker tracking."""
        self.circuit_breaker.record_trade_result(is_win)

    def get_status(self) -> dict:
        """Return full risk guard status for reporting."""
        return {
            "exposure_ceiling": self._exposure_ceiling,
            "max_position_pct": self._max_position_pct,
            "max_asset_class_pct": self._max_asset_class_pct,
            "min_cash_reserve_pct": self._min_cash_reserve_pct,
            "daily_loss_limit_pct": self._daily_loss_limit_pct,
            "max_trades_per_day": self._max_trades_per_day,
            "kill_switch": self.kill_switch.get_status(),
            "circuit_breaker": self.circuit_breaker.get_status(),
            "position_sizer": self.position_sizer.get_status(),
            "correlation_checker": self.correlation_checker.get_status(),
        }
