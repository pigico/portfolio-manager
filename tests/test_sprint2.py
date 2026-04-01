"""Tests for Sprint 2 modules — Market Posture, Regime, Technical, Fundamentals."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

# ── Market Posture ───────────────────────────────────────
_mp_path = Path(__file__).parent.parent / "skills" / "market-posture" / "scripts"
sys.path.insert(0, str(_mp_path))

from posture_analyzer import PostureAnalyzer, Posture
from bubble_detector import BubbleDetector
from breadth_analyzer import BreadthAnalyzer

# ── Macro Regime ─────────────────────────────────────────
_mr_path = Path(__file__).parent.parent / "skills" / "macro-regime-detector" / "scripts"
sys.path.insert(0, str(_mr_path))

from regime_detector import RegimeDetector
from macro_signals import MacroSignals

# ── Technical Analyzer ───────────────────────────────────
_ta_path = Path(__file__).parent.parent / "skills" / "technical-analyzer" / "scripts"
sys.path.insert(0, str(_ta_path))

from indicators import TechnicalIndicators, Signal
from confluence import ConfluenceScorer

# ── Fundamental Analyzer ─────────────────────────────────
_fa_path = Path(__file__).parent.parent / "skills" / "fundamental-analyzer" / "scripts"
sys.path.insert(0, str(_fa_path))

from stock_fundamentals import StockFundamentals
from crypto_fundamentals import CryptoFundamentals
from commodity_fundamentals import CommodityFundamentals

# ── Divergence Detector ──────────────────────────────────
_dd_path = Path(__file__).parent.parent / "skills" / "data-collectors" / "scripts"
sys.path.insert(0, str(_dd_path))

from divergence_detector import DivergenceDetector


# ==============================================================
# Market Posture
# ==============================================================

class TestPostureAnalyzer:
    def test_favorable_conditions(self):
        pa = PostureAnalyzer()
        result = pa.analyze(
            regime="Goldilocks", regime_confidence=0.8,
            pct_above_sma200=75, advance_decline_ratio=1.8,
            bubble_score=3, vix=14, fear_greed_value=40,
            pct_rsi_above_50=65,
        )
        assert result.posture == Posture.NEW_ENTRY_ALLOWED
        assert result.exposure_ceiling >= 75

    def test_crisis_conditions(self):
        pa = PostureAnalyzer()
        result = pa.analyze(
            regime="Stagflation", regime_confidence=0.9,
            pct_above_sma200=20, advance_decline_ratio=0.4,
            bubble_score=12, vix=45, fear_greed_value=95,
            pct_rsi_above_50=15,
        )
        assert result.posture in (Posture.CASH_PRIORITY, Posture.REDUCE_ONLY)
        assert result.exposure_ceiling < 50

    def test_output_has_allocation(self):
        pa = PostureAnalyzer()
        result = pa.analyze()
        assert "stocks" in result.recommended_allocation
        assert "cash" in result.recommended_allocation
        total = sum(result.recommended_allocation.values())
        assert abs(total - 100) < 5  # Should sum to ~100

    def test_exposure_ceiling_bounded(self):
        pa = PostureAnalyzer()
        result = pa.analyze(vix=100, bubble_score=15, pct_above_sma200=0)
        assert 0 <= result.exposure_ceiling <= 100


class TestBubbleDetector:
    def test_normal_market(self):
        bd = BubbleDetector()
        result = bd.analyze(
            shiller_cape=18, margin_debt_yoy_change_pct=3,
            put_call_ratio=0.9, vix=20, ipo_first_day_avg_return_pct=8,
        )
        assert result.classification == "Normal"
        assert result.total_score <= 4

    def test_euphoria_market(self):
        bd = BubbleDetector()
        result = bd.analyze(
            shiller_cape=40, margin_debt_yoy_change_pct=35,
            put_call_ratio=0.4, vix=10, ipo_first_day_avg_return_pct=60,
        )
        assert result.total_score >= 10
        assert result.classification in ("Euphoria", "Critical")

    def test_score_bounded(self):
        bd = BubbleDetector()
        result = bd.analyze(shiller_cape=100, margin_debt_yoy_change_pct=100,
                            put_call_ratio=0.1, vix=8, ipo_first_day_avg_return_pct=100)
        assert result.total_score <= 15


class TestBreadthAnalyzer:
    def test_strong_breadth(self):
        ba = BreadthAnalyzer()
        result = ba.analyze(pct_above_sma50=80, pct_above_sma200=85,
                            advancing_issues=400, declining_issues=100)
        assert result.classification in ("Strong", "Healthy")
        assert result.health_score >= 70

    def test_weak_breadth(self):
        ba = BreadthAnalyzer()
        result = ba.analyze(pct_above_sma50=15, pct_above_sma200=20,
                            advancing_issues=80, declining_issues=420)
        assert result.health_score < 40


# ==============================================================
# Macro Regime Detector
# ==============================================================

class TestRegimeDetector:
    def _make_obs(self, values):
        """Build observations newest-first (like FRED API returns)."""
        return [{"date": f"2024-{i:02d}-01", "value": v} for i, v in enumerate(values, 1)]

    def test_goldilocks(self):
        rd = RegimeDetector()
        # Newest first: GDP rising → recent values higher, CPI falling → recent values lower
        gdp = self._make_obs([112, 110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100])
        cpi = self._make_obs([289, 290, 291, 292, 293, 294, 295, 296, 297, 298, 299, 300])
        result = rd.detect(gdp_observations=gdp, cpi_observations=cpi)
        assert result.regime == "Goldilocks"

    def test_stagflation(self):
        rd = RegimeDetector()
        # GDP falling (recent lower), CPI rising (recent higher)
        gdp = self._make_obs([98, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110])
        cpi = self._make_obs([300, 299, 298, 297, 296, 295, 294, 293, 292, 291, 290, 289])
        result = rd.detect(gdp_observations=gdp, cpi_observations=cpi)
        assert result.regime == "Stagflation"

    def test_has_recommended_weights(self):
        rd = RegimeDetector()
        result = rd.detect()
        assert "stocks" in result.recommended_weights

    def test_transition_detection(self):
        rd = RegimeDetector()
        gdp_up = self._make_obs([112, 110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100])
        cpi_down = self._make_obs([289, 290, 291, 292, 293, 294, 295, 296, 297, 298, 299, 300])
        rd.detect(gdp_observations=gdp_up, cpi_observations=cpi_down)
        # Now switch to stagflation
        gdp_down = self._make_obs([98, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110])
        cpi_up = self._make_obs([300, 299, 298, 297, 296, 295, 294, 293, 292, 291, 290, 289])
        result = rd.detect(gdp_observations=gdp_down, cpi_observations=cpi_up)
        assert result.previous_regime == "Goldilocks"


class TestMacroSignals:
    def test_yield_curve_inversion(self):
        ms = MacroSignals()
        alerts = ms.check_all(yield_spread_10y2y=-0.3)
        assert any(a.signal == "YIELD_CURVE_INVERTED" for a in alerts)

    def test_vix_spike(self):
        ms = MacroSignals()
        alerts = ms.check_all(vix=42)
        assert any(a.severity == "CRITICAL" for a in alerts)

    def test_no_alerts_in_calm(self):
        ms = MacroSignals()
        alerts = ms.check_all(yield_spread_10y2y=1.5, vix=15,
                              junk_bond_spread_bps=300, buffett_indicator=120)
        assert len(alerts) == 0


# ==============================================================
# Technical Analyzer
# ==============================================================

class TestTechnicalIndicators:
    def _make_prices(self, n=250, base=100, trend=0.001):
        np.random.seed(42)
        returns = np.random.normal(trend, 0.02, n)
        prices = base * np.cumprod(1 + returns)
        return prices.tolist()

    def test_rsi_calculation(self):
        ti = TechnicalIndicators()
        prices = self._make_prices()
        result = ti.rsi(np.array(prices))
        assert 0 <= result.value <= 100

    def test_compute_all(self):
        ti = TechnicalIndicators()
        prices = self._make_prices()
        results = ti.compute_all(prices, prices, prices)
        assert len(results) >= 5
        names = {r.name for r in results}
        assert "RSI" in names
        assert "MACD" in names

    def test_oversold_rsi(self):
        ti = TechnicalIndicators()
        # Create downtrending prices
        prices = [100 - i * 2 for i in range(30)]
        result = ti.rsi(np.array(prices))
        assert result.signal == Signal.BULLISH  # Oversold = buy signal


class TestConfluence:
    def test_all_bullish(self):
        from indicators import IndicatorResult
        cs = ConfluenceScorer()
        indicators = [
            IndicatorResult("RSI", 25, Signal.BULLISH),
            IndicatorResult("MACD", 0.5, Signal.BULLISH),
            IndicatorResult("BB", 0.1, Signal.BULLISH),
            IndicatorResult("EMA_CROSS", 1, Signal.BULLISH),
        ]
        score = cs.score(indicators)
        assert score.total > 70
        assert score.confluence_level in ("Strong", "High-Confidence")

    def test_mixed_signals(self):
        from indicators import IndicatorResult
        cs = ConfluenceScorer()
        indicators = [
            IndicatorResult("RSI", 50, Signal.NEUTRAL),
            IndicatorResult("MACD", 0.1, Signal.BULLISH),
            IndicatorResult("BB", 0.9, Signal.BEARISH),
        ]
        score = cs.score(indicators)
        assert 30 < score.total < 70

    def test_triple_bonus(self):
        from indicators import IndicatorResult
        cs = ConfluenceScorer()
        indicators = [
            IndicatorResult("RSI", 25, Signal.BULLISH),
            IndicatorResult("MACD", 0.5, Signal.BULLISH),
            IndicatorResult("BB", 0.1, Signal.BULLISH),
        ]
        score = cs.score(indicators)
        assert score.confluence_level == "High-Confidence"

    def test_empty_indicators(self):
        cs = ConfluenceScorer()
        score = cs.score([])
        assert score.total == 50.0


# ==============================================================
# Fundamental Analyzers
# ==============================================================

class TestStockFundamentals:
    def test_value_stock(self):
        sf = StockFundamentals()
        result = sf.analyze({
            "pe_ratio": 10, "pb_ratio": 1.2, "ps_ratio": 1.5,
            "ev_ebitda": 7, "roe": 0.18, "roic": 0.15,
            "fcf_yield": 0.07, "debt_to_equity": 0.3,
            "dividend_yield": 0.03, "payout_ratio": 0.40,
        })
        assert result.total > 65
        assert result.economic_moat in ("Wide", "Narrow")

    def test_overvalued_stock(self):
        sf = StockFundamentals()
        result = sf.analyze({
            "pe_ratio": 80, "pb_ratio": 12, "ps_ratio": 20,
            "ev_ebitda": 50, "roe": 0.03, "roic": 0.02,
            "fcf_yield": 0.005, "debt_to_equity": 3.0,
        })
        assert result.total < 40

    def test_handles_missing_data(self):
        sf = StockFundamentals()
        result = sf.analyze({})
        assert 0 <= result.total <= 100


class TestCryptoFundamentals:
    def test_strong_crypto(self):
        cf = CryptoFundamentals()
        result = cf.analyze({
            "market_cap": 500e9, "total_volume": 20e9,
            "circulating_supply": 19e6, "max_supply": 21e6,
            "price": 50000, "ath": 69000,
            "price_change_7d": 5, "price_change_30d": 15,
        })
        assert result.total > 50

    def test_handles_missing(self):
        cf = CryptoFundamentals()
        result = cf.analyze({})
        assert 0 <= result.total <= 100


class TestCommodityFundamentals:
    def test_bullish_commodity(self):
        cf = CommodityFundamentals()
        result = cf.analyze(
            spot_price=100, futures_price=97,  # Backwardation
            price_vs_200sma_pct=5, usd_index_change_pct=-2,
            inventory_trend="drawing",
        )
        assert result.total > 60

    def test_bearish_commodity(self):
        cf = CommodityFundamentals()
        result = cf.analyze(
            spot_price=100, futures_price=110,  # Deep contango
            price_vs_200sma_pct=-20, usd_index_change_pct=5,
            inventory_trend="building",
        )
        assert result.total < 35


# ==============================================================
# Divergence Detector
# ==============================================================

class TestDivergenceDetector:
    def test_crypto_divergence_detected(self):
        dd = DivergenceDetector(crypto_threshold_pct=0.5)
        signal = dd.check_crypto_divergence("BTC", 50500, 50000)
        assert signal is not None
        assert signal.direction in ("BULLISH", "BEARISH")

    def test_no_divergence_below_threshold(self):
        dd = DivergenceDetector(crypto_threshold_pct=0.5)
        signal = dd.check_crypto_divergence("BTC", 50100, 50000)
        assert signal is None

    def test_probability_divergence(self):
        dd = DivergenceDetector(probability_threshold_pct=10.0)
        signal = dd.check_probability_divergence("Fed Rate Cut", 75, 60)
        assert signal is not None
        assert signal.delta_pct == 15.0

    def test_active_signals_tracking(self):
        dd = DivergenceDetector(crypto_threshold_pct=0.5)
        dd.check_crypto_divergence("BTC", 51000, 50000)
        dd.check_crypto_divergence("ETH", 3100, 3000)
        assert len(dd.active_signals) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
