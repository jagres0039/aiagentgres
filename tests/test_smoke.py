"""Smoke tests — pastiin module-module utama bisa di-import tanpa crash."""

import os


def test_paths_module_imports():
    import paths

    assert paths.BASE_DIR.exists()
    assert paths.SKILLS_DIR
    assert paths.OUTPUT_DIR


def test_paths_respects_jagresman_home(tmp_path, monkeypatch):
    monkeypatch.setenv("JAGRESMAN_HOME", str(tmp_path))
    # Re-import biar override env var ke-pick up.
    import importlib

    import paths

    importlib.reload(paths)
    assert paths.BASE_DIR == tmp_path
    assert paths.DB_PATH == tmp_path / "memory.db"
    # Cleanup: reload tanpa override biar tes lain gak kacau.
    monkeypatch.delenv("JAGRESMAN_HOME")
    importlib.reload(paths)


def test_logging_setup_idempotent():
    import logging_setup

    logging_setup.configure_logging()
    logging_setup.configure_logging()
    log = logging_setup.get_logger("smoketest")
    log.info("hello")


def test_auth_module_imports():
    # OWNER_TELEGRAM_IDS sengaja gak diset di CI; default = deny-all.
    os.environ.pop("OWNER_TELEGRAM_IDS", None)
    os.environ.pop("OWNER_TELEGRAM_ID", None)
    import importlib

    import auth

    importlib.reload(auth)
    assert auth.OWNER_IDS == frozenset()


def test_config_module_imports():
    import config

    # Konstanta wajib ada (boleh None/empty di test env).
    assert hasattr(config, "TELEGRAM_TOKEN")
    assert hasattr(config, "GROQ_MODEL")
    assert config.GROQ_MODEL  # ada default
