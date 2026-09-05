# tests/test_gitops.py
from pathlib import Path

from overleaf_sync import gitops


def test_giterror_is_runtimeerror():
    assert issubclass(gitops.GitError, RuntimeError)


def test_is_git_repo_true_for_clone(local_clone):
    assert gitops.is_git_repo(local_clone) is True


def test_is_git_repo_accepts_str_path(local_clone):
    assert gitops.is_git_repo(str(local_clone)) is True


def test_is_git_repo_false_for_plain_dir(tmp_path):
    plain = tmp_path / "not_a_repo"
    plain.mkdir()
    assert gitops.is_git_repo(plain) is False


def test_get_remote_url_origin(local_clone, bare_remote):
    url = gitops.get_remote_url(local_clone)
    assert url == str(bare_remote)


def test_get_remote_url_missing_remote_returns_none(tmp_path):
    repo = tmp_path / "lonely"
    repo.mkdir()
    import subprocess
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    assert gitops.get_remote_url(repo) is None


def test_get_remote_url_named(local_clone, bare_remote):
    assert gitops.get_remote_url(local_clone, name="origin") == str(bare_remote)


def test_rebase_in_progress_false_clean(local_clone):
    assert gitops.rebase_in_progress(local_clone) is False


def test_rebase_in_progress_true_when_rebase_merge_dir(local_clone):
    rebase_dir = Path(local_clone) / ".git" / "rebase-merge"
    rebase_dir.mkdir(parents=True)
    assert gitops.rebase_in_progress(local_clone) is True


def test_rebase_in_progress_true_when_rebase_apply_dir(local_clone):
    rebase_dir = Path(local_clone) / ".git" / "rebase-apply"
    rebase_dir.mkdir(parents=True)
    assert gitops.rebase_in_progress(local_clone) is True


def test_unmerged_files_empty_when_clean(local_clone):
    assert gitops.unmerged_files(local_clone) == []


def test_unmerged_files_lists_conflicts(conflict_repo):
    # conflict_repo fixture: a clone mid-rebase with an unresolved conflict in conflict.tex
    assert "conflict.tex" in gitops.unmerged_files(conflict_repo)


import subprocess


def _commit_file(repo: Path, name: str, content: str, msg: str):
    (Path(repo) / name).write_text(content)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", msg], check=True)


def test_repostatus_fields_defaults():
    st = gitops.RepoStatus(dirty=False, ahead=0, behind=0, conflicts=[], rebase_in_progress=False)
    assert st.dirty is False and st.ahead == 0 and st.behind == 0
    assert st.conflicts == [] and st.rebase_in_progress is False


def test_get_status_clean(local_clone):
    st = gitops.get_status(local_clone)
    assert st.dirty is False
    assert st.ahead == 0
    assert st.behind == 0
    assert st.conflicts == []
    assert st.rebase_in_progress is False


def test_get_status_dirty(local_clone):
    (Path(local_clone) / "notes.tex").write_text("scratch")
    st = gitops.get_status(local_clone)
    assert st.dirty is True


def test_get_status_ahead(local_clone):
    _commit_file(Path(local_clone), "ahead.tex", "local-only", "local commit")
    st = gitops.get_status(local_clone)
    assert st.ahead == 1
    assert st.behind == 0


def test_get_status_behind(local_clone, bare_remote, second_clone):
    # second_clone pushes a commit; local_clone fetches and is now behind
    _commit_file(Path(second_clone), "remote.tex", "from-other", "remote commit")
    subprocess.run(["git", "-C", str(second_clone), "push", "-q"], check=True)
    subprocess.run(["git", "-C", str(local_clone), "fetch", "-q"], check=True)
    st = gitops.get_status(local_clone)
    assert st.behind == 1
    assert st.ahead == 0


def test_auto_commit_returns_false_when_clean(local_clone):
    assert gitops.auto_commit(local_clone, "noop") is False


