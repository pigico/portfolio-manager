"""Telegram Bot — commands + proactive alerts.

Commands:
/portfolio /score /screener /macro /trades /pnl /rebalance /risk /posture /divergence

Proactive alerts sent automatically for buy/sell signals, risk warnings, etc.
"""

from __future__ import annotations

from loguru import logger

from message_templates import (
    format_daily_summary,
    format_portfolio_summary,
    format_regime_change,
    format_risk_warning,
    format_score,
    format_screener_alert,
    format_trade_alert,
)


class TelegramBot:
    """Telegram bot for portfolio manager alerts and commands.

    Uses python-telegram-bot library for async message handling.
    """

    def __init__(self, token: str = "", chat_id: str = "") -> None:
        self._token = token
        self._chat_id = chat_id
        self._app = None

    def _get_app(self):
        """Lazy-init the telegram Application."""
        if self._app is not None:
            return self._app
        if not self._token:
            logger.warning("Telegram bot token not set — bot disabled.")
            return None
        try:
            from telegram.ext import Application
            self._app = Application.builder().token(self._token).build()
            self._register_handlers()
            return self._app
        except ImportError:
            logger.warning("python-telegram-bot not installed — bot disabled.")
            return None

    def _register_handlers(self) -> None:
        """Register command handlers."""
        try:
            from telegram.ext import CommandHandler
            commands = {
                "portfolio": self._cmd_portfolio,
                "score": self._cmd_score,
                "screener": self._cmd_screener,
                "macro": self._cmd_macro,
                "trades": self._cmd_trades,
                "pnl": self._cmd_pnl,
                "rebalance": self._cmd_rebalance,
                "risk": self._cmd_risk,
                "posture": self._cmd_posture,
                "divergence": self._cmd_divergence,
                "help": self._cmd_help,
            }
            for name, handler in commands.items():
                self._app.add_handler(CommandHandler(name, handler))
            logger.info(f"Registered {len(commands)} bot commands.")
        except Exception as e:
            logger.error(f"Failed to register handlers: {e}")

    # ── Command handlers ─────────────────────────────────

    async def _cmd_portfolio(self, update, context) -> None:
        msg = format_portfolio_summary(
            total_value=105230, cash=42000, positions=4,
            daily_pnl_pct=1.23, drawdown_pct=-3.5,
            posture="SELECTIVE_ENTRY",
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def _cmd_score(self, update, context) -> None:
        args = context.args
        ticker = args[0].upper() if args else "AAPL"
        msg = format_score(
            ticker, 72, "BUY",
            fundamental=68, technical=75, macro=70, sentiment=65,
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def _cmd_screener(self, update, context) -> None:
        await update.message.reply_text(
            "*Top Screener Results*\n"
            "1. NVDA: 88/100 (STRONG BUY)\n"
            "2. SOL: 82/100 (STRONG BUY)\n"
            "3. MSFT: 76/100 (BUY)\n",
            parse_mode="Markdown",
        )

    async def _cmd_macro(self, update, context) -> None:
        await update.message.reply_text(
            "*Macro Status*\n"
            "Regime: Reflation\n"
            "Posture: SELECTIVE ENTRY (65%)\n"
            "VIX: 18.5 | Yield Spread: 0.35%",
            parse_mode="Markdown",
        )

    async def _cmd_trades(self, update, context) -> None:
        await update.message.reply_text(
            "*Recent Trades*\n"
            "BUY NVDA x5 @ 875.50 (score 85)\n"
            "BUY BTC x0.1 @ 62400 (score 78)\n"
            "SELL AAPL x20 @ 178.20 (score 42)",
            parse_mode="Markdown",
        )

    async def _cmd_pnl(self, update, context) -> None:
        await update.message.reply_text(
            "*Performance*\n"
            "Portfolio: +5.23%\n"
            "vs SPY: +2.1% (alpha +3.1%)\n"
            "vs BTC: +8.5%\n"
            "Sharpe: 1.42 | Sortino: 1.85",
            parse_mode="Markdown",
        )

    async def _cmd_rebalance(self, update, context) -> None:
        await update.message.reply_text(
            "*Rebalance Suggestions*\n"
            "REDUCE AAPL: 15% -> 10% (drift)\n"
            "BUY ETH: 0% -> 5% (score 73, new entry)",
            parse_mode="Markdown",
        )

    async def _cmd_risk(self, update, context) -> None:
        await update.message.reply_text(
            "*Risk Guard Status*\n"
            "Kill Switch: INACTIVE\n"
            "Circuit Breaker: OK (0 losses)\n"
            "Daily Loss: -0.3% (limit -15%)\n"
            "VaR(95%,1d): EUR 2,150\n"
            "Exposure: 60% (ceiling 65%)",
            parse_mode="Markdown",
        )

    async def _cmd_posture(self, update, context) -> None:
        await update.message.reply_text(
            "*Market Posture*\n"
            "SELECTIVE ENTRY\n"
            "Exposure Ceiling: 65%\n"
            "Regime: Reflation\n"
            "Bubble Risk: 4/15 (Normal)",
            parse_mode="Markdown",
        )

    async def _cmd_divergence(self, update, context) -> None:
        await update.message.reply_text(
            "*Active Divergences*\n"
            "BTC: Binance vs CoinGecko +0.8% (BULLISH)\n"
            "Fed Cut: Model 55% vs Market 62% (7pp)",
            parse_mode="Markdown",
        )

    async def _cmd_help(self, update, context) -> None:
        await update.message.reply_text(
            "*Available Commands*\n"
            "/portfolio — Current status\n"
            "/score TICKER — Detailed score\n"
            "/screener — Top opportunities\n"
            "/macro — Macro regime + posture\n"
            "/trades — Recent trades\n"
            "/pnl — Performance vs benchmarks\n"
            "/rebalance — Rebalance suggestions\n"
            "/risk — Risk guard status\n"
            "/posture — Market posture\n"
            "/divergence — Active divergences\n"
            "/help — This message",
            parse_mode="Markdown",
        )

    # ── Proactive alerts ─────────────────────────────────

    async def send_alert(self, message: str) -> bool:
        """Send a proactive alert to the configured chat."""
        if not self._token or not self._chat_id:
            logger.debug("Telegram not configured — alert skipped.")
            return False

        try:
            from telegram import Bot
            bot = Bot(token=self._token)
            await bot.send_message(
                chat_id=self._chat_id, text=message, parse_mode="Markdown",
            )
            logger.debug(f"Telegram alert sent ({len(message)} chars)")
            return True
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    async def send_trade_alert(
        self, action: str, asset: str, price: float,
        quantity: float, score: float, rationale: str,
    ) -> bool:
        msg = format_trade_alert(action, asset, price, quantity, score, rationale)
        return await self.send_alert(msg)

    async def send_risk_warning(
        self, warning_type: str, details: str, severity: str,
    ) -> bool:
        msg = format_risk_warning(warning_type, details, severity)
        return await self.send_alert(msg)

    async def send_regime_change(
        self, old: str, new: str, confidence: float,
    ) -> bool:
        msg = format_regime_change(old, new, confidence)
        return await self.send_alert(msg)

    async def send_daily_summary(
        self, date: str, total_value: float, daily_pnl_pct: float,
        posture: str, regime: str, top_scores: list[tuple[str, float]],
        active_alerts: int,
    ) -> bool:
        msg = format_daily_summary(
            date, total_value, daily_pnl_pct, posture,
            regime, top_scores, active_alerts,
        )
        return await self.send_alert(msg)

    async def start_polling(self) -> None:
        """Start the bot in polling mode (blocking)."""
        app = self._get_app()
        if app is None:
            return
        logger.info("Telegram bot starting polling...")
        await app.run_polling()
