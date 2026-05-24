"""Session store dengan FTS5 full-text search.

Inspired by Hermes Agent's session model. Tiap percakapan = satu session,
session di-scope ke (platform, platform_user_id), bisa ada banyak session
aktif per user (e.g. multi-thread Telegram, channel Discord beda, dll).

Schema:
- `sessions`: metadata (uid, user, platform, title, summary, timestamps)
- `messages`: full conversation log, dengan metadata JSON
- `messages_fts`: FTS5 virtual table untuk pencarian full-text

Migration: kalau ada tabel `conversations` (schema lama dari Phase 0),
rows-nya di-import ke sessions otomatis pas init. Tabel lamanya dibiarin
(read-only) biar gak destructive — bisa di-drop manual nanti.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import threading
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from logging_setup import get_logger
from paths import DB_PATH

logger = get_logger(__name__)

_DB_PATH_STR = str(DB_PATH)
_INIT_LOCK = threading.Lock()
_INITIALIZED = False


@dataclass
class Session:
    """Public-facing session record."""

    id: int
    session_uid: str
    user_id: int
    platform: str
    platform_user_id: str
    profile: str | None
    title: str | None
    summary: str | None
    created_at: str
    updated_at: str
    closed: bool


@dataclass
class Message:
    """A single message in a session."""

    id: int
    session_id: int
    role: str  # "user" | "assistant" | "system" | "tool"
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""


def _generate_uid() -> str:
    return "s_" + secrets.token_hex(6)


@contextmanager
def _connect():
    conn = sqlite3.connect(_DB_PATH_STR, timeout=10.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Idempotent: bikin schema kalau belum ada, migrate dari schema lama kalau perlu."""
    global _INITIALIZED
    with _INIT_LOCK:
        if _INITIALIZED:
            return
        with _connect() as conn:
            _create_schema(conn)
            _migrate_legacy_conversations(conn)
        _INITIALIZED = True


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_uid TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            platform TEXT NOT NULL DEFAULT 'telegram',
            platform_user_id TEXT NOT NULL,
            profile TEXT,
            title TEXT,
            summary TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            closed INTEGER NOT NULL DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, closed);
        CREATE INDEX IF NOT EXISTS idx_sessions_platform ON sessions(platform, platform_user_id);

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata TEXT,
            timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);

        CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
            content,
            content='messages',
            content_rowid='id',
            tokenize='unicode61'
        );

        CREATE TRIGGER IF NOT EXISTS messages_fts_ai AFTER INSERT ON messages BEGIN
            INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
        END;
        CREATE TRIGGER IF NOT EXISTS messages_fts_ad AFTER DELETE ON messages BEGIN
            INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
        END;
        CREATE TRIGGER IF NOT EXISTS messages_fts_au AFTER UPDATE ON messages BEGIN
            INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
            INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
        END;
        """
    )


def _migrate_legacy_conversations(conn: sqlite3.Connection) -> None:
    """Migrate rows dari tabel `conversations` (Phase 0 schema) ke sessions/messages.

    Strategy: tiap (user_id) di legacy table -> 1 session di sessions table
    dengan platform='telegram'. Semua message di-append ke session itu.
    Cuma jalan SEKALI — kalau tabel sessions udah ada datanya untuk user yang
    sama, skip migration.
    """
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'"
    )
    if cur.fetchone() is None:
        return  # tabel lama gak ada, fresh install

    # Cek apakah migration udah dijalankan (any session for any legacy user already exists?)
    legacy_users = [
        row["user_id"]
        for row in conn.execute("SELECT DISTINCT user_id FROM conversations")
    ]
    if not legacy_users:
        return

    migrated_count = 0
    for user_id in legacy_users:
        # Skip user yg udah punya session telegram (already migrated)
        existing = conn.execute(
            "SELECT 1 FROM sessions WHERE user_id = ? AND platform = 'telegram' LIMIT 1",
            (user_id,),
        ).fetchone()
        if existing:
            continue

        session_uid = _generate_uid()
        cur = conn.execute(
            """
            INSERT INTO sessions (session_uid, user_id, platform, platform_user_id, title)
            VALUES (?, ?, 'telegram', ?, 'Migrated from Phase 0')
            """,
            (session_uid, user_id, str(user_id)),
        )
        session_id = cur.lastrowid

        rows = conn.execute(
            """
            SELECT role, content, timestamp FROM conversations
            WHERE user_id = ? ORDER BY id ASC
            """,
            (user_id,),
        ).fetchall()
        for row in rows:
            conn.execute(
                """
                INSERT INTO messages (session_id, role, content, metadata, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, row["role"], row["content"], "{}", row["timestamp"]),
            )
        migrated_count += 1

    if migrated_count:
        logger.info(
            "Migrated %s legacy users dari `conversations` table ke sessions store.",
            migrated_count,
        )


