from click.testing import CliRunner

import overleaf_sync.cli as cli_mod
from overleaf_sync.cli import main
from overleaf_sync.gitops import PullResult, RepoStatus
from overleaf_sync.registry import Project


def _stub_resolve(monkeypatch, path="/repo"):
    monkeypatch.setattr(
        cli_mod.registry, "get_project",
        lambda alias: Project(alias=alias, path=path,
                              remote="https://git.overleaf.com/PID"))


def test_sync_rebase_continue_then_push(monkeypatch):
    _stub_resolve(monkeypatch)
    calls = []
    monkeypatch.setattr(cli_mod.gitops, "rebase_in_progress", lambda repo: True)
    monkeypatch.setattr(cli_mod.gitops, "unmerged_files", lambda repo: [])
    monkeypatch.setattr(cli_mod.gitops, "rebase_continue",
                        lambda repo: PullResult(ok=True, conflict=False, output="continued"))
    monkeypatch.setattr(cli_mod.gitops, "push",
                        lambda repo: calls.append("push") or "pushed 1")
    # these must NOT be reached on the continue path
    monkeypatch.setattr(cli_mod.gitops, "auto_commit",
                        lambda repo, message: (_ for _ in ()).throw(AssertionError("no commit")))
    monkeypatch.setattr(cli_mod.gitops, "pull_rebase",
                        lambda repo: (_ for _ in ()).throw(AssertionError("no pull")))

    runner = CliRunner()
    result = runner.invoke(main, ["sync", "mypaper"])

    assert result.exit_code == 0, result.output
    assert calls == ["push"]


def test_sync_rebase_continue_new_conflict_exits_1(monkeypatch):
    # A multi-commit rebase can resolve commit 1's conflict and immediately
    # hit a NEW conflict on a later replayed commit: rebase_continue returns
    # conflict=True (without raising), and the CLI must stop, not push.
    _stub_resolve(monkeypatch)
    unmerged = {"call": 0}

    def _unmerged(repo):
        # First check (before continue) is clean; after continue surfaces a
        # new conflict on the next replayed commit.
        unmerged["call"] += 1
        return [] if unmerged["call"] == 1 else ["c.tex"]

    monkeypatch.setattr(cli_mod.gitops, "rebase_in_progress", lambda repo: True)
    monkeypatch.setattr(cli_mod.gitops, "unmerged_files", _unmerged)
    monkeypatch.setattr(cli_mod.gitops, "rebase_continue",
                        lambda repo: PullResult(ok=False, conflict=True, output="CONFLICT"))
    monkeypatch.setattr(cli_mod.gitops, "push",
                        lambda repo: (_ for _ in ()).throw(AssertionError("must not push")))

    runner = CliRunner()
    result = runner.invoke(main, ["sync", "mypaper"])

    assert result.exit_code == 1
    assert "c.tex" in result.output
    assert "overleaf-ctl sync" in result.output


def test_sync_rebase_in_progress_with_conflicts_exits_1(monkeypatch):
    _stub_resolve(monkeypatch)
    monkeypatch.setattr(cli_mod.gitops, "rebase_in_progress", lambda repo: True)
    monkeypatch.setattr(cli_mod.gitops, "unmerged_files", lambda repo: ["a.tex", "b.tex"])
    monkeypatch.setattr(cli_mod.gitops, "rebase_continue",
                        lambda repo: (_ for _ in ()).throw(AssertionError("must not continue")))
    monkeypatch.setattr(cli_mod.gitops, "push",
                        lambda repo: (_ for _ in ()).throw(AssertionError("must not push")))

    runner = CliRunner()
    result = runner.invoke(main, ["sync", "mypaper"])

    assert result.exit_code == 1
    assert "a.tex" in result.output
    assert "b.tex" in result.output
    assert "overleaf-ctl sync" in result.output


def test_sync_dirty_commits_pulls_pushes(monkeypatch):
    _stub_resolve(monkeypatch)
    order = []
    monkeypatch.setattr(cli_mod.gitops, "rebase_in_progress", lambda repo: False)
    monkeypatch.setattr(cli_mod.gitops, "get_status",
                        lambda repo: RepoStatus(dirty=True, ahead=0, behind=0,
                                                conflicts=[], rebase_in_progress=False))

    def fake_commit(repo, message):
        order.append(("commit", message))
        assert message.startswith("overleaf-ctl: ")
        return True

    monkeypatch.setattr(cli_mod.gitops, "auto_commit", fake_commit)
    monkeypatch.setattr(cli_mod.gitops, "pull_rebase",
                        lambda repo: order.append("pull") or PullResult(ok=True, conflict=False, output="ok"))
    monkeypatch.setattr(cli_mod.gitops, "push",
                        lambda repo: order.append("push") or "pushed")

    runner = CliRunner()
    result = runner.invoke(main, ["sync", "mypaper"])

    assert result.exit_code == 0, result.output
    assert order[0][0] == "commit"
    assert order[1:] == ["pull", "push"]


