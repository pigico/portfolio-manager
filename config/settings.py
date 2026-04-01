"""Global settings loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")


# --- API Keys ---
ALPHA_VANTAGE_API_KEY: str = os.getenv("ALPHA_VANTAGE_API_KEY", "")
FMP_API_KEY: str = os.getenv("FMP_API_KEY", "")
FINNHUB_API_KEY: str = os.getenv("FINNHUB_API_KEY", "")
FRED_API_KEY: str = os.getenv("FRED_API_KEY", "")
TWELVE_DATA_API_KEY: str = os.getenv("TWELVE_DATA_API_KEY", "")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# --- Telegram ---
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# --- Database ---
DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'data' / 'portfolio.db'}")
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# --- Dashboard ---
DASHBOARD_PORT: int = int(os.getenv("DASHBOARD_PORT", "8501"))

# --- Logging ---
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# --- Paths ---
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
KILL_SWITCH_FILE = DATA_DIR / ".kill_switch_active"
