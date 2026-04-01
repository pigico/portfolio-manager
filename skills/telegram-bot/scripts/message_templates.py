"""Telegram message templates — formatted alert messages."""

from __future__ import annotations


def format_portfolio_summary(
    total_value: float, cash: float, positions: int,
    daily_pnl_pct: float, drawdown_pct: float, posture: str,
) -> str:
    pnl_emoji = "+" if daily_pnl_pct >= 0 else ""
    return (
        f"*Portfolio Summary*\n"
        f"Total: EUR {total_value:,.2f}\n"
        f"Cash: EUR {cash:,.2f} ({cash/total_value*100:.1f}%)\n"
        f"Positions: {positions}\n"
        f"Daily P&L: {pnl_emoji}{daily_pnl_pct:.2f}%\n"
        f"Max Drawdown: {drawdown_pct:.2f}%\n"
        f"Posture: {posture}"
    )


def format_score(
    asset: str, score: float, decision: str,
    fundamental: float, technical: float, macro: float, sentiment: float,
    ai_override: float = 0,
) -> str:
    bar = score_bar(score)
    parts = [
        f"*{asset}* — Score: {score:.1f}/100 {bar}",
        f"Decision: *{decision}*",
        f"Fundamental: {fundamental:.0f} | Technical: {technical:.0f}",
        f"Macro: {macro:.0f} | Sentiment: {sentiment:.0f}",
    ]
    if ai_override != 0:
        parts.append(f"AI Override: {ai_override:+.0f} pts")
    return "\n".join(parts)


def format_trade_alert(
    action: str, asset: str, price: float, quantity: float,
    score: float, rationale: str,
) -> str:
    emoji = {"BUY": "BUY", "STRONG_BUY": "STRONG BUY", "SELL": "SELL", "REDUCE": "REDUCE"}
    label = emoji.get(action, action)
    return (
        f"*Trade Signal: {label}*\n"
        f"Asset: {asset}\n"
        f"Price: {price:,.2f}\n"
        f"Qty: {quantity:.4f}\n"
        f"Score: {score:.1f}/100\n"
        f"Rationale: {rationale[:150]}"
    )


def format_risk_warning(
    warning_type: str, details: str, severity: str,
) -> str:
    sev_label = {"CRITICAL": "CRITICAL", "WARNING": "WARNING", "INFO": "INFO"}
    label = sev_label.get(severity, severity)
    return (
        f"*Risk Alert [{label}]*\n"
        f"Type: {warning_type}\n"
        f"{details}"
    )


def format_regime_change(old_regime: str, new_regime: str, confidence: float) -> str:
    return (
        f"*Macro Regime Change*\n"
        f"{old_regime} -> {new_regime}\n"
        f"Confidence: {confidence:.0%}\n"
        f"Review portfolio allocation."
    )


def format_daily_summary(
    date: str, total_value: float, daily_pnl_pct: float,
    posture: str, regime: str, top_scores: list[tuple[str, float]],
    active_alerts: int,
) -> str:
    pnl_emoji = "+" if daily_pnl_pct >= 0 else ""
    top_lines = "\n".join(f"  {t}: {s:.0f}" for t, s in top_scores[:5])
    return (
        f"*Daily Summary — {date}*\n\n"
        f"Value: EUR {total_value:,.2f} ({pnl_emoji}{daily_pnl_pct:.2f}%)\n"
        f"Posture: {posture}\n"
        f"Regime: {regime}\n\n"
        f"Top Scores:\n{top_lines}\n\n"
        f"Active Alerts: {active_alerts}"
    )


def format_screener_alert(asset: str, score: float, catalyst: str) -> str:
    return (
        f"*New Opportunity*\n"
        f"Asset: {asset}\n"
        f"Score: {score:.1f}/100\n"
        f"Catalyst: {catalyst}"
    )


def score_bar(score: float, width: int = 10) -> str:
    """Simple text-based score bar."""
    filled = int(score / 100 * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"
