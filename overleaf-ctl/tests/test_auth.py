# tests/test_auth.py
from unittest import mock

import overleaf_sync.auth as auth


def test_default_host_constant():
    assert auth.DEFAULT_HOST == "git.overleaf.com"


def test_ensure_credential_helper_sets_when_unset():
    """If credential.helper is unset, set it to osxkeychain via git config --global."""
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        # `git config --global credential.helper` returns empty + nonzero when unset
        if cmd[:3] == ["git", "config", "--global"] and cmd[-1] == "credential.helper":
            return mock.Mock(returncode=1, stdout="", stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")

    with mock.patch.object(auth.subprocess, "run", side_effect=fake_run):
        auth.ensure_credential_helper()

    # First call reads the value; a later call must SET it to osxkeychain.
    set_calls = [
        c for (c, _) in calls
        if c[:3] == ["git", "config", "--global"]
        and "credential.helper" in c
        and "osxkeychain" in c
    ]
    assert set_calls, f"expected a set call to osxkeychain, got {calls}"
    assert set_calls[0] == ["git", "config", "--global", "credential.helper", "osxkeychain"]


def test_ensure_credential_helper_noop_when_already_set():
    """If credential.helper already has a value, do NOT overwrite it."""
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:3] == ["git", "config", "--global"] and cmd[-1] == "credential.helper":
            return mock.Mock(returncode=0, stdout="osxkeychain\n", stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")

    with mock.patch.object(auth.subprocess, "run", side_effect=fake_run):
        auth.ensure_credential_helper()

    set_calls = [
        c for c in calls
        if c[:3] == ["git", "config", "--global"]
        and "credential.helper" in c
        and len(c) == 5
    ]
    assert not set_calls, f"must not overwrite existing helper, got {set_calls}"


def test_store_token_feeds_credential_approve_stdin():
    """store_token must pipe the exact credential payload to `git credential approve`."""
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["input"] = kwargs.get("input")
        captured["kwargs"] = kwargs
        return mock.Mock(returncode=0, stdout="", stderr="")

    with mock.patch.object(auth.subprocess, "run", side_effect=fake_run):
        auth.store_token("olp_secrettoken123")

    # Command is `git credential approve` — token must NOT be in argv.
    assert captured["cmd"] == ["git", "credential", "approve"]
    assert all("olp_secrettoken123" not in part for part in captured["cmd"])

    # Exact stdin payload format (trailing blank line terminates the request).
    assert captured["input"] == (
        "protocol=https\n"
        "host=git.overleaf.com\n"
        "username=git\n"
        "password=olp_secrettoken123\n"
        "\n"
    )
    # Payload must be passed as text (not bytes) on stdin.
    assert captured["kwargs"].get("text") is True


def test_store_token_honors_host_and_username():
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["input"] = kwargs.get("input")
        return mock.Mock(returncode=0, stdout="", stderr="")

    with mock.patch.object(auth.subprocess, "run", side_effect=fake_run):
        auth.store_token("tok", host="git.example.org", username="alice")

    assert captured["input"] == (
        "protocol=https\n"
        "host=git.example.org\n"
        "username=alice\n"
        "password=tok\n"
        "\n"
    )


def test_store_token_raises_on_git_failure():
    def fake_run(cmd, **kwargs):
        return mock.Mock(returncode=1, stdout="", stderr="boom")

    with mock.patch.object(auth.subprocess, "run", side_effect=fake_run):
        try:
            auth.store_token("tok")
        except RuntimeError as exc:
            # Error message must NOT leak the token.
            assert "tok" not in str(exc)
        else:
            raise AssertionError("expected RuntimeError on git credential failure")


def test_store_token_never_logs_or_persists_token(tmp_path, capsys):
    """The token must not appear in stdout/stderr nor be written to any file."""
    def fake_run(cmd, **kwargs):
        return mock.Mock(returncode=0, stdout="", stderr="")

    with mock.patch.object(auth.subprocess, "run", side_effect=fake_run):
        auth.store_token("olp_supersecret")

    out = capsys.readouterr()
    assert "olp_supersecret" not in out.out
    assert "olp_supersecret" not in out.err

    # No file under tmp_path (or cwd) should contain the token.
    leaked = []
    for p in tmp_path.rglob("*"):
        if p.is_file() and "olp_supersecret" in p.read_text(errors="ignore"):
            leaked.append(str(p))
    assert not leaked, f"token leaked into files: {leaked}"


# ---- platform-dispatched credential helper ---------------------------------

def test_default_helper_per_platform(monkeypatch):
    """Hardcoding osxkeychain poisons non-mac global git config; pick the
    platform's native helper instead."""
    monkeypatch.setattr(auth.sys, "platform", "darwin")
    assert auth.default_credential_helper() == "osxkeychain"
    monkeypatch.setattr(auth.sys, "platform", "win32")
    assert auth.default_credential_helper() == "manager"
    monkeypatch.setattr(auth.sys, "platform", "linux")
    assert auth.default_credential_helper() == "cache"


def test_ensure_credential_helper_uses_platform_helper_on_windows(monkeypatch):
    monkeypatch.setattr(auth.sys, "platform", "win32")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:3] == ["git", "config", "--global"] and cmd[-1] == "credential.helper":
            return mock.Mock(returncode=1, stdout="", stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")

    with mock.patch.object(auth.subprocess, "run", side_effect=fake_run):
        auth.ensure_credential_helper()

    set_calls = [c for c in calls if len(c) == 5 and c[3] == "credential.helper"]
    assert set_calls == [["git", "config", "--global", "credential.helper", "manager"]]


# ---- get_credential / erase_credential --------------------------------------

def test_get_credential_returns_stored_token():
    def fake_run(cmd, **kwargs):
        assert cmd == ["git", "credential", "fill"]
        # must never allow interactive prompting
        env = kwargs.get("env") or {}
        assert env.get("GIT_TERMINAL_PROMPT") == "0"
        return mock.Mock(returncode=0,
                         stdout="protocol=https\nhost=git.overleaf.com\n"
                                "username=git\npassword=olp_storedtok\n",
                         stderr="")

    with mock.patch.object(auth.subprocess, "run", side_effect=fake_run):
        assert auth.get_credential() == "olp_storedtok"


def test_get_credential_none_when_absent():
    def fake_run(cmd, **kwargs):
        return mock.Mock(returncode=128, stdout="", stderr="could not read")

    with mock.patch.object(auth.subprocess, "run", side_effect=fake_run):
        assert auth.get_credential() is None


def test_erase_credential_feeds_reject_via_stdin():
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["input"] = kwargs.get("input")
        return mock.Mock(returncode=0, stdout="", stderr="")

    with mock.patch.object(auth.subprocess, "run", side_effect=fake_run):
        auth.erase_credential(host="git.overleaf.com")

    assert captured["cmd"] == ["git", "credential", "reject"]
    assert captured["input"] == (
        "protocol=https\nhost=git.overleaf.com\nusername=git\n\n")
