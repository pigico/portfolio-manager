"""Comprehensive tests for the Risk Guard module.

Tests cover:
- Kill switch activation and lock file
- Circuit breaker pause thresholds
- Position sizing (Kelly criterion)
- Correlation checking
- Full RiskGuard validation pipeline
"""

from __future__ import annotations

import importlib
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

# Add the risk-guard scripts dir to sys.path so we can import directly
_scripts_dir = Path(__file__).parent.parent / "skills" / "risk-guard" / "scripts"
sys.path.insert(0, str(_scripts_dir))

from circuit_breaker import CircuitBreaker
from correlation_checker import CorrelationChecker
from kill_switch import KillSwitch
from models import (
    AssetClass,
    Confidence,
    PortfolioState,
    PositionInfo,
    TradeAction,
    TradeProposal,
)
from position_sizer import PositionSizer
from risk_guard import RiskGuard


# ============================================================
# Kill Switch Tests
# ============================================================

class TestKillSwitch:
    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.lock_file = Path(self.tmp_dir) / ".kill_switch_active"

    def teardown_method(self):
        if self.lock_file.exists():
            self.lock_file.unlink()

    def test_initial_state_not_active(self):
        ks = KillSwitch(lock_file_path=self.lock_file)
        assert not ks.is_active

    def test_check_ok_when_above_threshold(self):
        ks = KillSwitch(max_drawdown_pct=-40.0, lock_file_path=self.lock_file)
        assert ks.check(-10.0) is True
        assert ks.check(-39.9) is True
        assert not ks.is_active

    def test_triggers_at_threshold(self):
        ks = KillSwitch(max_drawdown_pct=-40.0, lock_file_path=self.lock_file)
        result = ks.check(-40.0)
        assert result is False
        assert ks.is_active
        assert self.lock_file.exists()

    def test_triggers_below_threshold(self):
        ks = KillSwitch(max_drawdown_pct=-40.0, lock_file_path=self.lock_file)
        result = ks.check(-50.0)
        assert result is False
        assert ks.is_active

    def test_stays_active_after_trigger(self):
        ks = KillSwitch(max_drawdown_pct=-40.0, lock_file_path=self.lock_file)
        ks.check(-45.0)
        # Even with good drawdown now, still active
        assert ks.check(-5.0) is False
        assert ks.is_active

    def test_lock_file_contains_info(self):
        ks = KillSwitch(max_drawdown_pct=-40.0, lock_file_path=self.lock_file)
        ks.check(-42.0)
        content = self.lock_file.read_text()
        assert "KILL SWITCH ACTIVATED" in content
        assert "-42.00%" in content

    def test_manual_reset_by_deleting_file(self):
        ks = KillSwitch(max_drawdown_pct=-40.0, lock_file_path=self.lock_file)
        ks.check(-45.0)
        assert ks.is_active
        # Simulate manual reset
        self.lock_file.unlink()
        assert not ks.is_active
        # Can trade again
        assert ks.check(-10.0) is True

    def test_detects_existing_lock_file(self):
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self.lock_file.write_text("PREVIOUSLY ACTIVATED")
        ks = KillSwitch(lock_file_path=self.lock_file)
        assert ks.is_active

    def test_get_status(self):
        ks = KillSwitch(max_drawdown_pct=-40.0, lock_file_path=self.lock_file)
        status = ks.get_status()
        assert status["is_active"] is False
        assert status["max_drawdown_pct"] == -40.0


# ============================================================
# Circuit Breaker Tests
# ============================================================

