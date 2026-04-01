# Telegram Bot

Commands and proactive alerts via Telegram.

## Scripts
- `bot.py` — Command handler + proactive alert engine
- `message_templates.py` — Formatted alert messages

## Commands
`/portfolio` `/score TICKER` `/screener` `/macro` `/trades` `/pnl` `/rebalance` `/risk` `/posture` `/divergence`

## Proactive Alerts
- BUY signal (score > 65 + risk guard approved)
- SELL signal (score < 30)
- Risk warning (circuit breaker, drawdown, VaR)
- Rebalance suggestion
- Macro regime change
- AI override triggered (with rationale)
- Daily summary at 08:00 + 18:00 CET
- Screener: new asset with score > 80
- Divergence alert

## Confirmation
Asks for inline button confirmation before executing paper trades.
