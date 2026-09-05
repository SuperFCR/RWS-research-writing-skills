from click.testing import CliRunner

import overleaf_sync.cli as cli_mod
from overleaf_sync.cli import main


def test_login_token_via_stdin(monkeypatch):
    calls = {}

    monkeypatch.setattr(cli_mod.auth, "ensure_credential_helper",
                        lambda: calls.setdefault("ensure", True))
    monkeypatch.setattr(cli_mod.auth, "get_credential",
                        lambda host="git.overleaf.com", username="git": None)

    def fake_store(token, host="git.overleaf.com", username="git"):
        calls["token"] = token
        calls["host"] = host

    monkeypatch.setattr(cli_mod.auth, "store_token", fake_store)

    runner = CliRunner()
    result = runner.invoke(main, ["login", "--token-stdin"], input="olp_secret123\n")

    assert result.exit_code == 0
    assert calls["ensure"] is True
    assert calls["token"] == "olp_secret123"
    assert calls["host"] == "git.overleaf.com"
    # token must never be echoed
    assert "olp_secret123" not in result.output


def test_login_token_via_getpass_and_host_override(monkeypatch):
    calls = {}
    monkeypatch.setattr(cli_mod.auth, "ensure_credential_helper", lambda: None)
    monkeypatch.setattr(cli_mod.auth, "get_credential",
                        lambda host="git.overleaf.com", username="git": None)
    monkeypatch.setattr(cli_mod.auth, "store_token",
                        lambda token, host="git.overleaf.com", username="git": calls.update(token=token, host=host))
    monkeypatch.setattr(cli_mod, "getpass", lambda prompt="": "olp_fromprompt")

    runner = CliRunner()
    result = runner.invoke(main, ["login", "--host", "git.example.com"])

    assert result.exit_code == 0
    assert calls["token"] == "olp_fromprompt"
    assert calls["host"] == "git.example.com"
    assert "olp_fromprompt" not in result.output


def test_login_existing_credential_confirm_overwrite(monkeypatch):
    """Re-login with a stored credential must show the current identity
    (masked token, never the full secret) and ask before overwriting."""
    calls = {}
    monkeypatch.setattr(cli_mod.auth, "ensure_credential_helper", lambda: None)
    monkeypatch.setattr(cli_mod.auth, "get_credential",
                        lambda host="git.overleaf.com", username="git": "olp_oldsecrettoken99")
    monkeypatch.setattr(cli_mod.auth, "store_token",
                        lambda token, host="git.overleaf.com", username="git":
                        calls.update(token=token))
    monkeypatch.setattr(cli_mod, "getpass", lambda prompt="": "olp_newtoken")

    runner = CliRunner()
    result = runner.invoke(main, ["login"], input="y\n")

    assert result.exit_code == 0, result.output
    assert calls["token"] == "olp_newtoken"
    # current identity shown, masked — full old token never echoed
    assert "olp_" in result.output and "en99" in result.output
    assert "olp_oldsecrettoken99" not in result.output


def test_login_existing_credential_decline_keeps(monkeypatch):
    calls = {}
    monkeypatch.setattr(cli_mod.auth, "ensure_credential_helper", lambda: None)
    monkeypatch.setattr(cli_mod.auth, "get_credential",
                        lambda host="git.overleaf.com", username="git": "olp_oldsecrettoken99")
    monkeypatch.setattr(cli_mod.auth, "store_token",
                        lambda *a, **k: calls.update(stored=True))

    result = CliRunner().invoke(main, ["login"], input="n\n")

    assert result.exit_code == 0, result.output
    assert "stored" not in calls
    assert "保留" in result.output


def test_logout_no_credential(monkeypatch):
    monkeypatch.setattr(cli_mod.auth, "get_credential",
                        lambda host="git.overleaf.com", username="git": None)
    erased = {}
    monkeypatch.setattr(cli_mod.auth, "erase_credential",
                        lambda host="git.overleaf.com", username="git": erased.update(yes=True))
    result = CliRunner().invoke(main, ["logout"])
    assert result.exit_code == 0
    assert not erased
    assert "没有" in result.output


def test_logout_confirm_erases(monkeypatch):
    monkeypatch.setattr(cli_mod.auth, "get_credential",
                        lambda host="git.overleaf.com", username="git": "olp_oldsecrettoken99")
    erased = {}
    monkeypatch.setattr(cli_mod.auth, "erase_credential",
                        lambda host="git.overleaf.com", username="git": erased.update(host=host))
    result = CliRunner().invoke(main, ["logout"], input="y\n")
    assert result.exit_code == 0, result.output
    assert erased["host"] == "git.overleaf.com"
    assert "olp_oldsecrettoken99" not in result.output  # masked only


def test_logout_decline_keeps(monkeypatch):
    monkeypatch.setattr(cli_mod.auth, "get_credential",
                        lambda host="git.overleaf.com", username="git": "olp_tok")
    erased = {}
    monkeypatch.setattr(cli_mod.auth, "erase_credential",
                        lambda **k: erased.update(yes=True))
    result = CliRunner().invoke(main, ["logout"], input="n\n")
    assert result.exit_code == 0
    assert not erased
