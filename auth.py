"""Allow-list + dangerous-command approval helpers.

Phase 0 security fix. Sebelumnya `handle_message` gak filter user_id, jadi
siapa aja yang DM bot bisa trigger LLM dan kalau LLM nge-call `EXECUTE_BASH`,
shell command jalan di VPS. Modul ini:

  1. `is_authorized(user_id)` — cek apakah user di allow-list.
  2. `classify_command(cmd)` — kategorikan command jadi `safe`/`moderate`/`dangerous`.
  3. `requires_approval(cmd)` — boolean wrapper, dipakai handler.
"""

from __future__ import annotations

import os
import re
import shlex
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from threading import Lock

from logging_setup import get_logger

logger = get_logger(__name__)


def _parse_owner_ids() -> frozenset[int]:
    """Parse `OWNER_TELEGRAM_IDS` (comma-separated) + legacy `OWNER_TELEGRAM_ID`."""
    raw_multi = os.getenv("OWNER_TELEGRAM_IDS", "")
    raw_single = os.getenv("OWNER_TELEGRAM_ID", "")
    out: set[int] = set()
    for raw in (raw_multi, raw_single):
        if not raw:
            continue
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                out.add(int(part))
            except ValueError:
                logger.warning("Ignoring invalid OWNER_TELEGRAM_ID%s value: %r", "S" if raw is raw_multi else "", part)
    return frozenset(out)


# Cache di module load — telegram-bot restart tiap deploy, OK.
OWNER_IDS: frozenset[int] = _parse_owner_ids()


def is_authorized(user_id: int | None) -> bool:
    """Apakah user_id ada di allow-list."""
    if user_id is None:
        return False
    if not OWNER_IDS:
        logger.warning(
            "OWNER_TELEGRAM_IDS kosong — DEFAULT-DENY semua user. "
            "Set OWNER_TELEGRAM_IDS=<your_id> di .env biar bisa pakai bot."
        )
        return False
    return int(user_id) in OWNER_IDS


class CommandRisk(str, Enum):
    SAFE = "safe"
    MODERATE = "moderate"
    DANGEROUS = "dangerous"


@dataclass(frozen=True)
class CommandClassification:
    risk: CommandRisk
    reason: str


# Whitelist read-only commands yang aman auto-run kalau AUTO_APPROVE_SAFE_COMMANDS=true.
_SAFE_BIN = frozenset(
    {
        "ls",
        "pwd",
        "cd",
        "echo",
        "cat",
        "head",
        "tail",
        "wc",
        "grep",
        "find",
        "tree",
        "stat",
        "file",
        "du",
        "df",
        "free",
        "uptime",
        "who",
        "id",
        "whoami",
        "hostname",
        "uname",
        "date",
        "cal",
        "ps",
        "top",
        "htop",
        "nproc",
        "lscpu",
        "lsblk",
        "lsmod",
        "lsusb",
        "lspci",
        "ip",
        "ifconfig",
        "ping",
        "dig",
        "nslookup",
        "curl",
        "wget",
        "git",
        "python",
        "python3",
        "python3.11",
        "pip",
        "pip3",
        "node",
        "npm",
        "which",
        "type",
        "history",
        "env",
        "printenv",
    }
)

# Token / pattern yang langsung naikin ke DANGEROUS.
_DANGEROUS_PATTERNS = (
    re.compile(r"\brm\b.*-[rRf]"),  # rm -rf, rm -r, rm -f
    re.compile(r"\bdd\b"),
    re.compile(r"\bmkfs"),
    re.compile(r":\(\)\s*\{"),  # fork bomb
    re.compile(r"/dev/(tcp|udp)/"),  # bash reverse shell
    re.compile(r"\bnc\b\s+.*-[el]"),  # netcat listener / exec
    re.compile(r"\bshutdown\b"),
    re.compile(r"\breboot\b"),
    re.compile(r"\bhalt\b"),
    re.compile(r"\bpoweroff\b"),
    re.compile(r"\bchmod\b\s+777"),
    re.compile(r"\bchown\b\s+-R"),
    re.compile(r"\bsudo\b"),
    re.compile(r"\bsu\b\s"),
    re.compile(r"\b(curl|wget)\b.*\|\s*(bash|sh|zsh)"),  # curl | bash
    re.compile(r"\beval\b\s+.*\$\("),
    re.compile(r"\bcrontab\b"),
    re.compile(r"\bsystemctl\b.*(disable|mask|stop)"),
    re.compile(r">\s*/dev/sd"),
    re.compile(r"\biptables\b"),
    re.compile(r"\bufw\b\s+(disable|delete)"),
    re.compile(r"\b(passwd|useradd|userdel|groupadd|groupdel|adduser|deluser)\b"),
    re.compile(r"\b(mv|cp)\b\s+.*\s+/(etc|bin|sbin|usr|boot|root|home)(/|\s|$)"),
)