# Init di import-time biar caller gak perlu ingat.
init_db()


def _row_to_session(row: sqlite3.Row) -> Session:
    return Session(
        id=row["id"],
        session_uid=row["session_uid"],
        user_id=row["user_id"],
        platform=row["platform"],
        platform_user_id=row["platform_user_id"],
        profile=row["profile"],
        title=row["title"],
        summary=row["summary"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        closed=bool(row["closed"]),
    )


def _row_to_message(row: sqlite3.Row) -> Message:
    metadata = {}
    if row["metadata"]:
        try:
            metadata = json.loads(row["metadata"])
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in messages.metadata id=%s", row["id"])
    return Message(
        id=row["id"],
        session_id=row["session_id"],
        role=row["role"],
        content=row["content"],
        metadata=metadata,
        timestamp=row["timestamp"],
    )


def get_or_create_active_session(
    user_id: int,
    platform: str = "telegram",
    platform_user_id: str | None = None,
    profile: str | None = None,
) -> Session:
    """Ambil session aktif terakhir, atau bikin baru kalau belum ada/sudah closed."""
    platform_user_id = platform_user_id or str(user_id)
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM sessions
            WHERE user_id = ? AND platform = ? AND platform_user_id = ? AND closed = 0
            ORDER BY id DESC LIMIT 1
            """,
            (user_id, platform, platform_user_id),
        ).fetchone()
        if row is not None:
            return _row_to_session(row)

        session_uid = _generate_uid()
        cur = conn.execute(
            """
            INSERT INTO sessions (session_uid, user_id, platform, platform_user_id, profile)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_uid, user_id, platform, platform_user_id, profile),
        )
        new_id = cur.lastrowid
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (new_id,)).fetchone()
        logger.info(
            "Created new session uid=%s user_id=%s platform=%s",
            session_uid,
            user_id,
            platform,
        )
        return _row_to_session(row)


def get_session_by_uid(session_uid: str) -> Session | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_uid = ?", (session_uid,)
        ).fetchone()
    return _row_to_session(row) if row else None


def list_sessions(user_id: int, include_closed: bool = False, limit: int = 50) -> list[Session]:
    with _connect() as conn:
        if include_closed:
            sql = "SELECT * FROM sessions WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?"
            rows = conn.execute(sql, (user_id, limit)).fetchall()
        else:
            sql = (
                "SELECT * FROM sessions WHERE user_id = ? AND closed = 0 "
                "ORDER BY updated_at DESC LIMIT ?"
            )
            rows = conn.execute(sql, (user_id, limit)).fetchall()
    return [_row_to_session(r) for r in rows]


def close_session(session_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET closed = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (session_id,),
        )


def update_session_metadata(
    session_id: int,
    *,
    title: str | None = None,
    summary: str | None = None,
    profile: str | None = None,
) -> None:
    fields: list[str] = []
    params: list[Any] = []
    if title is not None:
        fields.append("title = ?")
        params.append(title)
    if summary is not None:
        fields.append("summary = ?")
        params.append(summary)
    if profile is not None:
        fields.append("profile = ?")
        params.append(profile)
    if not fields:
        return
    fields.append("updated_at = CURRENT_TIMESTAMP")
    params.append(session_id)
    with _connect() as conn:
        conn.execute(
            f"UPDATE sessions SET {', '.join(fields)} WHERE id = ?",
            params,
        )


def append_message(
    session_id: int,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> Message:
    """Append a message ke session. Update session.updated_at otomatis."""
    metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO messages (session_id, role, content, metadata)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, role, content, metadata_json),
        )
        new_id = cur.lastrowid
        conn.execute(
            "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (session_id,),
        )
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (new_id,)).fetchone()
    return _row_to_message(row)