def test_auto_commit_commits_dirty_tree(local_clone):
    (Path(local_clone) / "draft.tex").write_text("hello")
    assert gitops.auto_commit(local_clone, "overleaf-ctl: test") is True
    log = subprocess.run(
        ["git", "-C", str(local_clone), "log", "-1", "--pretty=%s"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert log == "overleaf-ctl: test"
    # tree is clean again after commit
    assert gitops.get_status(local_clone).dirty is False


def test_auto_commit_includes_untracked(local_clone):
    (Path(local_clone) / "new_dir").mkdir()
    (Path(local_clone) / "new_dir" / "fig.tex").write_text("x")
    assert gitops.auto_commit(local_clone, "add untracked") is True
    tracked = subprocess.run(
        ["git", "-C", str(local_clone), "ls-files", "new_dir/fig.tex"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert tracked == "new_dir/fig.tex"


def test_pullresult_fields():
    r = gitops.PullResult(ok=True, conflict=False, output="up to date")
    assert r.ok is True and r.conflict is False and r.output == "up to date"


def test_pull_rebase_noop_when_up_to_date(local_clone):
    r = gitops.pull_rebase(local_clone)
    assert r.ok is True
    assert r.conflict is False


def test_pull_rebase_fast_forwards_remote_commit(local_clone, second_clone):
    _commit_file(Path(second_clone), "remote.tex", "from-other", "remote commit")
    subprocess.run(["git", "-C", str(second_clone), "push", "-q"], check=True)
    r = gitops.pull_rebase(local_clone)
    assert r.ok is True
    assert r.conflict is False
    assert (Path(local_clone) / "remote.tex").read_text() == "from-other"


def test_pull_rebase_replays_local_on_top(local_clone, second_clone):
    # remote advances a non-conflicting file; local has its own commit
    _commit_file(Path(second_clone), "remote.tex", "R", "remote commit")
    subprocess.run(["git", "-C", str(second_clone), "push", "-q"], check=True)
    _commit_file(Path(local_clone), "local.tex", "L", "local commit")
    r = gitops.pull_rebase(local_clone)
    assert r.ok is True
    assert r.conflict is False
    st = gitops.get_status(local_clone)
    assert st.ahead == 1  # local commit replayed, now ahead of fetched remote
    assert st.behind == 0
    assert gitops.rebase_in_progress(local_clone) is False


def test_pull_rebase_conflict_reports_and_preserves_state(local_clone, second_clone):
    # Both clones edit the SAME line of the SAME file -> rebase conflict.
    _commit_file(Path(second_clone), "conflict.tex", "REMOTE version\n", "remote edit")
    subprocess.run(["git", "-C", str(second_clone), "push", "-q"], check=True)
    _commit_file(Path(local_clone), "conflict.tex", "LOCAL version\n", "local edit")

    r = gitops.pull_rebase(local_clone)

    assert r.ok is False
    assert r.conflict is True
    # state is preserved (NOT aborted): rebase still in progress with unmerged files
    assert gitops.rebase_in_progress(local_clone) is True
    assert "conflict.tex" in gitops.unmerged_files(local_clone)


def test_rebase_continue_finishes_after_resolution(local_clone, second_clone):
    # Create a conflict, resolve it, then continue.
    _commit_file(Path(second_clone), "conflict.tex", "REMOTE version\n", "remote edit")
    subprocess.run(["git", "-C", str(second_clone), "push", "-q"], check=True)
    _commit_file(Path(local_clone), "conflict.tex", "LOCAL version\n", "local edit")
    pre = gitops.pull_rebase(local_clone)
    assert pre.conflict is True
    # user resolves the conflict in VSCode -> here we just pick a resolution + stage it
    (Path(local_clone) / "conflict.tex").write_text("RESOLVED\n")
    subprocess.run(["git", "-C", str(local_clone), "add", "conflict.tex"], check=True)

    r = gitops.rebase_continue(local_clone)

    assert r.ok is True
    assert r.conflict is False
    assert gitops.rebase_in_progress(local_clone) is False
    assert (Path(local_clone) / "conflict.tex").read_text() == "RESOLVED\n"


def test_rebase_continue_reports_residual_conflict(local_clone, second_clone):
    # Remote edits conflict.tex ONCE; LOCAL has TWO conflicting commits, so the rebase
    # replays two steps onto the remote base. Resolving step 1 to NEW content makes
    # step 2 (a patch from LOCAL_A->LOCAL_B applied onto that new content) conflict
    # again -> a residual conflict after `git rebase --continue`.
    # (A single local commit would finish cleanly on continue — that cannot test this.)
    _commit_file(Path(second_clone), "conflict.tex", "REMOTE\n", "remote edit")
    subprocess.run(["git", "-C", str(second_clone), "push", "-q"], check=True)
    _commit_file(Path(local_clone), "conflict.tex", "LOCAL_A\n", "local edit 1")
    _commit_file(Path(local_clone), "conflict.tex", "LOCAL_B\n", "local edit 2")
    pre = gitops.pull_rebase(local_clone)
    assert pre.conflict is True
    # resolve ONLY step 1, to content that differs from LOCAL_A so step 2 re-conflicts
    (Path(local_clone) / "conflict.tex").write_text("RESOLVED\n")
    subprocess.run(["git", "-C", str(local_clone), "add", "conflict.tex"], check=True)

    r = gitops.rebase_continue(local_clone)

    assert r.ok is False
    assert r.conflict is True
    assert gitops.rebase_in_progress(local_clone) is True


import pytest


def test_push_sends_local_commit_to_remote(local_clone, second_clone):
    _commit_file(Path(local_clone), "pushme.tex", "payload", "local commit")
    summary = gitops.push(local_clone)
    assert isinstance(summary, str)
    # second clone can now pull the pushed commit
    subprocess.run(["git", "-C", str(second_clone), "pull", "-q", "--rebase"], check=True)
    assert (Path(second_clone) / "pushme.tex").read_text() == "payload"


def test_push_noop_when_nothing_to_push(local_clone):
    # Already in sync with remote; push is a no-op but must not raise.
    summary = gitops.push(local_clone)
    assert isinstance(summary, str)


def test_push_raises_giterror_on_rejected(local_clone, second_clone):
    # Remote advances; local diverges -> non-fast-forward push is rejected.
    _commit_file(Path(second_clone), "remote.tex", "R", "remote commit")
    subprocess.run(["git", "-C", str(second_clone), "push", "-q"], check=True)
    _commit_file(Path(local_clone), "local.tex", "L", "local commit")
    with pytest.raises(gitops.GitError):
        gitops.push(local_clone)


def test_clone_creates_working_repo(bare_remote, tmp_path):
    dest = tmp_path / "fresh_clone"
    gitops.clone(str(bare_remote), dest)
    assert gitops.is_git_repo(dest) is True
    assert gitops.get_remote_url(dest) == str(bare_remote)


def test_clone_accepts_str_dest(bare_remote, tmp_path):
    dest = tmp_path / "str_clone"
    gitops.clone(str(bare_remote), str(dest))
    assert gitops.is_git_repo(dest) is True


def test_clone_raises_giterror_on_bad_url(tmp_path):
    dest = tmp_path / "nope"
    with pytest.raises(gitops.GitError):
        gitops.clone(str(tmp_path / "does_not_exist.git"), dest)


def test_fixtures_share_one_remote(local_clone, second_clone, bare_remote):
    # Both working clones point at the same bare remote.
    assert gitops.get_remote_url(local_clone) == str(bare_remote)
    assert gitops.get_remote_url(second_clone) == str(bare_remote)


def test_end_to_end_sync_round_trip(local_clone, second_clone):
    # local commits + pushes; second pulls; round-trip via the public gitops API only.
    (Path(local_clone) / "round.tex").write_text("trip")
    assert gitops.auto_commit(local_clone, "overleaf-ctl: round") is True
    gitops.push(local_clone)
    r = gitops.pull_rebase(second_clone)
    assert r.ok is True and r.conflict is False
    assert (Path(second_clone) / "round.tex").read_text() == "trip"
    assert gitops.get_status(second_clone).dirty is False


def test_ensure_local_excludes_writes_patterns(local_clone):
    gitops.ensure_local_excludes(local_clone, ["*.aux", ".DS_Store"])
    exclude = Path(local_clone) / ".git" / "info" / "exclude"
    text = exclude.read_text()
    assert "*.aux" in text
    assert ".DS_Store" in text


def test_ensure_local_excludes_is_idempotent(local_clone):
    gitops.ensure_local_excludes(local_clone, ["*.aux"])
    gitops.ensure_local_excludes(local_clone, ["*.aux", "*.log"])
    text = (Path(local_clone) / ".git" / "info" / "exclude").read_text()
    assert text.count("*.aux") == 1
    assert "*.log" in text


def test_ensure_local_excludes_noop_without_git_dir(tmp_path):
    # Must not raise (and create nothing) on a non-repo path.
    gitops.ensure_local_excludes(tmp_path / "nope", ["*.aux"])
    assert not (tmp_path / "nope").exists()


def test_excluded_artifacts_do_not_dirty_status(local_clone):
    gitops.ensure_local_excludes(local_clone, ["*.aux", ".DS_Store"])
    (Path(local_clone) / "main.aux").write_text("x")
    (Path(local_clone) / ".DS_Store").write_text("x")
    assert gitops.get_status(local_clone).dirty is False
