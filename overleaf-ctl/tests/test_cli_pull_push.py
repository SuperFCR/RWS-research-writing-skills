from click.testing import CliRunner

import overleaf_sync.cli as cli_mod
from overleaf_sync.cli import main
from overleaf_sync.gitops import GitError, PullResult
from overleaf_sync.registry import Project


def _stub_resolve(monkeypatch, path="/repo"):
    monkeypatch.setattr(
        cli_mod.registry, "get_project",
        lambda alias: Project(alias=alias, path=path,
                              remote="https://git.overleaf.com/PID"))


def test_pull_ok(monkeypatch):
    _stub_resolve(monkeypatch)
    monkeypatch.setattr(cli_mod.gitops, "pull_rebase",
                        lambda repo: PullResult(ok=True, conflict=False, output="Already up to date."))
    runner = CliRunner()
    result = runner.invoke(main, ["pull", "mypaper"])
    assert result.exit_code == 0, result.output
    assert "Already up to date." in result.output


def test_pull_conflict_exits_1(monkeypatch):
    _stub_resolve(monkeypatch)
    monkeypatch.setattr(cli_mod.gitops, "pull_rebase",
                        lambda repo: PullResult(ok=False, conflict=True, output="CONFLICT"))
    monkeypatch.setattr(cli_mod.gitops, "unmerged_files", lambda repo: ["x.tex"])
    runner = CliRunner()
    result = runner.invoke(main, ["pull", "mypaper"])
    assert result.exit_code == 1
    assert "x.tex" in result.output


def test_push_ok(monkeypatch):
    _stub_resolve(monkeypatch)
    monkeypatch.setattr(cli_mod.gitops, "push", lambda repo: "pushed 2 commits")
    runner = CliRunner()
    result = runner.invoke(main, ["push", "mypaper"])
    assert result.exit_code == 0, result.output
    assert "pushed 2 commits" in result.output


def test_push_error_exits_nonzero(monkeypatch):
    _stub_resolve(monkeypatch)
    def boom(repo):
        raise GitError("rejected: non-fast-forward")
    monkeypatch.setattr(cli_mod.gitops, "push", boom)
    runner = CliRunner()
    result = runner.invoke(main, ["push", "mypaper"])
    assert result.exit_code != 0
    assert "rejected" in result.output
