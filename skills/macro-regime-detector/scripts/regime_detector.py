"""Regime Detector — Dalio 4-quadrant economic regime classification.

Classifies the current macroeconomic environment into one of:
- Goldilocks: GDP↑ + CPI↓ (risk-on)
- Reflation: GDP↑ + CPI↑ (commodities, value)
- Deflation: GDP↓ + CPI↓ (bonds, defensives)
- Stagflation: GDP↓ + CPI↑ (gold, cash, BTC)
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger


@dataclass
class MacroRegime:
    """Result of macro regime detection."""
    regime: str  # Goldilocks, Reflation, Deflation, Stagflation
    confidence: float  # 0-1
    previous_regime: str | None
    transition_probability: float  # 0-1, probability of regime change
    recommended_weights: dict[str, float]  # asset_class -> weight
    indicators: dict[str, float]
    rationale: str


class RegimeDetector:
    """Detect current economic regime using macro indicators from FRED.

    Uses trend comparison: SMA(3 month) vs SMA(12 month) for GDP and CPI
    to determine direction of growth and inflation.
    """

    # Recommended asset weights per regime
    REGIME_WEIGHTS = {
        "Goldilocks": {"stocks": 50, "crypto": 25, "commodities": 10, "cash": 15},
        "Reflation": {"stocks": 30, "crypto": 15, "commodities": 30, "cash": 25},
        "Deflation": {"stocks": 20, "crypto": 10, "commodities": 10, "cash": 60},
        "Stagflation": {"stocks": 10, "crypto": 15, "commodities": 25, "cash": 50},
    }

    def __init__(self) -> None:
        self._previous_regime: str | None = None

    def detect(
        self,
        gdp_observations: list[dict] | None = None,
        cpi_observations: list[dict] | None = None,
        yield_spread_10y2y: float | None = None,
        ism_pmi: float | None = None,
        unemployment_rate: float | None = None,
        unemployment_claims_trend: str | None = None,
    ) -> MacroRegime:
        """Detect current macro regime.

        Args:
            gdp_observations: List of {date, value} from FRED GDP series.
            cpi_observations: List of {date, value} from FRED CPI series.
            yield_spread_10y2y: 10Y-2Y yield spread (negative = inversion).
            ism_pmi: ISM Manufacturing PMI.
            unemployment_rate: Current unemployment rate.
            unemployment_claims_trend: "rising" or "falling".
        """
        # Calculate growth and inflation trends
        growth_trend = self._calculate_trend(gdp_observations)
        inflation_trend = self._calculate_trend(cpi_observations)

        # Enhance with supplementary indicators
        growth_signal = self._growth_signal(growth_trend, ism_pmi, yield_spread_10y2y)
        inflation_signal = self._inflation_signal(inflation_trend)

        # Classify regime
        regime = self._classify(growth_signal, inflation_signal)

        # Calculate confidence
        confidence = self._calculate_confidence(
            growth_signal, inflation_signal, yield_spread_10y2y, ism_pmi
        )

        # Transition probability
        transition_prob = 0.0
        if self._previous_regime and self._previous_regime != regime:
            transition_prob = 1.0 - confidence
        elif self._previous_regime == regime and confidence < 0.5:
            transition_prob = 0.5

        weights = self.REGIME_WEIGHTS.get(regime, self.REGIME_WEIGHTS["Goldilocks"])

        indicators = {
            "growth_trend": growth_trend,
            "inflation_trend": inflation_trend,
            "growth_signal": growth_signal,
            "inflation_signal": inflation_signal,
            "yield_spread": yield_spread_10y2y or 0,
            "ism_pmi": ism_pmi or 0,
        }

        rationale = (
            f"Regime: {regime} (confidence {confidence:.0%}). "
            f"Growth {'rising' if growth_signal > 0 else 'falling'} "
            f"({growth_signal:+.2f}), "
            f"Inflation {'rising' if inflation_signal > 0 else 'falling'} "
            f"({inflation_signal:+.2f})."
        )
        if yield_spread_10y2y is not None and yield_spread_10y2y < 0:
            rationale += " WARNING: Yield curve inverted — recession risk."

        prev = self._previous_regime
        self._previous_regime = regime

        logger.info(f"Macro regime: {regime} (confidence={confidence:.2f})")

        return MacroRegime(
            regime=regime,
            confidence=confidence,
            previous_regime=prev,
            transition_probability=transition_prob,
            recommended_weights=weights,
            indicators=indicators,
            rationale=rationale,
        )

    def _calculate_trend(self, observations: list[dict] | None) -> float:
        """Calculate trend: SMA(3) vs SMA(12). Positive = rising."""
        if not observations or len(observations) < 12:
            return 0.0

        values = [o["value"] for o in observations[:12]]
        sma3 = sum(values[:3]) / 3
        sma12 = sum(values) / 12

        if sma12 == 0:
            return 0.0
        return (sma3 - sma12) / sma12

    def _growth_signal(
        self,
        gdp_trend: float,
        ism_pmi: float | None,
        yield_spread: float | None,
    ) -> float:
        """Composite growth signal incorporating multiple indicators."""
        signal = gdp_trend

        if ism_pmi is not None:
            # PMI > 50 = expansion, < 50 = contraction
            pmi_signal = (ism_pmi - 50) / 50
            signal = signal * 0.6 + pmi_signal * 0.4

        if yield_spread is not None and yield_spread < 0:
            # Inverted curve = strong recessionary signal
            signal -= 0.2

        return signal

    def _inflation_signal(self, cpi_trend: float) -> float:
        """Inflation direction signal."""
        return cpi_trend

    def _classify(self, growth: float, inflation: float) -> str:
        if growth > 0 and inflation <= 0:
            return "Goldilocks"
        elif growth > 0 and inflation > 0:
            return "Reflation"
        elif growth <= 0 and inflation <= 0:
            return "Deflation"
        else:  # growth <= 0 and inflation > 0
            return "Stagflation"

    def _calculate_confidence(
        self,
        growth: float,
        inflation: float,
        yield_spread: float | None,
        ism_pmi: float | None,
    ) -> float:
        """Higher confidence when signals are stronger and aligned."""
        # Base confidence from signal magnitude
        magnitude = (abs(growth) + abs(inflation)) / 2
        confidence = min(1.0, magnitude * 10 + 0.3)

        # Yield curve confirmation
        if yield_spread is not None:
            if (growth > 0 and yield_spread > 0) or (growth < 0 and yield_spread < 0):
                confidence = min(1.0, confidence + 0.1)

        # PMI confirmation
        if ism_pmi is not None:
            if (growth > 0 and ism_pmi > 50) or (growth < 0 and ism_pmi < 50):
                confidence = min(1.0, confidence + 0.1)

        return round(confidence, 2)