class TestCircuitBreaker:
    def test_initial_state(self):
        cb = CircuitBreaker()
        assert not cb.is_paused
        assert cb.consecutive_losses == 0
        assert not cb.should_half_size

    def test_no_pause_before_threshold(self):
        cb = CircuitBreaker(pause_1h_after=3)
        cb.record_trade_result(is_win=False)
        cb.record_trade_result(is_win=False)
        assert not cb.is_paused
        assert cb.consecutive_losses == 2

    def test_pause_after_3_losses(self):
        cb = CircuitBreaker(pause_1h_after=3)
        for _ in range(3):
            cb.record_trade_result(is_win=False)
        assert cb.is_paused
        allowed, reason = cb.check()
        assert not allowed
        assert "3 consecutive losses" in reason

    def test_pause_after_5_losses(self):
        cb = CircuitBreaker(pause_1h_after=3, pause_4h_after=5)
        for _ in range(5):
            cb.record_trade_result(is_win=False)
        assert cb.is_paused
        assert cb.pause_remaining_seconds > 3600  # More than 1 hour

    def test_half_size_after_pause(self):
        cb = CircuitBreaker(pause_1h_after=3, half_size_trades=10)
        for _ in range(3):
            cb.record_trade_result(is_win=False)
        assert cb.should_half_size
        assert cb.get_size_multiplier() == 0.5

    def test_win_resets_loss_counter(self):
        cb = CircuitBreaker(pause_1h_after=3)
        cb.record_trade_result(is_win=False)
        cb.record_trade_result(is_win=False)
        cb.record_trade_result(is_win=True)  # Reset
        assert cb.consecutive_losses == 0
        cb.record_trade_result(is_win=False)
        assert not cb.is_paused

    def test_consecutive_wins_full_reset(self):
        cb = CircuitBreaker(pause_1h_after=3, reset_after_wins=5, half_size_trades=10)
        # Trigger pause
        for _ in range(3):
            cb.record_trade_result(is_win=False)
        assert cb.should_half_size
        # Simulate pause expiry by resetting pause time
        cb._paused_until = datetime.now(tz=UTC) - timedelta(seconds=1)
        # Win 5 times
        for _ in range(5):
            cb.record_trade_result(is_win=True)
        assert not cb.should_half_size

    def test_pause_expires(self):
        cb = CircuitBreaker(pause_1h_after=3)
        for _ in range(3):
            cb.record_trade_result(is_win=False)
        # Manually expire the pause
        cb._paused_until = datetime.now(tz=UTC) - timedelta(seconds=1)
        assert not cb.is_paused
        allowed, _ = cb.check()
        assert allowed

    def test_manual_reset(self):
        cb = CircuitBreaker(pause_1h_after=3)
        for _ in range(3):
            cb.record_trade_result(is_win=False)
        cb.reset()
        assert not cb.is_paused
        assert cb.consecutive_losses == 0

    def test_get_status(self):
        cb = CircuitBreaker()
        status = cb.get_status()
        assert "is_paused" in status
        assert "consecutive_losses" in status
        assert "size_multiplier" in status


# ============================================================
# Position Sizer Tests
# ============================================================

