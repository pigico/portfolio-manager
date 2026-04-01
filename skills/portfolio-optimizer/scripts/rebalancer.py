"""Rebalancer — trigger-based portfolio rebalancing.

9 trigger conditions, each generating trade proposals that MUST pass through RiskGuard.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from loguru import logger


@dataclass
class RebalanceAction:
    """A suggested rebalancing action."""
    asset: str
    action: str  # BUY, SELL, REDUCE
    current_weight: float
    target_weight: float
    delta_weight: float
    score: float
    rationale: str
    trigger: str  # Which trigger caused this
    timestamp: datetime


class Rebalancer:
    """Generate rebalancing proposals based on 9 trigger conditions.

    Triggers:
    1. DRIFT: asset deviates >5% from target weight
    2. SCORE: score drops <30 or new asset enters >80
    3. MACRO_REGIME: regime quadrant change
    4. POSTURE: exposure ceiling category change
    5. TECHNICAL: death cross, RSI >80 sustained
    6. DIVERGENCE: significant cross-platform divergence
    7. AI_OVERRIDE: Claude identifies material event
    8. RISK: drawdown >-10% or position loss >-15%
    9. CALENDAR: monthly review, quarterly deep analysis
    """

    def __init__(self, drift_threshold_pct: float = 5.0) -> None:
        self._drift_threshold = drift_threshold_pct

    def check_drift(
        self,
        current_weights: dict[str, float],
        target_weights: dict[str, float],
    ) -> list[RebalanceAction]:
        """Check for drift beyond threshold."""
        actions = []
        all_assets = set(current_weights.keys()) | set(target_weights.keys())

        for asset in all_assets:
            current = current_weights.get(asset, 0)
            target = target_weights.get(asset, 0)
            delta = target - current

            if abs(delta) > self._drift_threshold:
                action = "BUY" if delta > 0 else "REDUCE"
                actions.append(RebalanceAction(
                    asset=asset,
                    action=action,
                    current_weight=current,
                    target_weight=target,
                    delta_weight=round(delta, 2),
                    score=0,
                    rationale=f"Drift {delta:+.1f}% from target (threshold {self._drift_threshold}%).",
                    trigger="DRIFT",
                    timestamp=datetime.now(tz=UTC),
                ))

        if actions:
            logger.info(f"Drift trigger: {len(actions)} rebalancing actions needed.")
        return actions

    def check_score_triggers(
        self,
        scores: dict[str, float],
        current_positions: set[str],
    ) -> list[RebalanceAction]:
        """Check for score-based triggers (SELL <30, new opportunities >80)."""
        actions = []

        for asset, score in scores.items():
            if asset in current_positions and score < 30:
                actions.append(RebalanceAction(
                    asset=asset, action="SELL",
                    current_weight=0, target_weight=0,
                    delta_weight=0, score=score,
                    rationale=f"Score dropped to {score:.1f} — SELL zone.",
                    trigger="SCORE",
                    timestamp=datetime.now(tz=UTC),
                ))
            elif asset not in current_positions and score >= 80:
                actions.append(RebalanceAction(
                    asset=asset, action="BUY",
                    current_weight=0, target_weight=0,
                    delta_weight=0, score=score,
                    rationale=f"New opportunity: score {score:.1f} — STRONG BUY zone.",
                    trigger="SCORE",
                    timestamp=datetime.now(tz=UTC),
                ))

        return actions

    def check_risk_triggers(
        self,
        portfolio_drawdown_pct: float,
        position_losses: dict[str, float],
        drawdown_threshold: float = -10.0,
        position_loss_threshold: float = -15.0,
    ) -> list[RebalanceAction]:
        """Check risk-based triggers."""
        actions = []

        if portfolio_drawdown_pct < drawdown_threshold:
            actions.append(RebalanceAction(
                asset="PORTFOLIO", action="REDUCE",
                current_weight=100, target_weight=50,
                delta_weight=-50, score=0,
                rationale=f"Portfolio drawdown {portfolio_drawdown_pct:.1f}% exceeds {drawdown_threshold}%.",
                trigger="RISK",
                timestamp=datetime.now(tz=UTC),
            ))

        for asset, loss in position_losses.items():
            if loss < position_loss_threshold:
                actions.append(RebalanceAction(
                    asset=asset, action="SELL",
                    current_weight=0, target_weight=0,
                    delta_weight=0, score=0,
                    rationale=f"Position loss {loss:.1f}% exceeds {position_loss_threshold}%.",
                    trigger="RISK",
                    timestamp=datetime.now(tz=UTC),
                ))

        return actions

    def check_regime_change(
        self,
        previous_regime: str | None,
        current_regime: str,
        new_weights: dict[str, float],
        current_weights: dict[str, float],
    ) -> list[RebalanceAction]:
        """Check for macro regime transition."""
        if previous_regime is None or previous_regime == current_regime:
            return []

        logger.info(f"Regime change: {previous_regime} → {current_regime}")
        actions = []
        for asset in set(current_weights.keys()) | set(new_weights.keys()):
            current = current_weights.get(asset, 0)
            target = new_weights.get(asset, 0)
            delta = target - current
            if abs(delta) > 2:  # Meaningful change
                actions.append(RebalanceAction(
                    asset=asset,
                    action="BUY" if delta > 0 else "REDUCE",
                    current_weight=current,
                    target_weight=target,
                    delta_weight=round(delta, 2),
                    score=0,
                    rationale=f"Regime change {previous_regime}→{current_regime}.",
                    trigger="MACRO_REGIME",
                    timestamp=datetime.now(tz=UTC),
                ))
        return actions
