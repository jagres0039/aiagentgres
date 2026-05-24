"""Tests untuk sessions store: schema, append, history, search FTS5, migration."""

from __future__ import annotations

import importlib
import sqlite3

import pytest


@pytest.fixture
def fresh_sessions(tmp_path, monkeypatch):
    """Re-init sessions module against a fresh tmp DB."""
    monkeypatch.setenv("JAGRESMAN_HOME", str(tmp_path))

    import paths

    importlib.reload(paths)
    import sessions

    importlib.reload(sessions)
    sessions.init_db()
    return sessions


def test_create_session(fresh_sessions):
    sess = fresh_sessions.get_or_create_active_session(42, platform="telegram")
    assert sess.session_uid.startswith("s_")
    assert sess.user_id == 42
    assert sess.platform == "telegram"
    assert sess.closed is False


def test_session_reused_when_active(fresh_sessions):
    s1 = fresh_sessions.get_or_create_active_session(42)
    s2 = fresh_sessions.get_or_create_active_session(42)
    assert s1.id == s2.id  # same active session reused


def test_session_new_after_close(fresh_sessions):
    s1 = fresh_sessions.get_or_create_active_session(42)
    fresh_sessions.close_session(s1.id)
    s2 = fresh_sessions.get_or_create_active_session(42)
    assert s2.id != s1.id


def test_append_and_get_messages(fresh_sessions):
    sess = fresh_sessions.get_or_create_active_session(42)
    fresh_sessions.append_message(sess.id, "user", "halo bro")
    fresh_sessions.append_message(sess.id, "assistant", "halo juga")
    fresh_sessions.append_message(sess.id, "user", "cek bitcoin dong")

    msgs = fresh_sessions.get_messages(sess.id)
    assert len(msgs) == 3
    assert msgs[0].role == "user"
    assert msgs[0].content == "halo bro"
    assert msgs[2].content == "cek bitcoin dong"


def test_get_messages_with_limit(fresh_sessions):
    sess = fresh_sessions.get_or_create_active_session(42)
    for i in range(10):
        fresh_sessions.append_message(sess.id, "user", f"message {i}")
    msgs = fresh_sessions.get_messages(sess.id, limit=3)
    assert len(msgs) == 3
    assert msgs[0].content == "message 7"
    assert msgs[2].content == "message 9"


def test_clear_messages(fresh_sessions):
    sess = fresh_sessions.get_or_create_active_session(42)
    fresh_sessions.append_message(sess.id, "user", "test")
    deleted = fresh_sessions.clear_messages(sess.id)
    assert deleted == 1
    assert fresh_sessions.get_messages(sess.id) == []


def test_fts_search_basic(fresh_sessions):
    sess = fresh_sessions.get_or_create_active_session(42)
    fresh_sessions.append_message(sess.id, "user", "harga bitcoin hari ini")
    fresh_sessions.append_message(sess.id, "assistant", "saat ini sekitar 100 ribu USD")
    fresh_sessions.append_message(sess.id, "user", "kalau ethereum?")
    fresh_sessions.append_message(sess.id, "assistant", "ethereum di 3500 USD")

    hits = fresh_sessions.search_messages("bitcoin")
    assert len(hits) == 1
    assert "bitcoin" in hits[0].message.content.lower()


def test_fts_search_prefix(fresh_sessions):
    sess = fresh_sessions.get_or_create_active_session(42)
    fresh_sessions.append_message(sess.id, "user", "saya butuh research crypto")
    hits = fresh_sessions.search_messages("rese")
    assert len(hits) == 1


def test_fts_search_user_filter(fresh_sessions):
    s1 = fresh_sessions.get_or_create_active_session(42)
    s2 = fresh_sessions.get_or_create_active_session(99)
    fresh_sessions.append_message(s1.id, "user", "user 42 ngomongin sumber daya")
    fresh_sessions.append_message(s2.id, "user", "user 99 ngomongin sumber daya")

    hits_42 = fresh_sessions.search_messages("sumber", user_id=42)
    assert len(hits_42) == 1
    assert hits_42[0].message.session_id == s1.id

    hits_all = fresh_sessions.search_messages("sumber")
    assert len(hits_all) == 2


