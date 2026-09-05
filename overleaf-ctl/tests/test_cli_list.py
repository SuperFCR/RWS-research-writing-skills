from click.testing import CliRunner

import overleaf_sync.cli as cli_mod
from overleaf_sync.cli import main
from overleaf_sync.gitops import RepoStatus
from overleaf_sync.registry import Project


def test_list_renders_table(monkeypatch):
    projects = [
        Project(alias="paperA", path="/p/A", remote="https://git.overleaf.com/A"),
        Project(alias="paperB", path="/p/B", remote="https://git.overleaf.com/B"),
    ]
    statuses = {
        "/p/A": RepoStatus(dirty=False, ahead=0, behind=0, conflicts=[], rebase_in_progress=False),
        "/p/B": RepoStatus(dirty=True, ahead=2, behind=1, conflicts=[], rebase_in_progress=False),
    }
    monkeypatch.setattr(cli_mod.registry, "list_projects", lambda: projects)
    monkeypatch.setattr(cli_mod.gitops, "get_status", lambda repo: statuses[str(repo)])

    runner = CliRunner()
    result = runner.invoke(main, ["list"])

    assert result.exit_code == 0, result.output
    assert "paperA" in result.output
    assert "paperB" in result.output
    assert "clean" in result.output
    assert "dirty" in result.output


def test_list_empty(monkeypatch):
    monkeypatch.setattr(cli_mod.registry, "list_projects", lambda: [])
    runner = CliRunner()
    result = runner.invoke(main, ["list"])
    assert result.exit_code == 0
    assert "无" in result.output or "empty" in result.output.lower()
