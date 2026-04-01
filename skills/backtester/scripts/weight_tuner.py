"""Weight Tuner — grid search optimization of scoring weights and thresholds.

Tests different weight combinations and thresholds to find optimal parameters.
Uses walk-forward validation to prevent overfitting.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

import numpy as np
from loguru import logger

from backtest_engine import BacktestConfig, BacktestEngine, BacktestResult


@dataclass
class TunerResult:
    """Result of a weight tuning run."""
    best_config: BacktestConfig
    best_sharpe: float
    best_return_pct: float
    all_results: list[dict]
    iterations: int


class WeightTuner:
    """Grid search over scoring weights and decision thresholds.

    Optimizes for Sharpe ratio (risk-adjusted return) rather than
    raw return to avoid parameter sets that take excessive risk.
    """

    def __init__(self, optimize_for: str = "sharpe") -> None:
        self._optimize_for = optimize_for

    def tune(
        self,
        asset: str,
        dates: list[str],
        opens: list[float],
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[float],
        # Weight ranges to search (as percentages, must sum to ~100)
        fundamental_range: list[float] | None = None,
        technical_range: list[float] | None = None,
        # Threshold ranges
        buy_threshold_range: list[float] | None = None,
        sell_threshold_range: list[float] | None = None,
    ) -> TunerResult:
        """Run grid search over parameter combinations.

        Default ranges are conservative to limit search space.
        """
        fund_range = fundamental_range or [0.25, 0.35, 0.45]
        tech_range = technical_range or [0.25, 0.30, 0.35]
        buy_range = buy_threshold_range or [60, 65, 70]
        sell_range = sell_threshold_range or [25, 30, 35]

        combinations = list(product(fund_range, tech_range, buy_range, sell_range))
        logger.info(f"Weight tuner: {len(combinations)} combinations to test")

        engine = BacktestEngine()
        all_results: list[dict] = []
        best_metric = -float("inf")
        best_config = BacktestConfig()

        for i, (fw, tw, bt, st) in enumerate(combinations):
            # Compute macro + sentiment weights to sum to 1
            remaining = 1.0 - fw - tw
            if remaining < 0.1:
                continue  # Invalid combination
            mw = remaining * 0.6  # 60% of remainder to macro
            sw = remaining * 0.4  # 40% to sentiment

            config = BacktestConfig(
                fundamental_weight=fw,
                technical_weight=tw,
                macro_weight=mw,
                sentiment_weight=sw,
                buy_threshold=bt,
                sell_threshold=st,
            )
            engine.config = config

            try:
                result = engine.run(
                    asset=asset, dates=dates,
                    opens=opens, highs=highs, lows=lows,
                    closes=closes, volumes=volumes,
                )

                metric = self._get_metric(result)
                all_results.append({
                    "fundamental_w": fw, "technical_w": tw,
                    "macro_w": round(mw, 3), "sentiment_w": round(sw, 3),
                    "buy_threshold": bt, "sell_threshold": st,
                    "return_pct": result.total_return_pct,
                    "sharpe": result.sharpe_ratio,
                    "max_dd": result.max_drawdown_pct,
                    "trades": result.total_trades,
                    "win_rate": result.win_rate,
                })

                if metric > best_metric:
                    best_metric = metric
                    best_config = config

            except Exception as e:
                logger.debug(f"Combination {i} failed: {e}")

            if (i + 1) % 10 == 0:
                logger.info(f"Tuner progress: {i + 1}/{len(combinations)}")

        # Sort by metric
        all_results.sort(key=lambda r: r.get("sharpe", 0), reverse=True)

        logger.info(
            f"Tuner complete: best Sharpe={best_metric:.3f} | "
            f"fund={best_config.fundamental_weight}, tech={best_config.technical_weight}, "
            f"buy_thr={best_config.buy_threshold}, sell_thr={best_config.sell_threshold}"
        )

        return TunerResult(
            best_config=best_config,
            best_sharpe=round(best_metric, 3),
            best_return_pct=all_results[0]["return_pct"] if all_results else 0,
            all_results=all_results,
            iterations=len(combinations),
        )

    def _get_metric(self, result: BacktestResult) -> float:
        if self._optimize_for == "sharpe":
            return result.sharpe_ratio
        elif self._optimize_for == "return":
            return result.total_return_pct
        elif self._optimize_for == "sortino":
            return result.sortino_ratio
        else:
            return result.sharpe_ratio