def test_sync_custom_message_is_used(monkeypatch):
    _stub_resolve(monkeypatch)
    captured = {}
    monkeypatch.setattr(cli_mod.gitops, "rebase_in_progress", lambda repo: False)
    monkeypatch.setattr(cli_mod.gitops, "get_status",
                        lambda repo: RepoStatus(dirty=True, ahead=0, behind=0,
                                                conflicts=[], rebase_in_progress=False))
    monkeypatch.setattr(cli_mod.gitops, "auto_commit",
                        lambda repo, message: captured.update(message=message) or True)
    monkeypatch.setattr(cli_mod.gitops, "pull_rebase",
                        lambda repo: PullResult(ok=True, conflict=False, output="ok"))
    monkeypatch.setattr(cli_mod.gitops, "push", lambda repo: "pushed")

    runner = CliRunner()
    result = runner.invoke(
        main, ["sync", "mypaper", "--message", "fix typo in abstract"])

    assert result.exit_code == 0, result.output
    assert captured["message"] == "fix typo in abstract"


def test_sync_clean_skips_commit(monkeypatch):
    _stub_resolve(monkeypatch)
    order = []
    monkeypatch.setattr(cli_mod.gitops, "rebase_in_progress", lambda repo: False)
    monkeypatch.setattr(cli_mod.gitops, "get_status",
                        lambda repo: RepoStatus(dirty=False, ahead=0, behind=1,
                                                conflicts=[], rebase_in_progress=False))
    monkeypatch.setattr(cli_mod.gitops, "auto_commit",
                        lambda repo, message: (_ for _ in ()).throw(AssertionError("clean -> no commit")))
    monkeypatch.setattr(cli_mod.gitops, "pull_rebase",
                        lambda repo: order.append("pull") or PullResult(ok=True, conflict=False, output="ok"))
    monkeypatch.setattr(cli_mod.gitops, "push",
                        lambda repo: order.append("push") or "pushed")

    runner = CliRunner()
    result = runner.invoke(main, ["sync", "mypaper"])

    assert result.exit_code == 0, result.output
    assert order == ["pull", "push"]


def test_sync_pull_conflict_exits_1_without_abort(monkeypatch):
    _stub_resolve(monkeypatch)
    monkeypatch.setattr(cli_mod.gitops, "rebase_in_progress", lambda repo: False)
    monkeypatch.setattr(cli_mod.gitops, "get_status",
                        lambda repo: RepoStatus(dirty=True, ahead=0, behind=0,
                                                conflicts=[], rebase_in_progress=False))
    monkeypatch.setattr(cli_mod.gitops, "auto_commit", lambda repo, message: True)
    monkeypatch.setattr(cli_mod.gitops, "pull_rebase",
                        lambda repo: PullResult(ok=False, conflict=True, output="CONFLICT"))
    monkeypatch.setattr(cli_mod.gitops, "unmerged_files",
                        lambda repo: ["chapter1.tex"])
    # push must NOT run on conflict
    monkeypatch.setattr(cli_mod.gitops, "push",
                        lambda repo: (_ for _ in ()).throw(AssertionError("must not push on conflict")))

    runner = CliRunner()
    result = runner.invoke(main, ["sync", "mypaper"])

    assert result.exit_code == 1
    assert "chapter1.tex" in result.output
    assert "overleaf-ctl sync" in result.output


def test_sync_no_commit_with_dirty_refuses(monkeypatch):
    _stub_resolve(monkeypatch)
    monkeypatch.setattr(cli_mod.gitops, "rebase_in_progress", lambda repo: False)
    monkeypatch.setattr(cli_mod.gitops, "get_status",
                        lambda repo: RepoStatus(dirty=True, ahead=0, behind=0,
                                                conflicts=[], rebase_in_progress=False))
    monkeypatch.setattr(cli_mod.gitops, "auto_commit",
                        lambda repo, message: (_ for _ in ()).throw(AssertionError("must not commit")))
    monkeypatch.setattr(cli_mod.gitops, "pull_rebase",
                        lambda repo: (_ for _ in ()).throw(AssertionError("must not pull")))
    monkeypatch.setattr(cli_mod.gitops, "push",
                        lambda repo: (_ for _ in ()).throw(AssertionError("must not push")))

    runner = CliRunner()
    result = runner.invoke(main, ["sync", "mypaper", "--no-commit"])

    assert result.exit_code == 1
    assert "commit" in result.output.lower() or "stash" in result.output.lower()


def test_sync_no_commit_clean_proceeds(monkeypatch):
    _stub_resolve(monkeypatch)
    order = []
    monkeypatch.setattr(cli_mod.gitops, "rebase_in_progress", lambda repo: False)
    monkeypatch.setattr(cli_mod.gitops, "get_status",
                        lambda repo: RepoStatus(dirty=False, ahead=1, behind=0,
                                                conflicts=[], rebase_in_progress=False))
    monkeypatch.setattr(cli_mod.gitops, "auto_commit",
                        lambda repo, message: (_ for _ in ()).throw(AssertionError("clean -> no commit")))
    monkeypatch.setattr(cli_mod.gitops, "pull_rebase",
                        lambda repo: order.append("pull") or PullResult(ok=True, conflict=False, output="ok"))
    monkeypatch.setattr(cli_mod.gitops, "push",
                        lambda repo: order.append("push") or "pushed")

    runner = CliRunner()
    result = runner.invoke(main, ["sync", "mypaper", "--no-commit"])

    assert result.exit_code == 0, result.output
    assert order == ["pull", "push"]