class TestPositionSizer:
    def test_kelly_positive_edge(self):
        ps = PositionSizer()
        # 60% win rate, 2:1 risk/reward
        kelly = ps.calculate_kelly(win_probability=0.6, win_loss_ratio=2.0)
        assert kelly > 0
        # Kelly = (2*0.6 - 0.4) / 2 = (1.2 - 0.4) / 2 = 0.4
        assert abs(kelly - 0.4) < 0.001

    def test_kelly_no_edge(self):
        ps = PositionSizer()
        # 50% win rate, 1:1 — no edge
        kelly = ps.calculate_kelly(win_probability=0.5, win_loss_ratio=1.0)
        assert kelly == 0.0

    def test_kelly_negative_edge(self):
        ps = PositionSizer()
        # 30% win rate, 1:1 — negative edge
        kelly = ps.calculate_kelly(win_probability=0.3, win_loss_ratio=1.0)
        assert kelly < 0

    def test_fractional_kelly_reduces_size(self):
        ps = PositionSizer(default_fraction=0.25, max_position_pct=20.0)
        size = ps.calculate_position_size_pct(
            win_probability=0.6,
            win_loss_ratio=2.0,
            confidence=Confidence.MEDIUM,
        )
        # Full Kelly would be 40%, 1/4 Kelly = 10%
        assert size == 10.0

    def test_capped_at_max(self):
        ps = PositionSizer(max_position_pct=20.0)
        size = ps.calculate_position_size_pct(
            win_probability=0.9,
            win_loss_ratio=5.0,
            confidence=Confidence.HIGH,
        )
        assert size <= 20.0

    def test_low_confidence_smaller_size(self):
        ps = PositionSizer()
        size_low = ps.calculate_position_size_pct(
            win_probability=0.6, win_loss_ratio=2.0, confidence=Confidence.LOW,
        )
        size_high = ps.calculate_position_size_pct(
            win_probability=0.6, win_loss_ratio=2.0, confidence=Confidence.HIGH,
        )
        assert size_low < size_high

    def test_circuit_breaker_halves_size(self):
        ps = PositionSizer()
        full_size = ps.calculate_position_size_pct(
            win_probability=0.6, win_loss_ratio=2.0,
            confidence=Confidence.MEDIUM, circuit_breaker_multiplier=1.0,
        )
        half_size = ps.calculate_position_size_pct(
            win_probability=0.6, win_loss_ratio=2.0,
            confidence=Confidence.MEDIUM, circuit_breaker_multiplier=0.5,
        )
        assert abs(half_size - full_size / 2.0) < 0.01

    def test_estimate_from_score(self):
        ps = PositionSizer()
        # High score = bigger position
        size_high = ps.estimate_from_score(85, Confidence.HIGH)
        size_low = ps.estimate_from_score(40, Confidence.LOW)
        assert size_high > size_low
        assert size_high <= 20.0
        assert size_low >= 0.0

    def test_zero_score_returns_small_or_zero(self):
        ps = PositionSizer()
        size = ps.estimate_from_score(0, Confidence.LOW)
        # Should still be positive (we have a floor on win_prob)
        assert size >= 0.0


# ============================================================
# Correlation Checker Tests
# ============================================================

class TestCorrelationChecker:
    def test_no_existing_positions(self):
        cc = CorrelationChecker()
        ok, mult, reason = cc.check("AAPL", [])
        assert ok is True
        assert mult == 1.0

    def test_perfect_correlation_blocks(self):
        cc = CorrelationChecker(max_correlation=0.7)
        # Create perfectly correlated returns
        returns = [0.01, -0.02, 0.015, -0.01, 0.02] * 10
        cc.update_price_history("AAPL", returns)
        cc.update_price_history("AAPL_CLONE", returns)
        ok, mult, reason = cc.check("AAPL_CLONE", ["AAPL"])
        assert ok is False
        assert mult == 0.0

    def test_uncorrelated_passes(self):
        import random
        random.seed(42)
        cc = CorrelationChecker(max_correlation=0.7)
        returns_a = [random.gauss(0, 0.02) for _ in range(60)]
        returns_b = [random.gauss(0, 0.02) for _ in range(60)]
        cc.update_price_history("AAPL", returns_a)
        cc.update_price_history("GLD", returns_b)
        ok, mult, reason = cc.check("GLD", ["AAPL"])
        assert ok is True
        assert mult == 1.0

    def test_insufficient_data_passes(self):
        cc = CorrelationChecker()
        cc.update_price_history("AAPL", [0.01, 0.02])  # Too few
        ok, mult, reason = cc.check("MSFT", ["AAPL"])
        assert ok is True

    def test_get_correlation_matrix(self):
        import random
        random.seed(42)
        cc = CorrelationChecker()
        for asset in ["A", "B", "C"]:
            cc.update_price_history(asset, [random.gauss(0, 0.02) for _ in range(60)])
        matrix = cc.get_correlation_matrix(["A", "B", "C"])
        assert matrix["A"]["A"] == 1.0
        assert matrix["B"]["B"] == 1.0


# ============================================================
# Full RiskGuard Integration Tests
# ============================================================

