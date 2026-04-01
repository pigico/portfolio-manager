"""Stock Fundamental Analyzer — 12 indicators scored 0-100.

Indicators (with weights):
P/E (12%), CAPE (8%), P/B (8%), P/S (5%), EV/EBITDA (8%), ROE (10%),
ROIC (10%), FCF Yield (12%), D/E (8%), EPS Growth 5yr (10%),
Dividend (5%), Piotroski F-Score (4%)
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger


@dataclass
class FundamentalScore:
    """Result of fundamental analysis."""
    total: float  # 0-100
    breakdown: dict[str, float]  # indicator -> score 0-100
    economic_moat: str  # Wide, Narrow, None
    rationale: str


class StockFundamentals:
    """Analyze stock fundamentals and produce a composite score."""

    WEIGHTS = {
        "pe_ratio": 0.12,
        "cape": 0.08,
        "pb_ratio": 0.08,
        "ps_ratio": 0.05,
        "ev_ebitda": 0.08,
        "roe": 0.10,
        "roic": 0.10,
        "fcf_yield": 0.12,
        "debt_to_equity": 0.08,
        "eps_growth_5yr": 0.10,
        "dividend": 0.05,
        "piotroski": 0.04,
    }

    def analyze(self, data: dict) -> FundamentalScore:
        """Analyze fundamental data and return scored result.

        Args:
            data: Dict with fundamental metrics from collectors.
                  Keys: pe_ratio, pb_ratio, ps_ratio, ev_ebitda, roe, roic,
                  fcf_yield, debt_to_equity, eps_growth_5yr, dividend_yield,
                  payout_ratio, income_statements, balance_sheets, cash_flows
        """
        breakdown: dict[str, float] = {}

        # P/E Ratio — lower is better (value)
        breakdown["pe_ratio"] = self._score_pe(data.get("pe_ratio"))

        # Shiller CAPE — placeholder (needs 10yr data)
        breakdown["cape"] = 50.0  # Default neutral until we have CAPE data

        # P/B Ratio
        breakdown["pb_ratio"] = self._score_pb(data.get("pb_ratio"))

        # P/S Ratio
        breakdown["ps_ratio"] = self._score_ps(data.get("ps_ratio"))

        # EV/EBITDA
        breakdown["ev_ebitda"] = self._score_ev_ebitda(data.get("ev_ebitda"))

        # ROE
        breakdown["roe"] = self._score_roe(data.get("roe"))

        # ROIC
        breakdown["roic"] = self._score_roic(data.get("roic"))

        # FCF Yield
        breakdown["fcf_yield"] = self._score_fcf_yield(data.get("fcf_yield"))

        # Debt-to-Equity
        breakdown["debt_to_equity"] = self._score_de(data.get("debt_to_equity"))

        # EPS Growth 5yr CAGR
        breakdown["eps_growth_5yr"] = self._score_eps_growth(data.get("income_statements", []))

        # Dividend
        breakdown["dividend"] = self._score_dividend(
            data.get("dividend_yield"), data.get("payout_ratio")
        )

        # Piotroski F-Score
        breakdown["piotroski"] = self._score_piotroski(data) * (100 / 9)

        # Weighted total
        total = sum(
            breakdown[k] * self.WEIGHTS[k] for k in self.WEIGHTS
        )
        total = round(max(0, min(100, total)), 1)

        moat = self._assess_moat(breakdown)

        strong = [k for k, v in breakdown.items() if v >= 75]
        weak = [k for k, v in breakdown.items() if v <= 25]
        rationale = f"Score {total}/100. "
        if strong:
            rationale += f"Strengths: {', '.join(strong[:3])}. "
        if weak:
            rationale += f"Weaknesses: {', '.join(weak[:3])}. "
        rationale += f"Moat: {moat}."

        return FundamentalScore(total=total, breakdown=breakdown, economic_moat=moat, rationale=rationale)

    # ── Individual scorers (0-100) ───────────────────────

    def _score_pe(self, pe: float | None) -> float:
        if pe is None or pe <= 0:
            return 50.0
        if pe < 10:
            return 95
        if pe < 15:
            return 80
        if pe < 20:
            return 60
        if pe < 25:
            return 40
        if pe < 35:
            return 20
        return 5

    def _score_pb(self, pb: float | None) -> float:
        if pb is None or pb <= 0:
            return 50.0
        if pb < 1.0:
            return 95
        if pb < 1.5:
            return 80
        if pb < 2.0:
            return 65
        if pb < 3.0:
            return 45
        if pb < 5.0:
            return 25
        return 10

    def _score_ps(self, ps: float | None) -> float:
        if ps is None or ps <= 0:
            return 50.0
        if ps < 1.0:
            return 90
        if ps < 2.0:
            return 70
        if ps < 5.0:
            return 50
        if ps < 10.0:
            return 30
        return 10

    def _score_ev_ebitda(self, ev: float | None) -> float:
        if ev is None or ev <= 0:
            return 50.0
        if ev < 8:
            return 90
        if ev < 10:
            return 75
        if ev < 15:
            return 55
        if ev < 20:
            return 35
        return 15

    def _score_roe(self, roe: float | None) -> float:
        if roe is None:
            return 50.0
        # yfinance returns ROE as ratio (e.g. 1.52 = 152%), FMP as decimal
        roe_pct = roe * 100 if abs(roe) < 1 else roe if abs(roe) < 100 else roe
        # If still looks like a ratio > 1 (e.g. 1.52), convert
        if 1 < abs(roe) < 10:
            roe_pct = roe * 100
        if roe_pct > 25:
            return 95
        if roe_pct > 15:
            return 80
        if roe_pct > 10:
            return 60
        if roe_pct > 5:
            return 40
        return 15

    def _score_roic(self, roic: float | None) -> float:
        if roic is None:
            return 50.0
        roic_pct = roic * 100 if roic < 1 else roic
        if roic_pct > 20:
            return 95
        if roic_pct > 12:
            return 80
        if roic_pct > 8:
            return 55
        if roic_pct > 4:
            return 35
        return 15

    def _score_fcf_yield(self, fcf: float | None) -> float:
        if fcf is None:
            return 50.0
        fcf_pct = fcf * 100 if fcf < 1 else fcf
        if fcf_pct > 8:
            return 95
        if fcf_pct > 5:
            return 80
        if fcf_pct > 3:
            return 60
        if fcf_pct > 1:
            return 40
        return 15

    def _score_de(self, de: float | None) -> float:
        if de is None:
            return 50.0
        # yfinance returns D/E as percentage (e.g. 102.63 = 1.0263 ratio)
        if de > 10:
            de = de / 100.0  # Convert from percentage to ratio
        if de < 0.3:
            return 95
        if de < 0.5:
            return 80
        if de < 1.0:
            return 60
        if de < 2.0:
            return 35
        return 10

    def _score_eps_growth(self, income_statements: list[dict]) -> float:
        if not income_statements or len(income_statements) < 2:
            return 50.0
        try:
            latest_eps = float(income_statements[0].get("eps", 0) or 0)
            oldest_eps = float(income_statements[-1].get("eps", 0) or 0)
            if oldest_eps <= 0 or latest_eps <= 0:
                return 50.0
            years = len(income_statements) - 1
            cagr = ((latest_eps / oldest_eps) ** (1 / years) - 1) * 100
            if cagr > 20:
                return 95
            if cagr > 10:
                return 75
            if cagr > 5:
                return 55
            if cagr > 0:
                return 35
            return 15
        except (ValueError, ZeroDivisionError):
            return 50.0

    def _score_dividend(self, div_yield: float | None, payout: float | None) -> float:
        if div_yield is None:
            return 50.0
        dy = div_yield * 100 if div_yield < 1 else div_yield
        pr = (payout * 100 if payout and payout < 1 else payout) or 50

        if dy > 2 and pr < 60:
            return 85  # Good yield, sustainable
        if dy > 1 and pr < 70:
            return 65
        if dy > 0:
            return 50
        return 40  # No dividend not necessarily bad

    def _score_piotroski(self, data: dict) -> float:
        """Simplified Piotroski F-Score (0-9 points)."""
        score = 0
        if (data.get("roe") or 0) > 0:
            score += 1  # Positive ROA proxy
        if (data.get("fcf_yield") or 0) > 0:
            score += 1  # Positive operating CF
        if (data.get("fcf_yield") or 0) > (data.get("roe") or 0):
            score += 1  # CF > earnings (quality)
        if (data.get("debt_to_equity") or 999) < 1.0:
            score += 1  # Low leverage
        # Remaining 5 points need YoY comparisons (simplified here)
        score += 3  # Default moderate for unavailable metrics
        return min(9, score)

    def _assess_moat(self, breakdown: dict) -> str:
        quality_metrics = [
            breakdown.get("roe", 0),
            breakdown.get("roic", 0),
            breakdown.get("fcf_yield", 0),
        ]
        avg_quality = sum(quality_metrics) / len(quality_metrics)
        if avg_quality >= 75:
            return "Wide"
        elif avg_quality >= 50:
            return "Narrow"
        return "None"
