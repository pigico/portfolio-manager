"""Tests for Sprint 3 — Composite Scorer, AI Reasoning, Optimizer, Paper Trader."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ── Composite Scorer ─────────────────────────────────────
_cs_path = Path(__file__).parent.parent / "skills" / "composite-scorer" / "scripts"
sys.path.insert(0, str(_cs_path))

from scorer import CompositeScorer, AssetType, Decision
from score_history import ScoreHistory
from screener import Screener

# ── AI Reasoning ─────────────────────────────────────────
_ai_path = Path(__file__).parent.parent / "skills" / "ai-reasoning" / "scripts"
sys.path.insert(0, str(_ai_path))

from override_manager import OverrideManager

# ── Portfolio Optimizer ──────────────────────────────────
_po_path = Path(__file__).parent.parent / "skills" / "portfolio-optimizer" / "scripts"
sys.path.insert(0, str(_po_path))

from optimizer import PortfolioOptimizer, OptMethod
from rebalancer import Rebalancer

# ── Paper Trader ─────────────────────────────────────────
_pt_path = Path(__file__).parent.parent / "skills" / "paper-trader" / "scripts"
sys.path.insert(0, str(_pt_path))

from paper_engine import PaperEngine
from trade_log import TradeLog
from benchmark_tracker import BenchmarkTracker

# Add risk-guard models
_rg_path = Path(__file__).parent.parent / "skills" / "risk-guard" / "scripts"
sys.path.insert(0, str(_rg_path))
from models import AssetClass


# ==============================================================
# Composite Scorer
# ==============================================================

class TestCompositeScorer:
    def test_strong_buy(self):
        cs = CompositeScorer()
        result = cs.score(
            "AAPL", AssetType.STOCKS,
            fundamental_score=90, technical_score=85,
            macro_score=80, sentiment_score=75,
        )
        assert result.decision == Decision.STRONG_BUY
        assert result.total >= 80

    def test_sell_signal(self):
        cs = CompositeScorer()
        result = cs.score(
            "BAD_STOCK", AssetType.STOCKS,
            fundamental_score=15, technical_score=20,
            macro_score=25, sentiment_score=10,
        )
        assert result.decision in (Decision.SELL, Decision.REDUCE)
        assert result.total < 35

    def test_crypto_weights_differ(self):
        cs = CompositeScorer()
        stock = cs.score("AAPL", AssetType.STOCKS,
                         fundamental_score=80, technical_score=50,
                         macro_score=50, sentiment_score=50)
        crypto = cs.score("BTC", AssetType.CRYPTO,
                          fundamental_score=80, technical_score=50,
                          macro_score=50, sentiment_score=50)
        # Stocks weight fundamentals 35% vs crypto 25%, so stock score should be higher
        assert stock.total > crypto.total

    def test_momentum_bonus(self):
        cs = CompositeScorer()
        no_bonus = cs.score("X", AssetType.STOCKS,
                            fundamental_score=60, technical_score=60,
                            macro_score=60, sentiment_score=60)
        with_bonus = cs.score("X", AssetType.STOCKS,
                              fundamental_score=60, technical_score=60,
                              macro_score=60, sentiment_score=60,
                              score_rising_periods=4)
        assert with_bonus.total == no_bonus.total + 5

    def test_contrarian_bonus(self):
        cs = CompositeScorer()
        result = cs.score("X", AssetType.STOCKS,
                          fundamental_score=70, technical_score=50,
                          macro_score=50, sentiment_score=50,
                          fear_greed_extreme_fear=True)
        assert "contrarian" in result.bonuses

    def test_divergence_bonus(self):
        cs = CompositeScorer()
        result = cs.score("X", AssetType.STOCKS,
                          fundamental_score=60, technical_score=60,
                          macro_score=60, sentiment_score=60,
                          divergence_confirmed=True)
        assert "divergence" in result.bonuses

    def test_ai_override_applied(self):
        cs = CompositeScorer()
        result = cs.score("X", AssetType.STOCKS,
                          fundamental_score=50, technical_score=50,
                          macro_score=50, sentiment_score=50,
                          ai_override_points=15,
                          ai_override_rationale="Earnings beat")
        assert result.ai_override_applied
        assert result.total == pytest.approx(65.0)

    def test_ai_override_clamped(self):
        cs = CompositeScorer()
        result = cs.score("X", AssetType.STOCKS,
                          fundamental_score=50, technical_score=50,
                          macro_score=50, sentiment_score=50,
                          ai_override_points=50)  # Should be clamped to 20
        assert result.total <= 70  # 50 base + 20 max override

    def test_score_bounded_0_100(self):
        cs = CompositeScorer()
        result = cs.score("X", AssetType.STOCKS,
                          fundamental_score=100, technical_score=100,
                          macro_score=100, sentiment_score=100,
                          ai_override_points=20,
                          score_rising_periods=5,
                          divergence_confirmed=True,
                          fear_greed_extreme_fear=True)
        assert result.total <= 100


class TestScoreHistory:
    def test_record_and_retrieve(self):
        sh = ScoreHistory()
        sh.record("AAPL", 75, "BUY")
        sh.record("AAPL", 78, "BUY")
        assert len(sh.get_history("AAPL")) == 2

    def test_consecutive_rising(self):
        sh = ScoreHistory()
        for s in [60, 65, 70, 75, 80]:
            sh.record("AAPL", s, "BUY")
        assert sh.consecutive_rising_periods("AAPL") == 4

    def test_no_history(self):
        sh = ScoreHistory()
        assert sh.consecutive_rising_periods("MISSING") == 0

    def test_score_change_detection(self):
        sh = ScoreHistory()
        sh.record("AAPL", 60, "HOLD")
        sh.record("AAPL", 80, "STRONG_BUY")
        changed, delta = sh.score_changed_significantly("AAPL", threshold=10)
        assert changed
        assert delta == 20


class TestScreener:
    def test_pre_screen_pass(self):
        s = Screener()
        passed, catalyst = s.pre_screen("AAPL", price=180, sma200=160, rsi=55)
        assert passed

    def test_pre_screen_fail_below_sma(self):
        s = Screener()
        passed, reason = s.pre_screen("BAD", price=50, sma200=100, rsi=55)
        assert not passed

    def test_pre_screen_fail_overbought(self):
        s = Screener()
        passed, reason = s.pre_screen("HOT", price=200, sma200=180, rsi=90)
        assert not passed

    def test_rank_candidates(self):
        s = Screener(top_n=3, min_score=60)
        candidates = [
            {"asset": "A", "composite_score": 90, "decision": "STRONG_BUY", "catalyst": "test"},
            {"asset": "B", "composite_score": 75, "decision": "BUY", "catalyst": "test"},
            {"asset": "C", "composite_score": 50, "decision": "HOLD", "catalyst": "test"},
            {"asset": "D", "composite_score": 85, "decision": "STRONG_BUY", "catalyst": "test"},
        ]
        ranked = s.rank_candidates(candidates)
        assert len(ranked) == 3  # C excluded (below 60)
        assert ranked[0].asset == "A"  # Highest score first


# ==============================================================
# AI Override Manager
# ==============================================================

class TestOverrideManager:
    def test_apply_override(self):
        om = OverrideManager()
        final, applied = om.apply_override("AAPL", 60, 15, "Earnings beat")
        assert applied
        assert final == 75

    def test_override_clamped(self):
        om = OverrideManager(max_override=20)
        final, applied = om.apply_override("AAPL", 50, 30, "test")
        assert final == 70  # 50 + 20 (clamped)

    def test_zero_override_not_applied(self):
        om = OverrideManager()
        final, applied = om.apply_override("AAPL", 60, 0, "no change")
        assert not applied
        assert final == 60

    def test_auto_disable_after_bad_overrides(self):
        om = OverrideManager(bad_override_threshold=3, disable_days=7)
        # Apply 3 overrides
        for i in range(3):
            om.apply_override(f"T{i}", 50, 10, "test")
        # Mark all as bad
        for i in range(3):
            om.record_outcome(f"T{i}", 45)  # Actual went down, override was wrong
        assert not om.is_enabled

    def test_good_overrides_stay_enabled(self):
        om = OverrideManager(bad_override_threshold=3)
        for i in range(5):
            om.apply_override(f"T{i}", 50, 10, "test")
            om.record_outcome(f"T{i}", 65)  # Actual matched override direction
        assert om.is_enabled

    def test_get_status(self):
        om = OverrideManager()
        status = om.get_status()
        assert status["enabled"] is True
        assert status["total_overrides"] == 0


# ==============================================================
# Portfolio Optimizer
# ==============================================================

class TestOptimizer:
    def test_equal_weight(self):
        po = PortfolioOptimizer()
        weights = po.optimize(
            {"A": 0.1, "B": 0.1, "C": 0.1, "D": 0.1},
            method=OptMethod.EQUAL_WEIGHT,
        )
        assert len(weights) == 4
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_empty_returns(self):
        po = PortfolioOptimizer()
        weights = po.optimize({}, method=OptMethod.EQUAL_WEIGHT)
        assert weights == {}

    def test_score_weighted_fallback(self):
        po = PortfolioOptimizer()
        weights = po.optimize(
            {"A": 0.15, "B": 0.10, "C": 0.05},
            method=OptMethod.MEAN_VARIANCE,  # Will fallback without pypfopt
        )
        assert len(weights) == 3
        assert sum(weights.values()) == pytest.approx(1.0, abs=0.01)


class TestRebalancer:
    def test_drift_trigger(self):
        rb = Rebalancer(drift_threshold_pct=5)
        actions = rb.check_drift(
            current_weights={"AAPL": 30, "BTC": 20},
            target_weights={"AAPL": 20, "BTC": 25},
        )
        assert len(actions) >= 1
        assert any(a.trigger == "DRIFT" for a in actions)

    def test_no_drift(self):
        rb = Rebalancer(drift_threshold_pct=5)
        actions = rb.check_drift(
            current_weights={"AAPL": 20, "BTC": 25},
            target_weights={"AAPL": 22, "BTC": 24},
        )
        assert len(actions) == 0

    def test_score_sell_trigger(self):
        rb = Rebalancer()
        actions = rb.check_score_triggers(
            scores={"AAPL": 25, "BTC": 85},
            current_positions={"AAPL"},
        )
        sell_actions = [a for a in actions if a.action == "SELL"]
        buy_actions = [a for a in actions if a.action == "BUY"]
        assert len(sell_actions) == 1  # AAPL < 30
        assert len(buy_actions) == 1  # BTC > 80 and not in positions

    def test_risk_trigger(self):
        rb = Rebalancer()
        actions = rb.check_risk_triggers(
            portfolio_drawdown_pct=-12,
            position_losses={"BAD_STOCK": -18},
        )
        assert len(actions) >= 2  # portfolio + position

    def test_regime_change_trigger(self):
        rb = Rebalancer()
        actions = rb.check_regime_change(
            previous_regime="Goldilocks",
            current_regime="Stagflation",
            new_weights={"stocks": 10, "commodities": 25},
            current_weights={"stocks": 45, "commodities": 15},
        )
        assert len(actions) >= 2


# ==============================================================
# Paper Trader
# ==============================================================

class TestPaperEngine:
    def test_initial_state(self):
        pe = PaperEngine(initial_capital=100000)
        assert pe.total_value == 100000
        assert pe.cash == 100000
        assert len(pe.positions) == 0

    def test_buy_reduces_cash(self):
        pe = PaperEngine(initial_capital=100000)
        pe.execute_buy("AAPL", AssetClass.STOCKS, price=150, quantity=10)
        assert pe.cash < 100000
        assert "AAPL" in pe.positions
        assert pe.positions["AAPL"].quantity == 10

    def test_sell_increases_cash(self):
        pe = PaperEngine(initial_capital=100000)
        pe.execute_buy("AAPL", AssetClass.STOCKS, price=150, quantity=10)
        cash_after_buy = pe.cash
        pe.execute_sell("AAPL")
        assert pe.cash > cash_after_buy
        assert "AAPL" not in pe.positions

    def test_commission_applied(self):
        pe = PaperEngine(initial_capital=100000, commission_pct=0.001)
        pe.execute_buy("AAPL", AssetClass.STOCKS, price=100, quantity=100)
        # Cost ≈ 100 * 100 * 1.0005 (slippage) + commission
        # Cash should be less than 100000 - 10000
        assert pe.cash < 90000

    def test_insufficient_cash(self):
        pe = PaperEngine(initial_capital=1000)
        trade = pe.execute_buy("AAPL", AssetClass.STOCKS, price=150, quantity=100)
        # Should auto-adjust quantity
        assert pe.positions.get("AAPL") is not None or trade.quantity == 0

    def test_sell_nonexistent_position(self):
        pe = PaperEngine()
        trade = pe.execute_sell("MISSING")
        assert trade.risk_guard_result == "rejected: no position"

    def test_update_prices(self):
        pe = PaperEngine(initial_capital=100000)
        pe.execute_buy("BTC", AssetClass.CRYPTO, price=50000, quantity=1)
        initial_value = pe.total_value
        pe.update_prices({"BTC": 55000})
        assert pe.total_value > initial_value

    def test_close_all_positions(self):
        pe = PaperEngine(initial_capital=100000)
        pe.execute_buy("AAPL", AssetClass.STOCKS, price=150, quantity=10)
        pe.execute_buy("BTC", AssetClass.CRYPTO, price=50000, quantity=0.5)
        trades = pe.close_all_positions()
        assert len(pe.positions) == 0
        assert len(trades) == 2

    def test_performance_metrics(self):
        pe = PaperEngine(initial_capital=100000)
        pe.execute_buy("AAPL", AssetClass.STOCKS, price=150, quantity=10)
        metrics = pe.get_performance_metrics()
        assert "total_value" in metrics
        assert "total_trades" in metrics
        assert metrics["total_trades"] == 1

    def test_daily_counter_reset(self):
        pe = PaperEngine()
        pe.execute_buy("AAPL", AssetClass.STOCKS, price=100, quantity=5)
        assert pe.daily_trades == 1
        pe.reset_daily_counters()
        assert pe.daily_trades == 0

    def test_partial_sell(self):
        pe = PaperEngine(initial_capital=100000)
        pe.execute_buy("AAPL", AssetClass.STOCKS, price=150, quantity=20)
        pe.execute_sell("AAPL", quantity=10)
        assert pe.positions["AAPL"].quantity == 10


class TestTradeLog:
    def test_log_and_retrieve(self, tmp_path):
        tl = TradeLog(log_dir=tmp_path)
        tl.log_trade(1, "AAPL", "BUY", 150, 10, 0.15, 75, False, "test", "approved", 100000)
        entries = tl.get_entries()
        assert len(entries) == 1
        assert entries[0]["asset"] == "AAPL"

    def test_export_csv(self, tmp_path):
        tl = TradeLog(log_dir=tmp_path)
        tl.log_trade(1, "BTC", "BUY", 50000, 1, 50, 80, True, "test", "approved", 100000)
        path = tl.export_csv()
        assert path.exists()


class TestBenchmarkTracker:
    def test_initial_state(self):
        bt = BenchmarkTracker(initial_capital=100000)
        returns = bt.get_total_returns()
        assert returns["portfolio"] == 0.0

    def test_record_and_compare(self):
        bt = BenchmarkTracker(initial_capital=100000)
        bt.set_initial_prices({"SPY": 450, "BTC": 50000, "GLD": 180})
        bt.record_snapshot(100000, {"SPY": 450, "BTC": 50000, "GLD": 180})
        bt.record_snapshot(110000, {"SPY": 460, "BTC": 52000, "GLD": 185})
        returns = bt.get_total_returns()
        assert returns["portfolio"] == pytest.approx(10.0)
        assert returns["SPY"] > 0

    def test_comparison_dict(self):
        bt = BenchmarkTracker()
        comp = bt.get_comparison()
        assert "total_returns_pct" in comp
        assert "outperformance_vs_spy" in comp


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
