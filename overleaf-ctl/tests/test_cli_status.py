from click.testing import CliRunner

import overleaf_sync.cli as cli_mod
from overleaf_sync.cli import main
from overleaf_sync.gitops import RepoStatus
from overleaf_sync.registry import Project


def _stub_resolve(monkeypatch, path="/repo"):
    monkeypatch.setattr(
        cli_mod.registry, "get_project",
        lambda alias: Project(alias=alias, path=path,
                              remote="https://git.overleaf.com/PID"))


def test_status_clean(monkeypatch):
    _stub_resolve(monkeypatch)
    monkeypatch.setattr(cli_mod.gitops, "get_status",
                        lambda repo: RepoStatus(dirty=False, ahead=0, behind=0,
                                                conflicts=[], rebase_in_progress=False))
    runner = CliRunner()
    result = runner.invoke(main, ["status", "mypaper"])
    assert result.exit_code == 0, result.output
    assert "clean" in result.output


def test_status_dirty_ahead_behind_conflicts(monkeypatch):
    _stub_resolve(monkeypatch)
    monkeypatch.setattr(cli_mod.gitops, "get_status",
                        lambda repo: RepoStatus(dirty=True, ahead=3, behind=2,
                                                conflicts=["a.tex"], rebase_in_progress=True))
    runner = CliRunner()
    result = runner.invoke(main, ["status", "mypaper"])
    assert result.exit_code == 0, result.output
    out = result.output
    assert "dirty" in out
    assert "3" in out and "2" in out
    assert "a.tex" in out
