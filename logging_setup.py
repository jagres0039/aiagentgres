"""Logging config buat aiagentgres.

Ganti `print()` acak-acakan dengan logger berstruktur. Level di-set via
env var `LOG_LEVEL` (default INFO).
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from paths import LOGS_DIR, ensure_runtime_dirs

_CONFIGURED = False


def configure_logging() -> None:
    """Configure root logger. Idempotent — aman dipanggil banyak kali."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    ensure_runtime_dirs()
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")

    root = logging.getLogger()
    root.setLevel(level)

    # Bersihin handler lama (kalau ada) biar gak duplikat.
    for h in list(root.handlers):
        root.removeHandler(h)

    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(formatter)
    root.addHandler(stream)

    log_file = LOGS_DIR / "aiagent.log"
    try:
        file_handler = RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        # Filesystem read-only / no permission — fallback ke stderr only.
        root.warning("Could not create log file at %s — stderr only", log_file)

    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Get a named logger. Auto-configures on first call."""
    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(name)
