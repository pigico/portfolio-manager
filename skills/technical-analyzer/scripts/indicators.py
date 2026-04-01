"""Technical Indicators — RSI, MACD, BB, SMA, EMA, ADX, OBV, ATR, etc.

Uses pandas-ta where available, with pure-numpy fallbacks.
Each indicator produces a sub-signal: BULLISH / BEARISH / NEUTRAL.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
from loguru import logger


class Signal(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


@dataclass
class IndicatorResult:
    """Result of a single indicator calculation."""
    name: str
    value: float
    signal: Signal
    detail: str = ""


class TechnicalIndicators:
    """Calculate technical indicators and generate signals."""

    def compute_all(
        self,
        closes: list[float],
        highs: list[float] | None = None,
        lows: list[float] | None = None,
        volumes: list[float] | None = None,
    ) -> list[IndicatorResult]:
        """Compute all indicators on price data.

        Args:
            closes: List of closing prices (oldest first).
            highs: List of high prices.
            lows: List of low prices.
            volumes: List of volume data.

        Returns:
            List of IndicatorResult for each computed indicator.
        """
        c = np.array(closes, dtype=float)
        h = np.array(highs or closes, dtype=float)
        l_ = np.array(lows or closes, dtype=float)
        v = np.array(volumes or [0] * len(closes), dtype=float)

        results: list[IndicatorResult] = []

        if len(c) < 26:
            logger.warning("Insufficient data (<26 periods) for full indicator set.")
            return results

        results.append(self.rsi(c))
        results.append(self.macd(c))
        results.append(self.bollinger_bands(c))

        if len(c) >= 200:
            results.append(self.sma_cross(c))
        results.append(self.ema_cross(c))
        results.append(self.adx(h, l_, c))
        results.append(self.stochastic(h, l_, c))

        if v.sum() > 0:
            results.append(self.obv(c, v))

        results.append(self.atr(h, l_, c))

        return results

    def rsi(self, closes: np.ndarray, period: int = 14) -> IndicatorResult:
        """RSI — Relative Strength Index."""
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])

        if avg_loss == 0:
            rsi_val = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_val = 100 - (100 / (1 + rs))

        if rsi_val < 30:
            signal = Signal.BULLISH
            detail = f"RSI={rsi_val:.1f} — oversold"
        elif rsi_val > 70:
            signal = Signal.BEARISH
            detail = f"RSI={rsi_val:.1f} — overbought"
        else:
            signal = Signal.NEUTRAL
            detail = f"RSI={rsi_val:.1f}"

        return IndicatorResult("RSI", rsi_val, signal, detail)

    def macd(
        self, closes: np.ndarray,
        fast: int = 12, slow: int = 26, signal_period: int = 9,
    ) -> IndicatorResult:
        """MACD — Moving Average Convergence Divergence."""
        ema_fast = self._ema(closes, fast)
        ema_slow = self._ema(closes, slow)
        macd_line = ema_fast - ema_slow
        signal_line = self._ema(macd_line, signal_period)
        histogram = macd_line - signal_line

        current_hist = histogram[-1]
        prev_hist = histogram[-2] if len(histogram) > 1 else 0

        if macd_line[-1] > signal_line[-1] and prev_hist <= 0 < current_hist:
            signal = Signal.BULLISH
            detail = "MACD bullish crossover"
        elif macd_line[-1] < signal_line[-1] and prev_hist >= 0 > current_hist:
            signal = Signal.BEARISH
            detail = "MACD bearish crossover"
        elif current_hist > 0:
            signal = Signal.BULLISH
            detail = f"MACD positive histogram ({current_hist:.4f})"
        elif current_hist < 0:
            signal = Signal.BEARISH
            detail = f"MACD negative histogram ({current_hist:.4f})"
        else:
            signal = Signal.NEUTRAL
            detail = "MACD neutral"

        return IndicatorResult("MACD", current_hist, signal, detail)

    def bollinger_bands(
        self, closes: np.ndarray, period: int = 20, num_std: float = 2.0,
    ) -> IndicatorResult:
        """Bollinger Bands."""
        if len(closes) < period:
            return IndicatorResult("BB", 0, Signal.NEUTRAL, "Insufficient data")

        sma = np.mean(closes[-period:])
        std = np.std(closes[-period:])
        upper = sma + num_std * std
        lower = sma - num_std * std
        current = closes[-1]

        # %B = (price - lower) / (upper - lower)
        band_width = upper - lower
        pct_b = (current - lower) / band_width if band_width > 0 else 0.5

        if current <= lower:
            signal = Signal.BULLISH
            detail = f"Price at/below lower BB ({current:.2f} ≤ {lower:.2f})"
        elif current >= upper:
            signal = Signal.BEARISH
            detail = f"Price at/above upper BB ({current:.2f} ≥ {upper:.2f})"
        else:
            signal = Signal.NEUTRAL
            detail = f"BB %B={pct_b:.2f}"

        return IndicatorResult("BB", pct_b, signal, detail)

    def sma_cross(self, closes: np.ndarray) -> IndicatorResult:
        """SMA 50/200 Golden Cross / Death Cross."""
        sma50 = np.mean(closes[-50:])
        sma200 = np.mean(closes[-200:])

        if sma50 > sma200:
            prev_sma50 = np.mean(closes[-51:-1])
            prev_sma200 = np.mean(closes[-201:-1])
            if prev_sma50 <= prev_sma200:
                signal = Signal.BULLISH
                detail = "Golden Cross — SMA50 just crossed above SMA200"
            else:
                signal = Signal.BULLISH
                detail = f"SMA50 ({sma50:.2f}) > SMA200 ({sma200:.2f})"
        else:
            signal = Signal.BEARISH
            detail = f"SMA50 ({sma50:.2f}) < SMA200 ({sma200:.2f})"

        return IndicatorResult("SMA_CROSS", sma50 - sma200, signal, detail)

    def ema_cross(self, closes: np.ndarray) -> IndicatorResult:
        """EMA 12/26 cross."""
        ema12 = self._ema(closes, 12)[-1]
        ema26 = self._ema(closes, 26)[-1]

        if ema12 > ema26:
            signal = Signal.BULLISH
            detail = f"EMA12 ({ema12:.2f}) > EMA26 ({ema26:.2f})"
        else:
            signal = Signal.BEARISH
            detail = f"EMA12 ({ema12:.2f}) < EMA26 ({ema26:.2f})"

        return IndicatorResult("EMA_CROSS", ema12 - ema26, signal, detail)

    def adx(
        self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
        period: int = 14,
    ) -> IndicatorResult:
        """ADX — Average Directional Index (trend strength)."""
        if len(closes) < period + 1:
            return IndicatorResult("ADX", 0, Signal.NEUTRAL, "Insufficient data")

        # Simplified ADX calculation
        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                np.abs(highs[1:] - closes[:-1]),
                np.abs(lows[1:] - closes[:-1]),
            ),
        )
        atr = np.mean(tr[-period:])

        plus_dm = np.where(
            (highs[1:] - highs[:-1]) > (lows[:-1] - lows[1:]),
            np.maximum(highs[1:] - highs[:-1], 0),
            0,
        )
        minus_dm = np.where(
            (lows[:-1] - lows[1:]) > (highs[1:] - highs[:-1]),
            np.maximum(lows[:-1] - lows[1:], 0),
            0,
        )

        if atr == 0:
            adx_val = 0.0
        else:
            plus_di = (np.mean(plus_dm[-period:]) / atr) * 100
            minus_di = (np.mean(minus_dm[-period:]) / atr) * 100
            di_sum = plus_di + minus_di
            dx = (abs(plus_di - minus_di) / di_sum * 100) if di_sum > 0 else 0
            adx_val = dx  # Simplified — real ADX uses smoothed DX

        if adx_val > 25:
            signal = Signal.BULLISH  # Strong trend (direction from other indicators)
            detail = f"ADX={adx_val:.1f} — strong trend"
        elif adx_val < 20:
            signal = Signal.NEUTRAL
            detail = f"ADX={adx_val:.1f} — no clear trend (range-bound)"
        else:
            signal = Signal.NEUTRAL
            detail = f"ADX={adx_val:.1f} — moderate trend"

        return IndicatorResult("ADX", adx_val, signal, detail)

    def stochastic(
        self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
        k_period: int = 14, d_period: int = 3,
    ) -> IndicatorResult:
        """Stochastic Oscillator."""
        if len(closes) < k_period:
            return IndicatorResult("STOCH", 50, Signal.NEUTRAL, "Insufficient data")

        highest_high = np.max(highs[-k_period:])
        lowest_low = np.min(lows[-k_period:])
        denom = highest_high - lowest_low

        pct_k = ((closes[-1] - lowest_low) / denom * 100) if denom > 0 else 50

        if pct_k < 20:
            signal = Signal.BULLISH
            detail = f"%K={pct_k:.1f} — oversold"
        elif pct_k > 80:
            signal = Signal.BEARISH
            detail = f"%K={pct_k:.1f} — overbought"
        else:
            signal = Signal.NEUTRAL
            detail = f"%K={pct_k:.1f}"

        return IndicatorResult("STOCHASTIC", pct_k, signal, detail)

    def obv(self, closes: np.ndarray, volumes: np.ndarray) -> IndicatorResult:
        """OBV — On-Balance Volume."""
        obv_values = np.zeros(len(closes))
        for i in range(1, len(closes)):
            if closes[i] > closes[i - 1]:
                obv_values[i] = obv_values[i - 1] + volumes[i]
            elif closes[i] < closes[i - 1]:
                obv_values[i] = obv_values[i - 1] - volumes[i]
            else:
                obv_values[i] = obv_values[i - 1]

        # OBV trend over last 20 periods
        if len(obv_values) >= 20:
            obv_sma = np.mean(obv_values[-20:])
            if obv_values[-1] > obv_sma and closes[-1] > closes[-20]:
                signal = Signal.BULLISH
                detail = "Rising OBV confirms price uptrend"
            elif obv_values[-1] < obv_sma and closes[-1] > closes[-20]:
                signal = Signal.BEARISH
                detail = "OBV divergence — price up but volume declining"
            else:
                signal = Signal.NEUTRAL
                detail = "OBV neutral"
        else:
            signal = Signal.NEUTRAL
            detail = "Insufficient OBV data"

        return IndicatorResult("OBV", obv_values[-1], signal, detail)

    def atr(
        self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
        period: int = 14,
    ) -> IndicatorResult:
        """ATR — Average True Range (volatility for position sizing)."""
        if len(closes) < period + 1:
            return IndicatorResult("ATR", 0, Signal.NEUTRAL, "Insufficient data")

        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                np.abs(highs[1:] - closes[:-1]),
                np.abs(lows[1:] - closes[:-1]),
            ),
        )
        atr_val = float(np.mean(tr[-period:]))
        atr_pct = (atr_val / closes[-1]) * 100 if closes[-1] > 0 else 0

        # ATR is not directional — used for position sizing
        signal = Signal.NEUTRAL
        detail = f"ATR={atr_val:.2f} ({atr_pct:.2f}% of price)"

        return IndicatorResult("ATR", atr_val, signal, detail)

    def _ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calculate Exponential Moving Average."""
        alpha = 2 / (period + 1)
        ema = np.zeros(len(data))
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1]
        return ema
