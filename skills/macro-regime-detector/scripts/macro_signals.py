"""Macro Signals — yield curve, VIX, junk bond spread, Buffett Indicator."""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger


@dataclass
class MacroAlert:
    """A macro signal alert."""
    signal: str
    severity: str  # INFO, WARNING, CRITICAL
    value: float
    threshold: float
    message: str


class MacroSignals:
    """Monitor key macro signals for early warning detection."""

    def check_all(
        self,
        yield_spread_10y2y: float | None = None,
        vix: float | None = None,
        junk_bond_spread_bps: float | None = None,
        buffett_indicator: float | None = None,
        m2_yoy_change_pct: float | None = None,
    ) -> list[MacroAlert]:
        """Run all macro signal checks and return alerts."""
        alerts: list[MacroAlert] = []

        if yield_spread_10y2y is not None:
            alert = self.check_yield_curve(yield_spread_10y2y)
            if alert:
                alerts.append(alert)

        if vix is not None:
            alert = self.check_vix(vix)
            if alert:
                alerts.append(alert)

        if junk_bond_spread_bps is not None:
            alert = self.check_junk_bond_spread(junk_bond_spread_bps)
            if alert:
                alerts.append(alert)

        if buffett_indicator is not None:
            alert = self.check_buffett_indicator(buffett_indicator)
            if alert:
                alerts.append(alert)

        if m2_yoy_change_pct is not None:
            alert = self.check_m2_supply(m2_yoy_change_pct)
            if alert:
                alerts.append(alert)

        return alerts

    def check_yield_curve(self, spread: float) -> MacroAlert | None:
        """10Y-2Y yield spread. Inversion (<0) = recession predictor."""
        if spread < -0.5:
            return MacroAlert(
                signal="YIELD_CURVE_DEEP_INVERSION",
                severity="CRITICAL",
                value=spread,
                threshold=0.0,
                message=f"Yield curve deeply inverted ({spread:.2f}%) — strong recession signal.",
            )
        elif spread < 0:
            return MacroAlert(
                signal="YIELD_CURVE_INVERTED",
                severity="WARNING",
                value=spread,
                threshold=0.0,
                message=f"Yield curve inverted ({spread:.2f}%) — recession risk elevated.",
            )
        return None

    def check_vix(self, vix: float) -> MacroAlert | None:
        """VIX spike detection."""
        if vix > 40:
            return MacroAlert(
                signal="VIX_EXTREME",
                severity="CRITICAL",
                value=vix,
                threshold=40.0,
                message=f"VIX at {vix:.1f} — extreme fear, market panic.",
            )
        elif vix > 30:
            return MacroAlert(
                signal="VIX_ELEVATED",
                severity="WARNING",
                value=vix,
                threshold=30.0,
                message=f"VIX at {vix:.1f} — elevated fear.",
            )
        return None

    def check_junk_bond_spread(self, spread_bps: float) -> MacroAlert | None:
        """High-yield bond spread. >500bps = credit stress."""
        if spread_bps > 700:
            return MacroAlert(
                signal="CREDIT_CRISIS",
                severity="CRITICAL",
                value=spread_bps,
                threshold=700,
                message=f"Junk bond spread at {spread_bps:.0f}bps — credit crisis conditions.",
            )
        elif spread_bps > 500:
            return MacroAlert(
                signal="CREDIT_STRESS",
                severity="WARNING",
                value=spread_bps,
                threshold=500,
                message=f"Junk bond spread at {spread_bps:.0f}bps — credit stress rising.",
            )
        return None

    def check_buffett_indicator(self, ratio: float) -> MacroAlert | None:
        """Wilshire 5000 / GDP. >150% = historically expensive."""
        if ratio > 200:
            return MacroAlert(
                signal="BUFFETT_EXTREME",
                severity="CRITICAL",
                value=ratio,
                threshold=200,
                message=f"Buffett Indicator at {ratio:.0f}% — extreme overvaluation.",
            )
        elif ratio > 150:
            return MacroAlert(
                signal="BUFFETT_ELEVATED",
                severity="WARNING",
                value=ratio,
                threshold=150,
                message=f"Buffett Indicator at {ratio:.0f}% — market historically expensive.",
            )
        return None

    def check_m2_supply(self, yoy_change_pct: float) -> MacroAlert | None:
        """M2 money supply growth. Contraction = liquidity drain."""
        if yoy_change_pct < -2:
            return MacroAlert(
                signal="M2_CONTRACTION",
                severity="WARNING",
                value=yoy_change_pct,
                threshold=-2,
                message=f"M2 contracting at {yoy_change_pct:.1f}% YoY — liquidity drain.",
            )
        return None
