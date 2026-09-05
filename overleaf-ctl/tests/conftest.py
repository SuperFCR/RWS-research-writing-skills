"""Shared pytest fixtures for overleaf-sync.

Git fixtures use a local bare repo as a stand-in for the Overleaf remote:
  - bare_remote:    a `git init --bare` repo SEEDED with one initial commit on `main`
  - local_clone:    a working clone of bare_remote (has the seed commit)
  - second_clone:   an independent second working clone of the same bare_remote
  - conflict_repo:  local_clone driven into an unresolved rebase conflict on conflict.tex
Registry fixtures:
  - tmp_registry_path / patched_registry_path
Compile fixtures:
  - latexmk_logs:   dict of named sample latexmk .log strings
"""
import subprocess
from pathlib import Path

import pytest


def _git(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    cmd = ["git"]
    if cwd is not None:
        cmd += ["-C", str(cwd)]
    cmd += list(args)
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def _configure(repo: Path) -> None:
    _git("config", "user.email", "test@example.com", cwd=repo)
    _git("config", "user.name", "Test User", cwd=repo)


def _clone(remote_url, dest: Path) -> Path:
    _git("clone", str(remote_url), str(dest))
    _configure(dest)
    return dest


# --- registry path fixtures -------------------------------------------------
@pytest.fixture
def tmp_registry_path(tmp_path: Path) -> Path:
    cfg_dir = tmp_path / "config" / "overleaf-sync"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir / "projects.json"


@pytest.fixture
def patched_registry_path(tmp_registry_path: Path, monkeypatch) -> Path:
    import overleaf_sync.registry as registry
    monkeypatch.setattr(registry, "REGISTRY_PATH", tmp_registry_path)
    return tmp_registry_path


# --- git remote/clone fixtures ----------------------------------------------
@pytest.fixture
def bare_remote(tmp_path: Path) -> Path:
    """A bare repo seeded with one initial commit on `main`."""
    remote = tmp_path / "remote.git"
    _git("init", "--bare", "--initial-branch=main", str(remote))
    seed = tmp_path / "_seed"
    _clone(remote, seed)
    (seed / "main.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\nhello\n\\end{document}\n"
    )
    _git("add", "-A", cwd=seed)
    _git("commit", "-m", "initial commit", cwd=seed)
    _git("push", "-u", "origin", "main", cwd=seed)
    return remote


@pytest.fixture
def local_clone(bare_remote: Path, tmp_path: Path) -> Path:
    return _clone(bare_remote, tmp_path / "local")


@pytest.fixture
def second_clone(bare_remote: Path, tmp_path: Path) -> Path:
    return _clone(bare_remote, tmp_path / "second")


@pytest.fixture
def conflict_repo(local_clone: Path, bare_remote: Path, tmp_path: Path) -> Path:
    """local_clone driven into an unresolved rebase conflict on conflict.tex."""
    other = _clone(bare_remote, tmp_path / "_conflict_other")
    (other / "conflict.tex").write_text("REMOTE version\n")
    _git("add", "-A", cwd=other)
    _git("commit", "-m", "remote edit", cwd=other)
    _git("push", "-q", cwd=other)
    (local_clone / "conflict.tex").write_text("LOCAL version\n")
    _git("add", "-A", cwd=local_clone)
    _git("commit", "-m", "local edit", cwd=local_clone)
    # add/add conflict on conflict.tex -> rebase stalls, leaving it unmerged
    _git("pull", "--rebase", cwd=local_clone, check=False)
    return local_clone


# --- sample latexmk logs ----------------------------------------------------
@pytest.fixture
def latexmk_logs() -> dict[str, str]:
    return {
        "tikz_missing": (
            "This is pdfTeX, Version 3.141592653-2.6-1.40.25 (TeX Live 2025)\n"
            "(./main.tex\n"
            "LaTeX2e <2024-11-01>\n"
            "! LaTeX Error: File `tikz.sty' not found.\n"
            "\n"
            "Type X to quit or <RETURN> to proceed,\n"
            "l.3 \\usepackage{tikz}\n"
        ),
        "clean": (
            "This is pdfTeX, Version 3.141592653-2.6-1.40.25 (TeX Live 2025)\n"
            "(./main.tex\n"
            "Output written on main.pdf (1 page, 12345 bytes).\n"
            "Transcript written on main.log.\n"
        ),
    }