_MODERATE_PATTERNS = (
    re.compile(r"\bgit\b\s+(push|reset|clean)"),
    re.compile(r"\bpip\b\s+install"),
    re.compile(r"\bnpm\b\s+install"),
    re.compile(r"\bdocker\b"),
    re.compile(r"\bkill\b"),
    re.compile(r"\bpkill\b"),
    re.compile(r"\bkillall\b"),
    re.compile(r"\bsystemctl\b"),
    re.compile(r"\bservice\b"),
    re.compile(r"\bmv\b"),
    re.compile(r"\brm\b"),
    re.compile(r">"),
    re.compile(r">>"),
    re.compile(r"\bcp\b\s+-[rR]"),
)


def classify_command(cmd: str) -> CommandClassification:
    """Klasifikasi 1 command shell jadi safe/moderate/dangerous."""
    cmd = cmd.strip()
    if not cmd:
        return CommandClassification(CommandRisk.SAFE, "empty command")

    for pat in _DANGEROUS_PATTERNS:
        m = pat.search(cmd)
        if m:
            return CommandClassification(CommandRisk.DANGEROUS, f"matched dangerous pattern: {m.group(0)}")

    for pat in _MODERATE_PATTERNS:
        m = pat.search(cmd)
        if m:
            return CommandClassification(CommandRisk.MODERATE, f"matched moderate pattern: {m.group(0)}")

    # Lihat binary pertama. Kalau bukan di safelist, anggep moderate.
    try:
        tokens = shlex.split(cmd, posix=True)
    except ValueError:
        return CommandClassification(CommandRisk.MODERATE, "unparseable command")

    if not tokens:
        return CommandClassification(CommandRisk.SAFE, "empty after parse")

    first = tokens[0].lstrip("./")
    base = os.path.basename(first)
    if base in _SAFE_BIN:
        return CommandClassification(CommandRisk.SAFE, f"safelist: {base}")
    return CommandClassification(CommandRisk.MODERATE, f"unknown binary: {base}")


def requires_approval(cmd: str) -> bool:
    """True kalau command harus minta approval user sebelum eksekusi."""
    if os.getenv("AUTO_APPROVE_DANGEROUS", "false").lower() == "true":
        return False
    classification = classify_command(cmd)
    if classification.risk is CommandRisk.DANGEROUS:
        return True
    if classification.risk is CommandRisk.MODERATE:
        return True
    auto_safe = os.getenv("AUTO_APPROVE_SAFE_COMMANDS", "true").lower() == "true"
    return not auto_safe


# =============================================================
# Pending-approval registry — in-memory store untuk command yang nunggu
# konfirmasi via tombol Telegram. Bot single-instance, jadi dict in-memory
# udah cukup buat Phase 0; nanti di Phase 1 bisa di-persist ke SQLite.
# =============================================================

_PENDING_LOCK = Lock()
_PENDING: dict[str, dict] = {}
PENDING_TTL_SECONDS = 600  # 10 menit — kalau lewat ini, approval di-expire


def record_pending_command(user_id: int, cmd: str) -> str:
    """Simpan command yang nunggu approval, return approval_id (hex)."""
    approval_id = uuid.uuid4().hex[:12]
    classification = classify_command(cmd)
    with _PENDING_LOCK:
        _prune_expired_locked()
        _PENDING[approval_id] = {
            "user_id": int(user_id),
            "cmd": cmd,
            "risk": classification.risk.value,
            "reason": classification.reason,
            "created_at": time.time(),
        }
    return approval_id


def consume_pending_command(approval_id: str, user_id: int) -> dict | None:
    """Ambil & hapus pending approval. Cek user_id biar gak ada cross-user attack.

    Kalau user_id mismatch, record TIDAK di-pop biar owner asli masih bisa
    approve. Cuma pop kalau verifikasi sukses.
    """
    with _PENDING_LOCK:
        _prune_expired_locked()
        record = _PENDING.get(approval_id)
        if record is None:
            return None
        if record["user_id"] != int(user_id):
            logger.warning(
                "Approval mismatch — user_id=%s mencoba approve approval_id=%s yang milik user_id=%s",
                user_id,
                approval_id,
                record["user_id"],
            )
            return None
        # Verified: pop sekarang.
        return _PENDING.pop(approval_id)


def cancel_pending_command(approval_id: str, user_id: int) -> bool:
    """Drop pending approval tanpa eksekusi. Return True kalau berhasil di-cancel."""
    return consume_pending_command(approval_id, user_id) is not None


def _prune_expired_locked() -> None:
    cutoff = time.time() - PENDING_TTL_SECONDS
    expired = [aid for aid, rec in _PENDING.items() if rec["created_at"] < cutoff]
    for aid in expired:
        _PENDING.pop(aid, None)


def pending_count() -> int:
    """Visible for testing."""
    with _PENDING_LOCK:
        _prune_expired_locked()
        return len(_PENDING)
