"""Portfolio Optimizer — MVO, HRP, Black-Litterman, Min Volatility.

Uses PyPortfolioOpt where available, with simplified fallbacks.
"""

from __future__ import annotations

from enum import Enum

import numpy as np
from loguru import logger


class OptMethod(str, Enum):
    MEAN_VARIANCE = "mean_variance"
    HRP = "hrp"
    MIN_VOLATILITY = "min_volatility"
    EQUAL_WEIGHT = "equal_weight"


class PortfolioOptimizer:
    """Optimize portfolio allocation using multiple methods.

    Methods:
    - Mean-Variance: efficient frontier with target return/risk
    - HRP: Hierarchical Risk Parity (robust)
    - Min Volatility: minimize risk (for defensive regimes)
    - Equal Weight: baseline fallback
    """

    def optimize(
        self,
        expected_returns: dict[str, float],
        covariance_matrix: dict[str, dict[str, float]] | None = None,
        historical_returns: dict[str, list[float]] | None = None,
        method: OptMethod = OptMethod.EQUAL_WEIGHT,
        constraints: dict | None = None,
    ) -> dict[str, float]:
        """Optimize portfolio weights.

        Args:
            expected_returns: Dict of asset -> expected annual return.
            covariance_matrix: Optional covariance matrix.
            historical_returns: Optional dict of asset -> list of daily returns.
            method: Optimization method to use.
            constraints: Optional dict with 'max_weight', 'min_weight'.

        Returns:
            Dict of asset -> target weight (0-1, summing to 1).
        """
        assets = list(expected_returns.keys())
        if not assets:
            return {}

        max_w = (constraints or {}).get("max_weight", 0.20)
        min_w = (constraints or {}).get("min_weight", 0.0)

        try:
            if method == OptMethod.MEAN_VARIANCE:
                return self._mean_variance(expected_returns, historical_returns, max_w, min_w)
            elif method == OptMethod.HRP:
                return self._hrp(assets, historical_returns)
            elif method == OptMethod.MIN_VOLATILITY:
                return self._min_volatility(assets, historical_returns, max_w)
            else:
                return self._equal_weight(assets)
        except Exception as e:
            logger.warning(f"Optimization failed ({method.value}): {e}. Falling back to equal weight.")
            return self._equal_weight(assets)

    def _equal_weight(self, assets: list[str]) -> dict[str, float]:
        """Simple equal weighting."""
        n = len(assets)
        w = round(1.0 / n, 4) if n > 0 else 0
        weights = {a: w for a in assets}
        logger.debug(f"Equal weight: {n} assets at {w:.2%} each.")
        return weights

    def _mean_variance(
        self,
        expected_returns: dict[str, float],
        historical_returns: dict[str, list[float]] | None,
        max_w: float,
        min_w: float,
    ) -> dict[str, float]:
        """Mean-Variance optimization using PyPortfolioOpt or fallback."""
        try:
            from pypfopt import EfficientFrontier, expected_returns as er, risk_models
            import pandas as pd

            if historical_returns:
                df = pd.DataFrame(historical_returns)
                mu = er.mean_historical_return(df)
                S = risk_models.sample_cov(df)
            else:
                assets = list(expected_returns.keys())
                mu = pd.Series(expected_returns)
                # Without historical data, use identity-like covariance
                n = len(assets)
                S = pd.DataFrame(
                    np.eye(n) * 0.04,
                    index=assets, columns=assets,
                )

            ef = EfficientFrontier(mu, S, weight_bounds=(min_w, max_w))
            ef.max_sharpe()
            weights = ef.clean_weights()
            logger.info(f"MVO optimized: {dict(weights)}")
            return dict(weights)
        except ImportError:
            logger.debug("PyPortfolioOpt not installed — using score-weighted fallback.")
            return self._score_weighted_fallback(expected_returns, max_w)

    def _hrp(
        self,
        assets: list[str],
        historical_returns: dict[str, list[float]] | None,
    ) -> dict[str, float]:
        """Hierarchical Risk Parity."""
        try:
            from pypfopt import HRPOpt
            import pandas as pd

            if not historical_returns:
                return self._equal_weight(assets)

            df = pd.DataFrame(historical_returns)
            hrp = HRPOpt(df)
            hrp.optimize()
            weights = hrp.clean_weights()
            logger.info(f"HRP optimized: {dict(weights)}")
            return dict(weights)
        except ImportError:
            logger.debug("PyPortfolioOpt not installed — falling back to equal weight.")
            return self._equal_weight(assets)

    def _min_volatility(
        self,
        assets: list[str],
        historical_returns: dict[str, list[float]] | None,
        max_w: float,
    ) -> dict[str, float]:
        """Minimum volatility portfolio."""
        try:
            from pypfopt import EfficientFrontier, risk_models
            import pandas as pd

            if not historical_returns:
                return self._equal_weight(assets)

            df = pd.DataFrame(historical_returns)
            S = risk_models.sample_cov(df)
            mu = pd.Series({a: 0.0 for a in assets})  # Don't care about returns

            ef = EfficientFrontier(mu, S, weight_bounds=(0, max_w))
            ef.min_volatility()
            weights = ef.clean_weights()
            logger.info(f"MinVol optimized: {dict(weights)}")
            return dict(weights)
        except ImportError:
            return self._equal_weight(assets)

    def _score_weighted_fallback(
        self, expected_returns: dict[str, float], max_w: float
    ) -> dict[str, float]:
        """Fallback: weight by expected return (proxy for score)."""
        total = sum(max(0, r) for r in expected_returns.values())
        if total == 0:
            return self._equal_weight(list(expected_returns.keys()))

        weights = {}
        for asset, ret in expected_returns.items():
            w = max(0, ret) / total
            weights[asset] = round(min(max_w, w), 4)

        # Normalize
        wsum = sum(weights.values())
        if wsum > 0:
            weights = {a: round(w / wsum, 4) for a, w in weights.items()}

        return weights
