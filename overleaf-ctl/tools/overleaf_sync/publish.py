"""Local-only files must not enter a commit or an outgoing commit's tree.

Git ignores alone do not protect forced additions or already tracked files.
These checks inspect the index and every outgoing commit, including files
added and deleted before HEAD. They never alter the index or rewrite history.
"""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

from . import gitops

RESERVED_DIRS = {".writing", ".outputs"}


def git_path(repo: str | Path, name: str) -> Path:
    result = gitops._run(repo, ["rev-parse", "--git-path", name], check=True)
    path = Path(result.stdout.strip())
    return path if path.is_absolute() else Path(repo).resolve() / path


def configured_paths(repo: str | Path) -> list[str]:
    path = git_path(repo, "info/overleaf-ctl-local-only.json")
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, list) or not all(isinstance(p, str) for p in value):
            raise ValueError("expected a list of relative paths")
        return [validate_local_path(p) for p in value]
    except (ValueError, OSError) as exc:
        raise gitops.GitError(f"Invalid local-only configuration {path}: {exc}") from exc


def validate_local_path(value: str) -> str:
    value = value.rstrip("/")
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or any(p in {".", "..", ".git"} for p in value.split("/"))
            or any(c in value for c in "\\\n\r\0*?[]!#:")):
        raise ValueError(f"Expected a literal project-relative local-only path: {value!r}")
    return path.as_posix()


def add_local_paths(repo: str | Path, paths: list[str]) -> None:
    values = sorted(set(configured_paths(repo) + [validate_local_path(p) for p in paths]))
    target = git_path(repo, "info/overleaf-ctl-local-only.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")
    # Escape spaces so a trailing space in a literal path is not discarded by git.
    gitops.ensure_local_excludes(repo, ["/" + p.replace(" ", "\\ ") for p in values])


def is_local_only(path: str, configured: list[str]) -> bool:
    parts = PurePosixPath(path).parts
    return bool(RESERVED_DIRS.intersection(parts)) or any(
        path == p or path.startswith(p + "/") for p in configured
    )


def assert_index_safe(repo: str | Path, include_untracked: bool = False) -> None:
    configured = configured_paths(repo)
    paths = gitops._run(repo, ["ls-files", "-z"], check=True).stdout.split("\0")
    if include_untracked:
        paths += gitops._run(repo, ["ls-files", "--others", "--exclude-standard", "-z"], check=True).stdout.split("\0")
    blocked = sorted({p for p in paths if p and is_local_only(p, configured)})
    if blocked:
        raise gitops.GitError(
            "Local-only files are tracked/staged or exposed to staging; publication blocked:\n  " + "\n  ".join(blocked)
            + "\nKeep the local copies. Review an explicit untrack/migration before retrying; "
            "ignore rules cannot untrack files. No history was rewritten."
        )


def push_target(repo: str | Path) -> tuple[str, str]:
    """Use the current branch's origin upstream, explicitly, to avoid push refspec surprises."""
    upstream = gitops._run(repo, ["rev-parse", "--symbolic-full-name", "@{upstream}"])
    ref = upstream.stdout.strip()
    prefix = "refs/remotes/origin/"
    if upstream.returncode or not ref.startswith(prefix):
        raise gitops.GitError(
            "Guarded push requires a current branch tracking origin/<branch>. "
            "Configure the intended upstream first; no remote was changed."
        )
    fetch_url = gitops._run(repo, ["remote", "get-url", "origin"], check=True).stdout.strip()
    push_urls = gitops._run(repo, ["remote", "get-url", "--push", "--all", "origin"], check=True).stdout.splitlines()
    if push_urls != [fetch_url]:
        raise gitops.GitError("Guarded push requires a single origin push URL matching its fetch URL.")
    return ref, "refs/heads/" + ref[len(prefix):]


def assert_publish_safe(repo: str | Path, refresh: bool = False) -> str:
    assert_index_safe(repo)
    base, destination = push_target(repo)
    if refresh:
        # Check the actual destination, not a potentially stale tracking ref.
        # A missing destination fails closed; creating a new branch is outside
        # the existing registered-project synchronization contract.
        gitops._run(repo, ["fetch", "--no-tags", "origin", destination], check=True)
        base = "FETCH_HEAD"
    configured = configured_paths(repo)
    commits = gitops._run(repo, ["rev-list", "HEAD", "--not", base], check=True).stdout.splitlines()
    for commit in commits:
        paths = gitops._run(repo, ["ls-tree", "-r", "--name-only", "-z", commit], check=True).stdout.split("\0")
        blocked = [p for p in paths if p and is_local_only(p, configured)]
        if blocked:
            raise gitops.GitError(
                f"Outgoing commit {commit[:12]} contains local-only files; push blocked:\n  "
                + "\n  ".join(blocked)
                + "\nDeleting them in a later commit is insufficient. Review unpublished history "
                "before retrying. No history was rewritten."
            )
    return destination
