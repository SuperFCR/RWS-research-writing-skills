from click.testing import CliRunner

import overleaf_sync.cli as cli_mod
from overleaf_sync.cli import main
from overleaf_sync.registry import Project


def _stub_resolve(monkeypatch, path="/repo/path"):
    monkeypatch.setattr(
        cli_mod.registry, "get_project",
        lambda alias: Project(alias=alias, path=path,
                              remote="https://git.overleaf.com/PID"))


def test_open_invokes_code(monkeypatch):
    _stub_resolve(monkeypatch, path="/repo/path")
    captured = {}
    # `code` must be resolved via shutil.which (on Windows it's code.cmd,
    # which bare subprocess cannot find).
    monkeypatch.setattr(cli_mod.shutil, "which",
                        lambda name: "/resolved/bin/code")
    monkeypatch.setattr(cli_mod.subprocess, "run",
                        lambda args, **kw: captured.update(args=args))
    runner = CliRunner()
    result = runner.invoke(main, ["open", "mypaper"])
    assert result.exit_code == 0, result.output
    assert captured["args"] == ["/resolved/bin/code", "/repo/path"]


def test_open_friendly_error_when_code_missing(monkeypatch):
    _stub_resolve(monkeypatch, path="/repo/path")
    monkeypatch.setattr(cli_mod.shutil, "which", lambda name: None)
    result = CliRunner().invoke(main, ["open", "mypaper"])
    assert result.exit_code == 1
    assert "code" in result.output
