"""Tests for Sprint 4 — Telegram templates, Scheduler, Dashboard imports."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

# ── Telegram message templates ───────────────────────────
_tg_path = Path(__file__).parent.parent / "skills" / "telegram-bot" / "scripts"
sys.path.insert(0, str(_tg_path))

from message_templates import (
    format_daily_summary,
    format_portfolio_summary,
    format_regime_change,
    format_risk_warning,
    format_score,
    format_screener_alert,
    format_trade_alert,
    score_bar,
)

# ── Scheduler ────────────────────────────────────────────
_sc_path = Path(__file__).parent.parent / "scheduler"
sys.path.insert(0, str(_sc_path))

from jobs import JobScheduler, SchedulerConfig


# ==============================================================
# Message Templates
# ==============================================================

class TestMessageTemplates:
    def test_portfolio_summary(self):
        msg = format_portfolio_summary(
            total_value=105000, cash=42000, positions=4,
            daily_pnl_pct=1.5, drawdown_pct=-3.0, posture="SELECTIVE_ENTRY",
        )
        assert "105,000" in msg
        assert "SELECTIVE_ENTRY" in msg
        assert "+1.50%" in msg

    def test_score_format(self):
        msg = format_score("AAPL", 72, "BUY",
                           fundamental=68, technical=75, macro=70, sentiment=65)
        assert "AAPL" in msg
        assert "72.0" in msg
        assert "BUY" in msg

    def test_score_with_ai_override(self):
        msg = format_score("AAPL", 82, "STRONG_BUY",
                           fundamental=70, technical=75, macro=70, sentiment=65,
                           ai_override=12)
        assert "+12" in msg

    def test_trade_alert(self):
        msg = format_trade_alert("BUY", "BTC", 62400, 0.5, 78, "Strong momentum")
        assert "BTC" in msg
        assert "62,400" in msg

    def test_risk_warning(self):
        msg = format_risk_warning("CIRCUIT_BREAKER", "3 consecutive losses", "WARNING")
        assert "WARNING" in msg
        assert "CIRCUIT_BREAKER" in msg

    def test_regime_change(self):
        msg = format_regime_change("Goldilocks", "Stagflation", 0.85)
        assert "Goldilocks" in msg
        assert "Stagflation" in msg

    def test_daily_summary(self):
        msg = format_daily_summary(
            "2025-03-28", 105000, 1.5, "SELECTIVE_ENTRY", "Reflation",
            [("NVDA", 88), ("BTC", 78), ("AAPL", 72)], 2,
        )
        assert "2025-03-28" in msg
        assert "NVDA" in msg

    def test_screener_alert(self):
        msg = format_screener_alert("SOL", 85, "DeFi TVL surge")
        assert "SOL" in msg
        assert "85.0" in msg

    def test_score_bar(self):
        bar = score_bar(75)
        assert len(bar) == 12  # [ + 10 chars + ]
        assert "#" in bar
        assert "-" in bar

    def test_score_bar_empty(self):
        bar = score_bar(0)
        assert bar == "[----------]"

    def test_score_bar_full(self):
        bar = score_bar(100)
        assert bar == "[##########]"


# ==============================================================
# Scheduler
# ==============================================================

class TestScheduler:
    def test_scheduler_config(self):
        assert SchedulerConfig.TECHNICAL_INTERVAL_MIN == 5
        assert SchedulerConfig.SENTIMENT_INTERVAL_MIN == 15
        assert SchedulerConfig.COMPOSITE_INTERVAL_MIN == 60

    def test_scheduler_init(self):
        s = JobScheduler()
        assert not s._running
        assert len(s._tasks) == 0

    def test_scheduler_status(self):
        s = JobScheduler()
        status = s.get_status()
        assert status["running"] is False
        assert "technical" in status["schedule"]
        assert "macro" in status["schedule"]

    @pytest.mark.asyncio
    async def test_scheduler_start_stop(self):
        s = JobScheduler()
        # Start in background
        task = asyncio.create_task(s.start())
        await asyncio.sleep(0.1)
        assert s._running
        # Stop
        await s.stop()
        assert not s._running
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


# ==============================================================
# Telegram Bot (structural test — no actual API calls)
# ==============================================================

class TestTelegramBot:
    def test_bot_init_no_token(self):
        from bot import TelegramBot
        bot = TelegramBot()
        assert bot._token == ""
        assert bot._app is None

    def test_bot_get_app_no_token(self):
        from bot import TelegramBot
        bot = TelegramBot()
        app = bot._get_app()
        assert app is None  # No token = disabled


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
