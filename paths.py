"""Centralized path resolution for aiagentgres.

Replaces hardcoded `/root/aiagent/` paths. Direktori dasar bisa di-override
lewat env var `JAGRESMAN_HOME` (handy buat development di luar VPS).
"""

import os
from pathlib import Path

_DEFAULT_BASE = Path(__file__).resolve().parent


def _resolve_base() -> Path:
    override = os.getenv("JAGRESMAN_HOME")
    if override:
        return Path(override).resolve()
    return _DEFAULT_BASE


BASE_DIR: Path = _resolve_base()
SKILLS_DIR: Path = BASE_DIR / "skills"
TOOLS_DIR: Path = BASE_DIR / "tools"
OUTPUT_DIR: Path = BASE_DIR / "outputs"
OUTPUT_OFFICE_DIR: Path = BASE_DIR / "output_office"
LOGS_DIR: Path = BASE_DIR / "logs"
TMP_DIR: Path = BASE_DIR / "tmp"
DB_PATH: Path = BASE_DIR / "memory.db"
KNOWLEDGE_FILE: Path = BASE_DIR / "knowledge.txt"
SOUL_FILE: Path = BASE_DIR / "SOUL.md"
AGENTS_FILE: Path = BASE_DIR / "AGENTS.md"
PLAYWRIGHT_COOKIES: Path = BASE_DIR / "playwright_cookies.json"


def ensure_runtime_dirs() -> None:
    """Bikin direktori runtime kalau belum ada. Aman dipanggil berkali-kali."""
    for d in (SKILLS_DIR, OUTPUT_DIR, OUTPUT_OFFICE_DIR, LOGS_DIR, TMP_DIR):
        d.mkdir(parents=True, exist_ok=True)


def as_str(path: Path) -> str:
    """Convenience: dapetin path absolut sebagai string."""
    return str(path)
