# tests/test_conftest_fixtures.py
import subprocess
from pathlib import Path


def test_tmp_registry_path_fixture(tmp_registry_path):
    assert isinstance(tmp_registry_path, Path)
    assert tmp_registry_path.name == "projects.json"
    assert tmp_registry_path.parent.exists()
    assert not tmp_registry_path.exists()


def test_patched_registry_path_overrides_module_default(patched_registry_path):
    import overleaf_sync.registry as registry
    assert registry.REGISTRY_PATH == patched_registry_path
    assert registry.REGISTRY_PATH.parent.exists()


def test_bare_remote_is_seeded_git_dir(bare_remote):
    assert isinstance(bare_remote, Path)
    assert (bare_remote / "HEAD").exists()


def test_local_clone_tracks_seeded_remote(local_clone, bare_remote):
    assert (local_clone / ".git").is_dir()
    out = subprocess.run(
        ["git", "-C", str(local_clone), "remote", "get-url", "origin"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert out == str(bare_remote)
    assert (local_clone / "main.tex").exists()  # seed commit present


def test_second_clone_is_independent(second_clone, local_clone, bare_remote):
    assert (second_clone / ".git").is_dir()
    assert second_clone != local_clone
    out = subprocess.run(
        ["git", "-C", str(second_clone), "remote", "get-url", "origin"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert out == str(bare_remote)


def test_conflict_repo_has_unresolved_conflict(conflict_repo):
    git_dir = Path(conflict_repo) / ".git"
    assert (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists()
    unmerged = subprocess.run(
        ["git", "-C", str(conflict_repo), "diff", "--name-only", "--diff-filter=U"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "conflict.tex" in unmerged


def test_sample_logs_contain_known_missing_packages(latexmk_logs):
    assert "tikz_missing" in latexmk_logs
    assert "tikz.sty' not found" in latexmk_logs["tikz_missing"]
    assert "clean" in latexmk_logs
    assert "not found" not in latexmk_logs["clean"]