def test_fts_search_special_chars_dont_crash(fresh_sessions):
    sess = fresh_sessions.get_or_create_active_session(42)
    fresh_sessions.append_message(sess.id, "user", "test message")
    hits = fresh_sessions.search_messages("(test)")
    # Should not throw — kalau crash, ada masalah dengan escape.
    assert isinstance(hits, list)


def test_fts_search_empty_query(fresh_sessions):
    sess = fresh_sessions.get_or_create_active_session(42)
    fresh_sessions.append_message(sess.id, "user", "halo")
    assert fresh_sessions.search_messages("") == []
    assert fresh_sessions.search_messages("   ") == []


def test_list_sessions(fresh_sessions):
    s1 = fresh_sessions.get_or_create_active_session(42)
    fresh_sessions.close_session(s1.id)
    s2 = fresh_sessions.get_or_create_active_session(42)

    active = fresh_sessions.list_sessions(42)
    assert len(active) == 1
    assert active[0].id == s2.id

    all_sessions = fresh_sessions.list_sessions(42, include_closed=True)
    assert len(all_sessions) == 2


def test_update_session_metadata(fresh_sessions):
    s = fresh_sessions.get_or_create_active_session(42)
    fresh_sessions.update_session_metadata(s.id, title="Test session", summary="Bla bla")
    refreshed = fresh_sessions.get_session_by_uid(s.session_uid)
    assert refreshed is not None
    assert refreshed.title == "Test session"
    assert refreshed.summary == "Bla bla"


def test_count_messages(fresh_sessions):
    s = fresh_sessions.get_or_create_active_session(42)
    assert fresh_sessions.count_messages(s.id) == 0
    fresh_sessions.append_message(s.id, "user", "halo")
    fresh_sessions.append_message(s.id, "assistant", "halo juga")
    assert fresh_sessions.count_messages(s.id) == 2


def test_metadata_roundtrip(fresh_sessions):
    s = fresh_sessions.get_or_create_active_session(42)
    fresh_sessions.append_message(s.id, "user", "halo", metadata={"foo": "bar", "n": 42})
    msgs = fresh_sessions.get_messages(s.id)
    assert msgs[0].metadata == {"foo": "bar", "n": 42}


def test_migrate_legacy_conversations(tmp_path, monkeypatch):
    """Verify migration dari schema lama (conversations table) jalan.

    Bikin DB manual dengan tabel `conversations` ala Phase 0, lalu reload
    sessions module dan check rows pindah.
    """
    monkeypatch.setenv("JAGRESMAN_HOME", str(tmp_path))

    import paths

    importlib.reload(paths)

    # Bikin DB legacy.
    db_path = tmp_path / "memory.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO conversations (user_id, role, content) VALUES (42, 'user', 'legacy halo');
        INSERT INTO conversations (user_id, role, content) VALUES (42, 'assistant', 'legacy reply');
        INSERT INTO conversations (user_id, role, content) VALUES (99, 'user', 'user lain');
        """
    )
    conn.commit()
    conn.close()

    import sessions

    importlib.reload(sessions)
    sessions.init_db()

    s42_list = sessions.list_sessions(42, include_closed=True)
    assert len(s42_list) == 1
    msgs = sessions.get_messages(s42_list[0].id)
    assert len(msgs) == 2
    assert msgs[0].content == "legacy halo"
    assert msgs[1].content == "legacy reply"

    s99_list = sessions.list_sessions(99, include_closed=True)
    assert len(s99_list) == 1


def test_migration_idempotent(fresh_sessions):
    """Re-init schema gak duplikat data."""
    s = fresh_sessions.get_or_create_active_session(42)
    fresh_sessions.append_message(s.id, "user", "halo")
    fresh_sessions._INITIALIZED = False
    fresh_sessions.init_db()
    # Sessions list masih sama.
    sess_list = fresh_sessions.list_sessions(42, include_closed=True)
    assert len(sess_list) == 1
