"""Divergence Detector — Cross-platform price divergence detection.

Monitors real-time divergences between:
- Crypto: Binance vs CoinGecko
- Spot vs Futures: contango/backwardation anomalies
- Polymarket implied prob vs composite model score
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from loguru import logger


@dataclass
class DivergenceSignal:
    """A detected cross-platform divergence."""
    asset: str
    source_a: str
    source_b: str
    price_a: float
    price_b: float
    delta_pct: float
    direction: str  # "BULLISH" or "BEARISH"
    confidence: str  # "LOW", "MEDIUM", "HIGH"
    signal_type: str  # "PRICE", "PROBABILITY", "FUTURES"
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    @property
    def is_significant(self) -> bool:
        return abs(self.delta_pct) > 0.5


class DivergenceDetector:
    """Detect cross-platform divergences as high-conviction signals.

    Thresholds:
    - Crypto price: >0.5% divergence = signal
    - Spot vs Futures: abnormal contango/backwardation
    - Polymarket vs model: >10% divergence = high-conviction
    """

    def __init__(
        self,
        crypto_threshold_pct: float = 0.5,
        probability_threshold_pct: float = 10.0,
        futures_threshold_pct: float = 2.0,
    ) -> None:
        self._crypto_threshold = crypto_threshold_pct
        self._prob_threshold = probability_threshold_pct
        self._futures_threshold = futures_threshold_pct
        self._active_signals: list[DivergenceSignal] = []

    @property
    def active_signals(self) -> list[DivergenceSignal]:
        """Get currently active divergence signals."""
        return list(self._active_signals)

    def check_crypto_divergence(
        self,
        asset: str,
        binance_price: float,
        coingecko_price: float,
    ) -> DivergenceSignal | None:
        """Check for price divergence between Binance and CoinGecko.

        Args:
            asset: Crypto symbol (e.g., 'BTC').
            binance_price: Real-time price from Binance WS.
            coingecko_price: Price from CoinGecko REST API.

        Returns:
            DivergenceSignal if threshold breached, else None.
        """
        if binance_price <= 0 or coingecko_price <= 0:
            return None

        mid_price = (binance_price + coingecko_price) / 2
        delta_pct = ((binance_price - coingecko_price) / mid_price) * 100

        if abs(delta_pct) < self._crypto_threshold:
            return None

        # If Binance > CoinGecko, buying pressure on Binance = bullish
        direction = "BULLISH" if delta_pct > 0 else "BEARISH"
        confidence = self._classify_confidence(abs(delta_pct), self._crypto_threshold)

        signal = DivergenceSignal(
            asset=asset,
            source_a="binance",
            source_b="coingecko",
            price_a=binance_price,
            price_b=coingecko_price,
            delta_pct=round(delta_pct, 4),
            direction=direction,
            confidence=confidence,
            signal_type="PRICE",
        )

        self._update_active(signal)
        logger.info(
            f"DIVERGENCE [{asset}]: Binance={binance_price:.2f} vs "
            f"CoinGecko={coingecko_price:.2f} ({delta_pct:+.3f}%) — {direction}"
        )
        return signal

    def check_probability_divergence(
        self,
        event: str,
        model_probability: float,
        market_probability: float,
    ) -> DivergenceSignal | None:
        """Check divergence between our model and Polymarket implied probability.

        Args:
            event: Description of the event.
            model_probability: Our model's estimated probability (0-100).
            market_probability: Polymarket implied probability (0-100).

        Returns:
            DivergenceSignal if threshold breached.
        """
        delta_pct = model_probability - market_probability

        if abs(delta_pct) < self._prob_threshold:
            return None

        # If our model says higher prob than market → market underpricing
        direction = "BULLISH" if delta_pct > 0 else "BEARISH"
        confidence = self._classify_confidence(abs(delta_pct), self._prob_threshold)

        signal = DivergenceSignal(
            asset=event,
            source_a="model",
            source_b="polymarket",
            price_a=model_probability,
            price_b=market_probability,
            delta_pct=round(delta_pct, 2),
            direction=direction,
            confidence=confidence,
            signal_type="PROBABILITY",
        )

        self._update_active(signal)
        logger.info(
            f"DIVERGENCE [{event}]: Model={model_probability:.1f}% vs "
            f"Polymarket={market_probability:.1f}% ({delta_pct:+.1f}pp) — {direction}"
        )
        return signal

    def check_futures_divergence(
        self,
        asset: str,
        spot_price: float,
        futures_price: float,
    ) -> DivergenceSignal | None:
        """Check spot vs futures divergence (contango/backwardation anomalies).

        Args:
            asset: Asset symbol.
            spot_price: Current spot price.
            futures_price: Nearest futures contract price.
        """
        if spot_price <= 0 or futures_price <= 0:
            return None

        delta_pct = ((futures_price - spot_price) / spot_price) * 100

        if abs(delta_pct) < self._futures_threshold:
            return None

        # Backwardation (futures < spot) = supply squeeze = bullish
        # Extreme contango (futures >> spot) = oversupply = bearish
        direction = "BEARISH" if delta_pct > 0 else "BULLISH"
        confidence = self._classify_confidence(abs(delta_pct), self._futures_threshold)

        signal = DivergenceSignal(
            asset=asset,
            source_a="spot",
            source_b="futures",
            price_a=spot_price,
            price_b=futures_price,
            delta_pct=round(delta_pct, 4),
            direction=direction,
            confidence=confidence,
            signal_type="FUTURES",
        )

        self._update_active(signal)
        return signal

    def clear_old_signals(self, max_age_minutes: float = 60) -> int:
        """Remove signals older than max_age_minutes."""
        now = datetime.now(tz=UTC)
        before = len(self._active_signals)
        self._active_signals = [
            s for s in self._active_signals
            if (now - s.timestamp).total_seconds() < max_age_minutes * 60
        ]
        removed = before - len(self._active_signals)
        if removed:
            logger.debug(f"Cleared {removed} old divergence signals.")
        return removed

    def _classify_confidence(self, delta: float, threshold: float) -> str:
        if delta >= threshold * 3:
            return "HIGH"
        elif delta >= threshold * 2:
            return "MEDIUM"
        return "LOW"

    def _update_active(self, signal: DivergenceSignal) -> None:
        # Replace existing signal for same asset+type or append
        self._active_signals = [
            s for s in self._active_signals
            if not (s.asset == signal.asset and s.signal_type == signal.signal_type)
        ]
        self._active_signals.append(signal)

    def get_status(self) -> dict:
        return {
            "active_signals": len(self._active_signals),
            "signals": [
                {
                    "asset": s.asset,
                    "type": s.signal_type,
                    "delta_pct": s.delta_pct,
                    "direction": s.direction,
                    "confidence": s.confidence,
                }
                for s in self._active_signals
            ],
        }
