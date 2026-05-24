"""Memory store untuk aiagentgres.

Phase 1: conversation history & search di-handle `sessions.py`. Modul ini
jadi thin adapter biar kode lama (agent.py, skills) tetep bisa pake API
`add_message` / `get_history` / `clear_history` tanpa kebanyakan rewrite.

Long-term memory (fakta tentang user) tetep di tabel `long_term_memory` —
bukan bagian dari sessions, karena scope-nya per-user bukan per-conversation.
"""

from __future__ import annotations

import sqlite3

import sessions  # bootstraps sessions/messages/FTS5 schema on import
from logging_setup import get_logger
from paths import DB_PATH as _DB_PATH

logger = get_logger(__name__)
DB_PATH = str(_DB_PATH)
MAX_HISTORY = 20


def _init_long_term_tables() -> None:
    """Bikin tabel long_term_memory & preferences (kalau belum ada).

    Sessions schema di-init oleh `sessions.init_db()` saat sessions diimport.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS long_term_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, key)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            UNIQUE(user_id, key)
        )
        """
    )
    conn.commit()
    conn.close()


_init_long_term_tables()


def init_db() -> None:
    """Back-compat alias. Modules lama nge-call ini buat ensure schema."""
    _init_long_term_tables()
    sessions.init_db()


def _session_id_for(user_id: int, platform: str = "telegram") -> int:
    """Ambil session aktif untuk user, atau bikin baru."""
    return sessions.get_or_create_active_session(user_id, platform=platform).id


def add_message(user_id: int, role: str, content: str) -> None:
    """Append message ke session aktif user. Sesuai signature lama."""
    session_id = _session_id_for(user_id)
    sessions.append_message(session_id, role, content)
    # Trim: di Hermes, sessions gak auto-trim — kita simpan semua history,
    # tapi `get_history` cuma return MAX_HISTORY terakhir.


def get_history(user_id: int) -> list[dict]:
    """Return history sebagai list of {"role", "content"} (chronological)."""
    session_id = _session_id_for(user_id)
    msgs = sessions.get_messages(session_id, limit=MAX_HISTORY)
    return [{"role": m.role, "content": m.content} for m in msgs]


def clear_history(user_id: int) -> None:
    """Hapus messages di session aktif (tapi session record itu sendiri tetep)."""
    session_id = _session_id_for(user_id)
    sessions.clear_messages(session_id)


def save_memory(user_id: int, key: str, value: str) -> None:
    """Simpan fakta penting tentang user (long-term)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO long_term_memory (user_id, key, value, timestamp)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (user_id, key, value),
    )
    conn.commit()
    conn.close()


def get_memory(user_id: int) -> dict[str, str]:
    """Ambil semua memory tentang user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT key, value FROM long_term_memory WHERE user_id = ?",
        (user_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}


def get_memory_prompt(user_id: int) -> str:
    """Generate system prompt dari long term memory."""
    memories = get_memory(user_id)
    if not memories:
        return ""
    prompt = "Yang lo tau tentang user ini:\n"
    for key, value in memories.items():
        prompt += f"- {key}: {value}\n"
    return prompt


def save_preference(user_id: int, key: str, value: str) -> None:
    """Simpan preferensi user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO preferences (user_id, key, value)
        VALUES (?, ?, ?)
        """,
        (user_id, key, value),
    )
    conn.commit()
    conn.close()


def get_preferences(user_id: int) -> dict[str, str]:
    """Ambil semua preferensi user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT key, value FROM preferences WHERE user_id = ?",
        (user_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}


def delete_memory(user_id: int, key: str) -> None:
    """Hapus memory tertentu."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM long_term_memory WHERE user_id = ? AND key = ?",
        (user_id, key),
    )
    conn.commit()
    conn.close()


def get_all_user_ids() -> list[int]:
    """Daftar user_id unique yang pernah chat. Sekarang lewat sessions store."""
    return sessions.get_all_user_ids()


def get_all_memories_text(user_id: int) -> str:
    """Tampilkan semua long-term memory dalam format teks."""
    memories = get_memory(user_id)
    if not memories:
        return "📭 Belum ada memory tersimpan."
    text = "🧠 Memory yang gua tau tentang lo:\n\n"
    for key, value in memories.items():
        text += f"• {key}: {value}\n"
    return text
