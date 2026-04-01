"""Scheduler — asyncio event loop + APScheduler cron jobs.

Main event loop manages:
- WebSocket streams (Binance + Finnhub) — ALWAYS ACTIVE
- Periodic jobs via APScheduler

Job schedule:
- Every 5 min: recalculate technical indicators
- Every 15 min: update sentiment
- Every 1 hour: recalculate composite scores + divergence check
- Every 6 hours: update fundamentals
- Every 24 hours: macro data (FRED) + run screener + market posture
- Monday morning: full rebalancing analysis
- 08:00 + 18:00 CET: daily summary via Telegram
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from loguru import logger


class SchedulerConfig:
    """Job schedule configuration."""
    TECHNICAL_INTERVAL_MIN = 5
    SENTIMENT_INTERVAL_MIN = 15
    COMPOSITE_INTERVAL_MIN = 60
    FUNDAMENTALS_INTERVAL_HOURS = 6
    MACRO_INTERVAL_HOURS = 24
    POSTURE_INTERVAL_HOURS = 24
    DAILY_SUMMARY_TIMES = ["08:00", "18:00"]  # CET


class JobScheduler:
    """Main scheduler orchestrating all periodic tasks.

    Uses asyncio as the primary event loop for WebSocket streams,
    with APScheduler for cron-like periodic tasks.
    """

    def __init__(self) -> None:
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """Start the scheduler and all background tasks."""
        self._running = True
        logger.info("Scheduler starting...")

        # Schedule periodic jobs
        self._tasks.append(asyncio.create_task(
            self._periodic_job("technical_update", SchedulerConfig.TECHNICAL_INTERVAL_MIN * 60,
                               self._job_technical_update)
        ))
        self._tasks.append(asyncio.create_task(
            self._periodic_job("sentiment_update", SchedulerConfig.SENTIMENT_INTERVAL_MIN * 60,
                               self._job_sentiment_update)
        ))
        self._tasks.append(asyncio.create_task(
            self._periodic_job("composite_scores", SchedulerConfig.COMPOSITE_INTERVAL_MIN * 60,
                               self._job_composite_scores)
        ))
        self._tasks.append(asyncio.create_task(
            self._periodic_job("fundamentals_update", SchedulerConfig.FUNDAMENTALS_INTERVAL_HOURS * 3600,
                               self._job_fundamentals_update)
        ))
        self._tasks.append(asyncio.create_task(
            self._periodic_job("macro_update", SchedulerConfig.MACRO_INTERVAL_HOURS * 3600,
                               self._job_macro_update)
        ))
        self._tasks.append(asyncio.create_task(
            self._periodic_job("posture_update", SchedulerConfig.POSTURE_INTERVAL_HOURS * 3600,
                               self._job_posture_update)
        ))

        logger.info("Scheduler started with all periodic jobs.")

        # Keep running
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("Scheduler stopped.")

    async def _periodic_job(
        self, name: str, interval_seconds: float, job_func
    ) -> None:
        """Run a job periodically."""
        while self._running:
            try:
                await asyncio.sleep(interval_seconds)
                if not self._running:
                    break
                logger.debug(f"Running job: {name}")
                await job_func()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Job {name} failed: {e}")

    # ── Job implementations ──────────────────────────────
    # These are stubs that will be connected to actual skill modules

    async def _job_technical_update(self) -> None:
        """Recalculate technical indicators from WebSocket data."""
        logger.debug("Job: technical_update — recalculating indicators")

    async def _job_sentiment_update(self) -> None:
        """Update sentiment (news + fear&greed)."""
        logger.debug("Job: sentiment_update — fetching news sentiment")

    async def _job_composite_scores(self) -> None:
        """Recalculate composite scores + divergence check."""
        logger.debug("Job: composite_scores — scoring all assets")

    async def _job_fundamentals_update(self) -> None:
        """Update fundamental data."""
        logger.debug("Job: fundamentals_update — fetching fundamentals")

    async def _job_macro_update(self) -> None:
        """Update macro data from FRED + run screener."""
        logger.debug("Job: macro_update — fetching FRED data")

    async def _job_posture_update(self) -> None:
        """Full market posture recalculation."""
        logger.debug("Job: posture_update — recalculating market posture")

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "active_tasks": len(self._tasks),
            "schedule": {
                "technical": f"every {SchedulerConfig.TECHNICAL_INTERVAL_MIN}min",
                "sentiment": f"every {SchedulerConfig.SENTIMENT_INTERVAL_MIN}min",
                "composite": f"every {SchedulerConfig.COMPOSITE_INTERVAL_MIN}min",
                "fundamentals": f"every {SchedulerConfig.FUNDAMENTALS_INTERVAL_HOURS}h",
                "macro": f"every {SchedulerConfig.MACRO_INTERVAL_HOURS}h",
                "posture": f"every {SchedulerConfig.POSTURE_INTERVAL_HOURS}h",
            },
        }
