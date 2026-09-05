from click.testing import CliRunner

import overleaf_sync.cli as cli_mod
from overleaf_sync.cli import main
from overleaf_sync.registry import Project


def test_register_rejects_non_git(monkeypatch, tmp_path):
    monkeypatch.setattr(cli_mod.gitops, "is_git_repo", lambda repo: False)
    monkeypatch.setattr(cli_mod.gitops, "get_remote_url", lambda repo: None)
    monkeypatch.setattr(cli_mod.registry, "add_project",
                        lambda project: (_ for _ in ()).throw(AssertionError("must not register")))

    runner = CliRunner()
    result = runner.invoke(main, ["register", str(tmp_path), "p"])

    assert result.exit_code != 0
    assert "git" in result.output.lower()


def test_register_rejects_non_overleaf_remote(monkeypatch, tmp_path):
    monkeypatch.setattr(cli_mod.gitops, "is_git_repo", lambda repo: True)
    monkeypatch.setattr(cli_mod.gitops, "get_remote_url",
                        lambda repo: "https://github.com/me/repo.git")
    monkeypatch.setattr(cli_mod.registry, "add_project",
                        lambda project: (_ for _ in ()).throw(AssertionError("must not register")))

    runner = CliRunner()
    result = runner.invoke(main, ["register", str(tmp_path), "p"])

    assert result.exit_code != 0
    assert "overleaf" in result.output.lower()


def test_register_accepts_overleaf_repo(monkeypatch, tmp_path):
    monkeypatch.setattr(cli_mod.gitops, "ensure_local_excludes", lambda *args: None)
    added = {}
    monkeypatch.setattr(cli_mod.gitops, "is_git_repo", lambda repo: True)
    monkeypatch.setattr(cli_mod.gitops, "get_remote_url",
                        lambda repo: "https://git.overleaf.com/PID")
    monkeypatch.setattr(cli_mod.registry, "add_project",
                        lambda project: added.update(project=project))

    runner = CliRunner()
    result = runner.invoke(main, ["register", str(tmp_path), "mypaper"])

    assert result.exit_code == 0, result.output
    proj = added["project"]
    assert isinstance(proj, Project)
    assert proj.alias == "mypaper"
    assert proj.path == str(tmp_path)
    assert proj.remote == "https://git.overleaf.com/PID"


def test_relative_register_path_remains_usable_after_chdir(local_clone, patched_registry_path, tmp_path, monkeypatch):
    from tests.conftest import _git
    from overleaf_sync import registry
    _git('remote', 'set-url', 'origin', 'https://git.overleaf.com/TEST', cwd=local_clone)
    monkeypatch.chdir(local_clone.parent)
    original_add = registry.add_project
    monkeypatch.setattr(registry, 'add_project', lambda project: original_add(project, patched_registry_path))
    result = CliRunner().invoke(main, ['register', local_clone.name, 'relative-paper'])
    assert result.exit_code == 0, result.output
    monkeypatch.chdir(tmp_path)
    project = registry.get_project('relative-paper', patched_registry_path)
    assert project.path == str(local_clone.resolve())
    assert cli_mod.gitops.is_git_repo(project.path)