class TestRiskGuard:
    def setup_method(self):
        RiskGuard.reset_singleton()
        self.tmp_dir = tempfile.mkdtemp()
        self.lock_file = Path(self.tmp_dir) / ".kill_switch_active"
        self.rg = RiskGuard(
            kill_switch_lock_file=self.lock_file,
            max_position_pct=20.0,
            max_asset_class_pct=60.0,
            min_cash_reserve_pct=5.0,
            daily_loss_limit_pct=-15.0,
            max_trades_per_day=20,
            max_new_positions_per_day=5,
        )

    def teardown_method(self):
        if self.lock_file.exists():
            self.lock_file.unlink()
        RiskGuard.reset_singleton()

    def _make_portfolio(self, **kwargs) -> PortfolioState:
        defaults = {
            "total_value": 100000.0,
            "cash": 50000.0,
            "positions": {},
            "peak_value": 100000.0,
            "daily_start_value": 100000.0,
            "daily_trades": 0,
            "daily_new_positions": 0,
        }
        defaults.update(kwargs)
        return PortfolioState(**defaults)

    def _make_proposal(self, **kwargs) -> TradeProposal:
        defaults = {
            "asset": "AAPL",
            "asset_class": AssetClass.STOCKS,
            "action": TradeAction.BUY,
            "price": 150.0,
            "quantity": 10,
            "score": 75.0,
            "confidence": Confidence.MEDIUM,
            "rationale": "Test trade",
        }
        defaults.update(kwargs)
        return TradeProposal(**defaults)

    def test_approve_valid_trade(self):
        portfolio = self._make_portfolio()
        proposal = self._make_proposal(price=100.0, quantity=10)  # $1000 = 1%
        result = self.rg.validate_trade(proposal, portfolio)
        assert result.approved is True
        assert len(result.checks_failed) == 0

    def test_reject_when_kill_switch_active(self):
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self.lock_file.write_text("ACTIVE")
        portfolio = self._make_portfolio()
        proposal = self._make_proposal()
        result = self.rg.validate_trade(proposal, portfolio)
        assert result.approved is False
        assert "KILL_SWITCH" in result.checks_failed

    def test_reject_when_circuit_breaker_paused(self):
        # Trigger circuit breaker
        for _ in range(3):
            self.rg.record_trade_result(is_win=False)
        portfolio = self._make_portfolio()
        proposal = self._make_proposal()
        result = self.rg.validate_trade(proposal, portfolio)
        assert result.approved is False
        assert "CIRCUIT_BREAKER" in result.checks_failed

    def test_reject_exceeds_daily_loss_limit(self):
        portfolio = self._make_portfolio(
            total_value=80000.0,
            daily_start_value=100000.0,  # -20% daily loss
        )
        proposal = self._make_proposal()
        result = self.rg.validate_trade(proposal, portfolio)
        assert result.approved is False
        assert "DAILY_LOSS_LIMIT" in result.checks_failed

    def test_reject_max_daily_trades(self):
        portfolio = self._make_portfolio(daily_trades=20)
        proposal = self._make_proposal()
        result = self.rg.validate_trade(proposal, portfolio)
        assert result.approved is False
        assert "MAX_DAILY_TRADES" in result.checks_failed

    def test_reject_position_too_large(self):
        portfolio = self._make_portfolio(total_value=100000.0, cash=50000.0)
        # $25,000 = 25% > 20% max
        proposal = self._make_proposal(price=250.0, quantity=100)
        result = self.rg.validate_trade(proposal, portfolio)
        assert result.approved is False
        assert "MAX_POSITION_SIZE" in result.checks_failed

    def test_reject_asset_class_limit(self):
        # Already have 55% in stocks
        positions = {
            "MSFT": PositionInfo("MSFT", AssetClass.STOCKS, 100, 550.0, 550.0, 550.0),
        }
        portfolio = self._make_portfolio(
            total_value=100000.0,
            cash=45000.0,
            positions=positions,
        )
        # Adding 10% more stocks would be 65% > 60%
        proposal = self._make_proposal(price=100.0, quantity=100)  # $10,000 = 10%
        result = self.rg.validate_trade(proposal, portfolio)
        assert result.approved is False
        assert "MAX_ASSET_CLASS" in result.checks_failed

    def test_reject_insufficient_cash_reserve(self):
        portfolio = self._make_portfolio(
            total_value=100000.0,
            cash=6000.0,  # 6% cash
        )
        # Buying $2000 would leave 4% < 5% min
        proposal = self._make_proposal(price=200.0, quantity=10)
        result = self.rg.validate_trade(proposal, portfolio)
        assert result.approved is False
        assert "MIN_CASH_RESERVE" in result.checks_failed

    def test_reject_exceeds_exposure_ceiling(self):
        self.rg.set_exposure_ceiling(30.0)  # Only 30% allowed
        positions = {
            "MSFT": PositionInfo("MSFT", AssetClass.STOCKS, 50, 500.0, 500.0, 500.0),
        }
        portfolio = self._make_portfolio(
            total_value=100000.0,
            cash=75000.0,
            positions=positions,
        )
        # Already 25% invested, adding 10% = 35% > 30% ceiling
        proposal = self._make_proposal(price=100.0, quantity=100)
        result = self.rg.validate_trade(proposal, portfolio)
        assert result.approved is False
        assert "EXPOSURE_CEILING" in result.checks_failed

    def test_sell_trades_bypass_most_checks(self):
        """SELL/REDUCE trades should be allowed even in restricted conditions."""
        portfolio = self._make_portfolio(daily_trades=20)
        proposal = self._make_proposal(action=TradeAction.SELL)
        result = self.rg.validate_trade(proposal, portfolio)
        # SELL bypasses daily trade limit, position size, etc.
        assert result.approved is True

    def test_sell_still_blocked_by_kill_switch(self):
        """Kill switch blocks EVERYTHING, even exits."""
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self.lock_file.write_text("ACTIVE")
        portfolio = self._make_portfolio()
        proposal = self._make_proposal(action=TradeAction.SELL)
        result = self.rg.validate_trade(proposal, portfolio)
        assert result.approved is False

    def test_kelly_adjusts_quantity(self):
        portfolio = self._make_portfolio(total_value=100000.0, cash=80000.0)
        # Propose a large trade — Kelly should cap it
        proposal = self._make_proposal(
            price=100.0, quantity=200, score=70.0,  # $20,000 requested
            confidence=Confidence.LOW,
        )
        result = self.rg.validate_trade(proposal, portfolio)
        assert result.approved is True
        # Kelly with LOW confidence should give less than requested
        assert result.final_quantity <= 200

    def test_max_new_positions_per_day(self):
        portfolio = self._make_portfolio(daily_new_positions=5)
        proposal = self._make_proposal(asset="NEW_TICKER")  # Not in positions
        result = self.rg.validate_trade(proposal, portfolio)
        assert result.approved is False
        assert "MAX_NEW_POSITIONS" in result.checks_failed

    def test_get_status(self):
        status = self.rg.get_status()
        assert "kill_switch" in status
        assert "circuit_breaker" in status
        assert "position_sizer" in status
        assert "exposure_ceiling" in status


