# overleaf_sync/gitops.py
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


class GitError(RuntimeError):
    """Raised when a git subprocess fails."""


def _run(repo: str | Path, args: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    """Run `git -C <repo> <args...>` capturing text output."""
    cmd = ["git", "-C", str(repo), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed (exit {proc.returncode}): "
            f"{(proc.stderr or proc.stdout).strip()}"
        )
    return proc


def is_git_repo(repo: str | Path) -> bool:
    """True if <repo> is inside a git work tree."""
    if not Path(repo).is_dir():
        return False
    proc = _run(repo, ["rev-parse", "--is-inside-work-tree"])
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def get_remote_url(repo: str | Path, name: str = "origin") -> str | None:
    """Return the configured URL for remote <name>, or None if unset."""
    proc = _run(repo, ["remote", "get-url", name])
    if proc.returncode != 0:
        return None
    url = proc.stdout.strip()
    return url or None


def rebase_in_progress(repo: str | Path) -> bool:
    """True if a rebase is paused (rebase-merge or rebase-apply dir exists)."""
    from .publish import git_path
    if not is_git_repo(repo):
        return False
    return git_path(repo, "rebase-merge").exists() or git_path(repo, "rebase-apply").exists()


def unmerged_files(repo: str | Path) -> list[str]:
    """List paths with unresolved merge conflicts (staged as 'U')."""
    proc = _run(repo, ["diff", "--name-only", "--diff-filter=U"])
    return [line for line in proc.stdout.splitlines() if line.strip()]


@dataclass
class RepoStatus:
    dirty: bool
    ahead: int
    behind: int
    conflicts: list[str] = field(default_factory=list)
    rebase_in_progress: bool = False


def get_status(repo: str | Path) -> RepoStatus:
    """Parse `git status --porcelain=v2 --branch` + rebase dir into RepoStatus."""
    proc = _run(repo, ["status", "--porcelain=v2", "--branch"], check=True)
    ahead = behind = 0
    dirty = False
    conflicts: list[str] = []
    for line in proc.stdout.splitlines():
        if line.startswith("# branch.ab "):
            # "# branch.ab +A -B"
            parts = line.split()
            ahead = int(parts[2].lstrip("+"))
            behind = int(parts[3].lstrip("-"))
        elif line.startswith("# "):
            continue
        elif line.startswith("u "):
            # unmerged entry: last field is the path
            dirty = True
            conflicts.append(line.split(" ", 10)[-1])
        elif line and line[0] in {"1", "2", "?"}:
            # changed (1/2) or untracked (?) entries
            dirty = True
    return RepoStatus(
        dirty=dirty,
        ahead=ahead,
        behind=behind,
        conflicts=conflicts,
        rebase_in_progress=rebase_in_progress(repo),
    )


def auto_commit(repo: str | Path, message: str) -> bool:
    """Stage all changes and commit. Return False if nothing to commit."""
    from .publish import assert_index_safe
    ensure_local_excludes(repo, TEX_LOCAL_EXCLUDES)
    assert_index_safe(repo, include_untracked=True)
    if not get_status(repo).dirty:
        return False
    _run(repo, ["add", "-A"], check=True)
    assert_index_safe(repo)
    proc = _run(repo, ["commit", "-m", message])
    if proc.returncode != 0:
        # Re-check: a clean tree (race) is not an error; otherwise raise.
        if not get_status(repo).dirty:
            return False
        raise GitError(
            f"git commit failed (exit {proc.returncode}): "
            f"{(proc.stderr or proc.stdout).strip()}"
        )
    return True


@dataclass
class PullResult:
    ok: bool
    conflict: bool
    output: str


def _has_conflict_markers(text: str) -> bool:
    lowered = text.lower()
    return "conflict" in lowered or "could not apply" in lowered


def pull_rebase(repo: str | Path) -> PullResult:
    """`git pull --rebase`. On conflict do NOT abort; return conflict=True."""
    proc = _run(repo, ["pull", "--rebase"])
    output = (proc.stdout + proc.stderr).strip()
    if proc.returncode == 0 and not rebase_in_progress(repo):
        return PullResult(ok=True, conflict=False, output=output)
    # Failure: distinguish a rebase conflict (keep the working state) from other errors.
    if rebase_in_progress(repo) or unmerged_files(repo) or _has_conflict_markers(output):
        return PullResult(ok=False, conflict=True, output=output)
    raise GitError(f"git pull --rebase failed (exit {proc.returncode}): {output}")


def rebase_continue(repo: str | Path) -> PullResult:
    """`git rebase --continue` with a no-op editor so it never blocks on a message."""
    proc = _run(repo, ["-c", "core.editor=true", "rebase", "--continue"])
    output = (proc.stdout + proc.stderr).strip()
    if proc.returncode == 0 and not rebase_in_progress(repo):
        return PullResult(ok=True, conflict=False, output=output)
    if rebase_in_progress(repo) or unmerged_files(repo) or _has_conflict_markers(output):
        return PullResult(ok=False, conflict=True, output=output)
    raise GitError(f"git rebase --continue failed (exit {proc.returncode}): {output}")


def push(repo: str | Path) -> str:
    """`git push`. Raise GitError on failure; return a one-line summary."""
    from .publish import assert_publish_safe
    destination = assert_publish_safe(repo, refresh=True)
    proc = _run(repo, ["-c", "push.followTags=false", "push", "origin", f"HEAD:{destination}"])
    output = (proc.stdout + proc.stderr).strip()
    if proc.returncode != 0:
        raise GitError(f"git push failed (exit {proc.returncode}): {output}")
    return output or "Everything up-to-date"


def clone(url: str, dest: str | Path) -> None:
    """`git clone <url> <dest>`. Raise GitError on failure."""
    proc = subprocess.run(
        ["git", "clone", url, str(dest)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise GitError(
            f"git clone failed (exit {proc.returncode}): "
            f"{(proc.stderr or proc.stdout).strip()}"
        )


# Local-only ignore patterns for LaTeX build artifacts and macOS junk.
# Written to .git/info/exclude (NOT .gitignore), so they never get pushed
# to Overleaf yet keep `sync` from auto-committing build noise.
TEX_LOCAL_EXCLUDES: list[str] = [
    ".outputs/", ".writing/",
    "*.aux", "*.log", "*.out", "*.toc", "*.lof", "*.lot",
    "*.bbl", "*.blg", "*.fls", "*.fdb_latexmk",
    "*.synctex.gz", "*.synctex(busy)",
    "*.nav", "*.snm", "*.vrb", "*.xdv",
    "missfont.log",
    ".DS_Store",
]


def ensure_local_excludes(repo: str | Path, patterns: list[str]) -> None:
    """Idempotently append ``patterns`` to <repo>/.git/info/exclude.

    No-op outside Git; resolves the actual Git path for linked worktrees too.
    The exclude file is local-only and never synced to the remote.
    """
    from .publish import git_path
    if not is_git_repo(repo):
        return
    exclude = git_path(repo, "info/exclude")
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = set()
    if exclude.exists():
        existing = {line.strip() for line in exclude.read_text().splitlines()}
    missing = [p for p in patterns if p not in existing]
    if missing:
        with exclude.open("a") as fh:
            if exclude.exists() and exclude.stat().st_size and not exclude.read_bytes().endswith(b"\n"):
                fh.write("\n")
            fh.write("\n".join(missing) + "\n")
