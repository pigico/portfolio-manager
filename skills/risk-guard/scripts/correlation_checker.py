"""Correlation Checker — Prevents over-correlated positions.

Calculates rolling correlation between assets and rejects or reduces
positions that would create excessive correlation risk.
"""

from __future__ import annotations

import numpy as np
from loguru import logger


class CorrelationChecker:
    """Check correlation between a new position and existing holdings.

    If the new position has correlation > threshold with any existing
    position, it either reduces the proposed size proportionally or
    blocks the trade entirely.
    """

    def __init__(
        self,
        max_correlation: float = 0.7,
        lookback_days: int = 60,
    ) -> None:
        self._max_correlation = max_correlation
        self._lookback_days = lookback_days
        # Store price histories: asset -> list of daily returns
        self._price_histories: dict[str, list[float]] = {}

    def update_price_history(self, asset: str, daily_returns: list[float]) -> None:
        """Update stored price history for an asset.

        Args:
            asset: Asset ticker/symbol.
            daily_returns: List of daily return percentages.
        """
        self._price_histories[asset] = daily_returns[-self._lookback_days:]

    def calculate_correlation(self, asset_a: str, asset_b: str) -> float | None:
        """Calculate Pearson correlation between two assets.

        Returns:
            Correlation coefficient (-1 to 1), or None if insufficient data.
        """
        hist_a = self._price_histories.get(asset_a)
        hist_b = self._price_histories.get(asset_b)

        if not hist_a or not hist_b:
            return None

        # Align lengths
        min_len = min(len(hist_a), len(hist_b))
        if min_len < 20:  # Need at least 20 data points
            return None

        arr_a = np.array(hist_a[-min_len:])
        arr_b = np.array(hist_b[-min_len:])

        # Handle zero variance
        if np.std(arr_a) == 0 or np.std(arr_b) == 0:
            return 0.0

        corr_matrix = np.corrcoef(arr_a, arr_b)
        return float(corr_matrix[0, 1])

    def check(
        self,
        new_asset: str,
        existing_positions: list[str],
    ) -> tuple[bool, float, str]:
        """Check if a new position would create excessive correlation.

        Args:
            new_asset: The asset being proposed.
            existing_positions: List of currently held asset tickers.

        Returns:
            Tuple of:
                - allowed: bool (True if OK to proceed)
                - size_multiplier: float (1.0 = full size, <1.0 = reduced)
                - reason: str
        """
        if not existing_positions:
            return True, 1.0, "No existing positions — correlation check passed."

        max_found_corr = 0.0
        highest_corr_asset = ""

        for existing in existing_positions:
            corr = self.calculate_correlation(new_asset, existing)
            if corr is None:
                logger.debug(
                    f"Insufficient data for correlation between "
                    f"{new_asset} and {existing} — skipping."
                )
                continue

            abs_corr = abs(corr)
            if abs_corr > max_found_corr:
                max_found_corr = abs_corr
                highest_corr_asset = existing

        if max_found_corr > self._max_correlation:
            # High correlation — reduce size proportionally
            # At threshold: multiplier = 0.5, at 1.0: multiplier = 0.0
            overshoot = max_found_corr - self._max_correlation
            max_overshoot = 1.0 - self._max_correlation
            if max_overshoot > 0:
                reduction = overshoot / max_overshoot
            else:
                reduction = 1.0
            multiplier = max(0.0, 1.0 - reduction)

            if multiplier < 0.1:
                logger.warning(
                    f"BLOCKED: {new_asset} has {max_found_corr:.2f} correlation "
                    f"with {highest_corr_asset} (threshold: {self._max_correlation})"
                )
                return False, 0.0, (
                    f"Correlation {max_found_corr:.2f} with {highest_corr_asset} "
                    f"exceeds threshold {self._max_correlation}."
                )

            logger.info(
                f"REDUCED: {new_asset} has {max_found_corr:.2f} correlation "
                f"with {highest_corr_asset} — size multiplier: {multiplier:.2f}"
            )
            return True, multiplier, (
                f"High correlation ({max_found_corr:.2f}) with {highest_corr_asset}. "
                f"Size reduced to {multiplier:.0%}."
            )

        return True, 1.0, (
            f"Max correlation: {max_found_corr:.2f} "
            f"(threshold: {self._max_correlation}) — OK."
        )

    def get_correlation_matrix(self, assets: list[str]) -> dict[str, dict[str, float | None]]:
        """Get full correlation matrix for a list of assets."""
        matrix: dict[str, dict[str, float | None]] = {}
        for a in assets:
            matrix[a] = {}
            for b in assets:
                if a == b:
                    matrix[a][b] = 1.0
                else:
                    matrix[a][b] = self.calculate_correlation(a, b)
        return matrix

    def get_status(self) -> dict:
        """Return checker configuration and state."""
        return {
            "max_correlation": self._max_correlation,
            "lookback_days": self._lookback_days,
            "tracked_assets": list(self._price_histories.keys()),
        }