# ============================================================
# Model Tests
# ============================================================

class TestModels:
    def test_portfolio_drawdown(self):
        ps = PortfolioState(
            total_value=80000.0,
            cash=20000.0,
            peak_value=100000.0,
            daily_start_value=90000.0,
        )
        assert ps.drawdown_pct == pytest.approx(-20.0)
        assert ps.daily_pnl_pct == pytest.approx(-11.11, abs=0.01)
        assert ps.cash_pct == pytest.approx(25.0)

    def test_position_info(self):
        pos = PositionInfo(
            asset="BTC",
            asset_class=AssetClass.CRYPTO,
            quantity=1.0,
            entry_price=50000.0,
            current_price=60000.0,
            peak_price=65000.0,
        )
        assert pos.market_value == 60000.0
        assert pos.pnl_pct == pytest.approx(20.0)
        assert pos.drawdown_from_peak_pct == pytest.approx(-7.69, abs=0.01)

    def test_trade_proposal_notional(self):
        tp = TradeProposal(
            asset="AAPL",
            asset_class=AssetClass.STOCKS,
            action=TradeAction.BUY,
            price=150.0,
            quantity=10,
            score=75.0,
            confidence=Confidence.MEDIUM,
            rationale="Test",
        )
        assert tp.notional_value == 1500.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
