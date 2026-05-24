"""Configuration loaded from environment.

Backed by `.env` di repo root (atau `JAGRESMAN_HOME/.env`). Lihat `.env.example`
buat list lengkap env yang dipakai.
"""

import os

from dotenv import load_dotenv

from paths import BASE_DIR

# Cari .env di BASE_DIR (atau JAGRESMAN_HOME override). Fallback ke cwd biar
# `python -m pytest` di subfolder masih kebaca.
_env_path = BASE_DIR / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)
else:
    load_dotenv()

# --- Telegram ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- Groq ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_KEY_2 = os.getenv("GROQ_API_KEY_2")
GROQ_API_KEY_3 = os.getenv("GROQ_API_KEY_3")
GROQ_API_KEY_4 = os.getenv("GROQ_API_KEY_4")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# --- Tools ---
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY")

# --- Binance ---
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")
BINANCE_TESTNET = os.getenv("BINANCE_TESTNET", "false").lower() == "true"

# --- Agent runtime config ---
AUTO_APPROVE_DANGEROUS = os.getenv("AUTO_APPROVE_DANGEROUS", "false").lower() == "true"
AUTO_APPROVE_SAFE_COMMANDS = os.getenv("AUTO_APPROVE_SAFE_COMMANDS", "true").lower() == "true"