def get_messages(session_id: int, limit: int | None = None) -> list[Message]:
    """Ambil messages dalam urutan chronological (oldest first).

    Kalau limit di-set, ambil N terbaru terus reverse jadi chronological.
    """
    with _connect() as conn:
        if limit is None:
            rows = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM (
                    SELECT * FROM messages WHERE session_id = ?
                    ORDER BY id DESC LIMIT ?
                ) ORDER BY id ASC
                """,
                (session_id, limit),
            ).fetchall()
    return [_row_to_message(r) for r in rows]


def clear_messages(session_id: int) -> int:
    """Hapus semua message di session. Return count yang dihapus."""
    with _connect() as conn:
        cur = conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        deleted = cur.rowcount
        conn.execute(
            "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (session_id,),
        )
    return deleted


@dataclass
class SearchHit:
    message: Message
    session: Session
    snippet: str


def search_messages(
    query: str,
    user_id: int | None = None,
    limit: int = 20,
) -> list[SearchHit]:
    """Full-text search lewat FTS5. Optionally filter by user.

    `query` pakai FTS5 syntax (e.g. "kata1 kata2", "kata1 OR kata2", "kata*").
    Untuk casual user, kita auto-escape: kalau query gak ada operator FTS,
    kita treat sebagai prefix-match phrase.
    """
    if not query.strip():
        return []
    safe_query = _to_fts_query(query)

    sql = """
        SELECT m.*, s.session_uid, s.user_id AS s_user_id, s.platform, s.platform_user_id,
               s.profile, s.title, s.summary, s.created_at AS s_created_at,
               s.updated_at AS s_updated_at, s.closed,
               snippet(messages_fts, 0, '<b>', '</b>', '…', 16) AS snippet
        FROM messages_fts
        JOIN messages m ON m.id = messages_fts.rowid
        JOIN sessions s ON s.id = m.session_id
        WHERE messages_fts MATCH ?
    """
    params: list[Any] = [safe_query]
    if user_id is not None:
        sql += " AND s.user_id = ?"
        params.append(user_id)
    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)

    with _connect() as conn:
        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            logger.warning("FTS5 query failed (%s): %r — falling back to LIKE", exc, safe_query)
            return _search_messages_like(query, user_id, limit)

    hits: list[SearchHit] = []
    for row in rows:
        msg = Message(
            id=row["id"],
            session_id=row["session_id"],
            role=row["role"],
            content=row["content"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            timestamp=row["timestamp"],
        )
        sess = Session(
            id=row["session_id"],
            session_uid=row["session_uid"],
            user_id=row["s_user_id"],
            platform=row["platform"],
            platform_user_id=row["platform_user_id"],
            profile=row["profile"],
            title=row["title"],
            summary=row["summary"],
            created_at=row["s_created_at"],
            updated_at=row["s_updated_at"],
            closed=bool(row["closed"]),
        )
        hits.append(SearchHit(message=msg, session=sess, snippet=row["snippet"]))
    return hits


def _to_fts_query(raw: str) -> str:
    """Convert user input ke FTS5 query string yang aman.

    Kalau user pake operator FTS (AND/OR/NOT/prefix*/phrase " "), kita
    biarkan as-is. Kalau plain text, kita treat tiap token sebagai prefix
    match (token*) dan AND semua. Karakter spesial FTS di-strip.
    """
    raw = raw.strip()
    if any(op in raw for op in ('"', "*", " AND ", " OR ", " NOT ", "(", ")")):
        return raw  # advanced user, trust them

    # Strip karakter punctuation yang bikin FTS error.
    cleaned = "".join(c if c.isalnum() or c.isspace() else " " for c in raw)
    tokens = [t for t in cleaned.split() if t]
    if not tokens:
        return ""
    # Prefix-match tiap token, joined dengan implicit AND.
    return " ".join(f"{t}*" for t in tokens)


def _search_messages_like(query: str, user_id: int | None, limit: int) -> list[SearchHit]:
    """Fallback search pakai LIKE kalau FTS5 gak available."""
    pattern = f"%{query}%"
    sql = """
        SELECT m.*, s.session_uid, s.user_id AS s_user_id, s.platform, s.platform_user_id,
               s.profile, s.title, s.summary, s.created_at AS s_created_at,
               s.updated_at AS s_updated_at, s.closed
        FROM messages m
        JOIN sessions s ON s.id = m.session_id
        WHERE m.content LIKE ?
    """
    params: list[Any] = [pattern]
    if user_id is not None:
        sql += " AND s.user_id = ?"
        params.append(user_id)
    sql += " ORDER BY m.id DESC LIMIT ?"
    params.append(limit)
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    hits: list[SearchHit] = []
    for row in rows:
        msg = Message(
            id=row["id"],
            session_id=row["session_id"],
            role=row["role"],
            content=row["content"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            timestamp=row["timestamp"],
        )
        sess = Session(
            id=row["session_id"],
            session_uid=row["session_uid"],
            user_id=row["s_user_id"],
            platform=row["platform"],
            platform_user_id=row["platform_user_id"],
            profile=row["profile"],
            title=row["title"],
            summary=row["summary"],
            created_at=row["s_created_at"],
            updated_at=row["s_updated_at"],
            closed=bool(row["closed"]),
        )
        hits.append(SearchHit(message=msg, session=sess, snippet=row["content"][:200]))
    return hits


def get_all_user_ids() -> list[int]:
    """Daftar user_id unique yang punya sessions (replacement buat memory.get_all_user_ids)."""
    with _connect() as conn:
        rows = conn.execute("SELECT DISTINCT user_id FROM sessions").fetchall()
    return [r["user_id"] for r in rows]


def count_messages(session_id: int) -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM messages WHERE session_id = ?", (session_id,)
        ).fetchone()
    return int(row["c"])


def iter_recent_messages(session_id: int, limit: int) -> Iterable[Message]:
    """Convenience: yield recent messages chronologically."""
    return iter(get_messages(session_id, limit=limit))
