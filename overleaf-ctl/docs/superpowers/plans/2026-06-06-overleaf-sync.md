# overleaf-sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `overleaf-sync` — a robbyctl-style CLI skill (`overleaf`) that two-way-syncs Overleaf projects through their native git remote and compiles them locally with TinyTeX.

**Architecture:** A Python (click + rich) package `overleaf_sync` exposes the `overleaf` command, backed by a JSON project registry (alias → path/remote/main/engine). `sync` wraps git as auto-commit → `pull --rebase` → `push`, and on any conflict it stops and preserves the working state (never auto-resolves or force-pushes). `compile` wraps `latexmk` (engine aligned to Overleaf's pdfLaTeX) with a missing-package auto-install loop via `tlmgr`. The Overleaf git token lives only in the macOS Keychain (written through `git credential approve`); it is never persisted to the registry, git config, argv, or logs.

**Tech Stack:** Python ≥3.10 (click ≥8.2, rich ≥13), `git`, TinyTeX (TeX Live 2025 / `pdflatex`), macOS Keychain via `git credential`, `pytest`.

---

## Environment notes (verified on this machine, 2026-06-06)

These shape the scaffold/setup tasks — do not ignore them:

- **Python:** `python3` on PATH is **3.13.12** (has `tomllib`, native PEP 604 `X | None`). Use it (or any ≥3.10 interpreter). **`/usr/bin/python3` is 3.9.6 — do NOT build the venv with it**: the dataclasses/CLI use `str | None` and a test imports `tomllib`, both of which break on 3.9.
- **Broken pip mirror (both layers):** `~/.pip/pip.conf` `index-url` **and** the env var `HOMEBREW_PIP_INDEX_URL` both point at the malformed `https://pypi.tuna.tsinghua.edu.cn/web/simple` (note the bogus `/web/`). The correct mirror is `https://pypi.tuna.tsinghua.edu.cn/simple`. `setup.sh` neutralizes both (`PIP_CONFIG_FILE=/dev/null`, `PIP_INDEX_URL=<correct>`, `unset HOMEBREW_PIP_INDEX_URL`) and installs with `--no-build-isolation` so the PEP 517 build subprocess cannot re-read the broken config.
- **No TeX yet:** `latexmk`/`tlmgr` are absent; `setup.sh` installs TinyTeX idempotently.
- **`git` 2.39.5**, **`code` (VSCode CLI)** present.

## File Structure

| Path | Responsibility |
|---|---|
| `overleaf_sync/__init__.py` | `__version__ = "0.1.0"` |
| `overleaf_sync/registry.py` | `Project` dataclass + `projects.json` load/save/add/get/list/remove (atomic, 0700/0600) |
| `overleaf_sync/gitops.py` | thin `git -C <repo>` wrappers: status, auto_commit, pull_rebase, rebase_continue, push, clone |
| `overleaf_sync/auth.py` | store the git token into macOS Keychain via `git credential approve` |
| `overleaf_sync/tex.py` | locate `latexmk`/`tlmgr` (PATH → TinyTeX → MacTeX); `tlmgr` search/install; TinyTeX install |
| `overleaf_sync/compile.py` | main-tex detection; `latexmk` compile loop with missing-package auto-install |
| `overleaf_sync/cli.py` | click group `main` wiring all commands; rich output |
| `pyproject.toml` | packaging metadata, deps (click ≥8.2 / rich ≥13), `overleaf` console script |
| `requirements.txt` | runtime deps |
| `setup.sh` | venv (≥3.10) + editable install (mirror-safe) + symlink + idempotent TinyTeX |
| `tests/conftest.py` | shared fixtures: tmp registry path, seeded bare-remote + clones, sample latexmk logs |
| `tests/test_*.py` | per-module pytest suites |
| `SKILL.md` / `README.md` / `LEGAL.md` | docs |

## Task groups (51 tasks)

1. **Scaffold & packaging** (Tasks 1–5) · 2. **registry.py** (6–10) · 3. **gitops.py** (11–21) · 4. **auth.py** (22–23) · 5. **tex.py** (24–28) · 6. **compile.py** (29–34) · 7. **cli.py** (35–48) · 8. **Docs** (49–51) · then **Final Verification**.

---

## Group 1 — Scaffold & packaging

### Task 1: Bootstrap the test virtualenv (≥3.10) so every later `.venv/bin/python -m pytest` works

**Files:**
- Create: `.gitignore`
- (creates `.venv/` — git-ignored, not committed)

This task exists first so all subsequent TDD steps can run `.venv/bin/python -m pytest` against a known interpreter. It deliberately avoids `/usr/bin/python3` (3.9.6) and the broken pip mirror.

- [ ] **Step 1: Write `.gitignore`**
```text
.venv/
__pycache__/
*.pyc
*.egg-info/
.pytest_cache/
.DS_Store
```

- [ ] **Step 2: Pick a ≥3.10 interpreter and create the venv**

Run:
```bash
PYBIN=""
for cand in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$cand" >/dev/null 2>&1 && \
     "$cand" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,10) else 1)'; then
    PYBIN="$cand"; break
  fi
done
test -n "$PYBIN" || { echo "no python >=3.10 found"; exit 1; }
echo "using: $($PYBIN --version) ($PYBIN)"
"$PYBIN" -m venv .venv
```
Expected: prints e.g. `using: Python 3.13.12 (python3)` and creates `.venv/`.

- [ ] **Step 3: Install pytest (+ tomli on <3.11) through the CORRECT mirror, ignoring the broken config**

Run:
```bash
PIP_CONFIG_FILE=/dev/null PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple" \
HOMEBREW_PIP_INDEX_URL= \
  .venv/bin/python -m pip install --upgrade pip setuptools wheel
PIP_CONFIG_FILE=/dev/null PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple" \
HOMEBREW_PIP_INDEX_URL= \
  .venv/bin/python -m pip install 'pytest>=7' 'tomli; python_version<"3.11"'
```
Expected: pip resolves from `.../simple` (NOT `.../web/simple`) and installs without the `Could not find a version that satisfies the requirement setuptools` error.

- [ ] **Step 4: Verify the toolchain**

Run: `.venv/bin/python -m pytest --version`
Expected: prints a `pytest 7.x`/`8.x` banner.

- [ ] **Step 5: Commit**

Run: `git add .gitignore && git commit -m "build: gitignore + bootstrap notes for the test venv"`

---

### Task 2: Package version constant (`overleaf_sync/__init__.py`)

**Files:**
- Create: `overleaf_sync/__init__.py`
- Test: `tests/__init__.py` (empty), `tests/test_init.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_init.py
import overleaf_sync


def test_version_is_declared():
    assert overleaf_sync.__version__ == "0.1.0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_init.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'overleaf_sync'`.

- [ ] **Step 3: Write minimal implementation**
```python
# overleaf_sync/__init__.py
"""overleaf-sync: local VSCode + git two-way sync + local LaTeX compile for Overleaf."""

__version__ = "0.1.0"
```
```python
# tests/__init__.py
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_init.py -q`
Expected: PASS (1 passed). (`overleaf_sync` is importable because pytest adds the repo root to `sys.path`; the editable install lands in Task 5.)

- [ ] **Step 5: Commit**

Run: `git add overleaf_sync/__init__.py tests/__init__.py tests/test_init.py && git commit -m "feat: overleaf_sync package with __version__ 0.1.0"`

---

### Task 3: Packaging metadata (`pyproject.toml`, `requirements.txt`)

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Test: `tests/test_packaging.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_packaging.py
from pathlib import Path

try:
    import tomllib  # Python >=3.11
except ModuleNotFoundError:  # 3.10 fallback
    import tomli as tomllib

ROOT = Path(__file__).resolve().parent.parent


def _load_pyproject():
    with open(ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)


def test_project_name_and_version():
    data = _load_pyproject()
    assert data["project"]["name"] == "overleaf-sync"
    assert data["project"]["version"] == "0.1.0"
    assert data["project"]["requires-python"] == ">=3.10"


def test_runtime_dependencies_declared():
    deps = " ".join(_load_pyproject()["project"]["dependencies"])
    # click>=8.2 is required so CliRunner merges stderr into result.output.
    assert "click>=8.2" in deps
    assert "rich>=13" in deps


def test_console_script_entrypoint():
    scripts = _load_pyproject()["project"]["scripts"]
    assert scripts["overleaf"] == "overleaf_sync.cli:main"


def test_setuptools_build_backend():
    assert _load_pyproject()["build-system"]["build-backend"] == "setuptools.build_meta"


def test_dev_extra_has_pytest():
    extras = _load_pyproject()["project"]["optional-dependencies"]["dev"]
    assert any(e.startswith("pytest") for e in extras)


def test_requirements_txt_lists_deps():
    text = (ROOT / "requirements.txt").read_text()
    assert "click>=8.2" in text
    assert "rich>=13" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_packaging.py -q`
Expected: FAIL — `FileNotFoundError` opening `pyproject.toml`.

- [ ] **Step 3: Write minimal implementation**
```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=64", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "overleaf-sync"
version = "0.1.0"
description = "Local VSCode + git two-way sync + local LaTeX compile CLI for Overleaf"
readme = "README.md"
requires-python = ">=3.10"
license = { file = "LEGAL.md" }
authors = [{ name = "falcary" }]
dependencies = [
    "click>=8.2",
    "rich>=13",
]

[project.optional-dependencies]
dev = ["pytest>=7", "tomli; python_version<'3.11'"]

[project.scripts]
overleaf = "overleaf_sync.cli:main"

[tool.setuptools]
packages = ["overleaf_sync"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```
```text
# requirements.txt
click>=8.2
rich>=13
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_packaging.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

Run: `git add pyproject.toml requirements.txt tests/test_packaging.py && git commit -m "build: pyproject + requirements (click>=8.2/rich, overleaf console script, dev extra)"`

---

### Task 4: Shared test fixtures (`tests/conftest.py`)

**Files:**
- Create: `tests/conftest.py`
- Test: `tests/test_conftest_fixtures.py`

This task builds the fixtures every later component relies on. The git fixtures are named exactly as the gitops suite consumes them: `bare_remote` (a bare repo **seeded with one initial commit**), `local_clone` and `second_clone` (independent working clones of that remote), and `conflict_repo` (a `local_clone` driven into an unresolved rebase conflict on `conflict.tex`). Plus the registry-path fixtures and sample latexmk logs.

- [ ] **Step 1: Write the failing test**
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_conftest_fixtures.py -q`
Expected: FAIL — every test errors with `fixture '...' not found`.

- [ ] **Step 3: Write minimal implementation**
```python
# tests/conftest.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_conftest_fixtures.py -q`
Expected: PASS for the git/log fixtures (6 of 7). `test_patched_registry_path_overrides_module_default` needs `overleaf_sync/registry.py` (Group 2) and errors until then — re-run after Task 6 and confirm 7 passed.

- [ ] **Step 5: Commit**

Run: `git add tests/conftest.py tests/test_conftest_fixtures.py && git commit -m "test: shared conftest fixtures (seeded bare-remote + clones, conflict_repo, registry path, latexmk logs)"`

---

### Task 5: `setup.sh` (mirror-safe editable install + symlink + idempotent TinyTeX)

**Files:**
- Create: `setup.sh`

`setup.sh` is shell, so it gets a manual verification step. It must dodge BOTH broken pip layers (`~/.pip/pip.conf` and `HOMEBREW_PIP_INDEX_URL`), pre-install `setuptools`/`wheel` and use `--no-build-isolation` (so the PEP 517 build subprocess can't re-read the broken config), pin a ≥3.10 interpreter, symlink the command, and install TinyTeX idempotently.

- [ ] **Step 1: Confirm we start from nothing**

Run: `test -f setup.sh && echo EXISTS || echo MISSING`
Expected: prints `MISSING`.

- [ ] **Step 2: Write the script (full contents, no placeholders)**
```bash
# setup.sh
#!/usr/bin/env bash
# overleaf-sync setup: venv (>=3.10) + mirror-safe editable install + symlink + idempotent TinyTeX.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SKILL_DIR/.venv"
BIN_LINK="$HOME/.local/bin/overleaf"
GOOD_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"   # NOT the broken .../web/simple
TINYTEX_INSTALLER="https://yihui.org/tinytex/install-bin-unix.sh"

echo "==> overleaf-sync setup (skill dir: $SKILL_DIR)"

# 1. Pick a >=3.10 interpreter (NEVER /usr/bin/python3 = 3.9.6).
PYBIN=""
for cand in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$cand" >/dev/null 2>&1 && \
     "$cand" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,10) else 1)'; then
    PYBIN="$(command -v "$cand")"; break
  fi
done
[ -n "$PYBIN" ] || { echo "ERROR: no python >=3.10 found on PATH"; exit 1; }
echo "==> Using interpreter: $("$PYBIN" --version) ($PYBIN)"

# 2. Create venv (idempotent).
if [ ! -x "$VENV_DIR/bin/python" ]; then
  "$PYBIN" -m venv "$VENV_DIR"
else
  echo "==> Reusing venv at $VENV_DIR"
fi

# 3. Editable install through the CORRECT mirror, ignoring the broken pip config/env.
#    PIP_CONFIG_FILE=/dev/null  -> ignore ~/.pip/pip.conf (.../web/simple)
#    HOMEBREW_PIP_INDEX_URL=    -> ignore the broken env mirror
#    --no-build-isolation       -> build with the setuptools/wheel we just installed
export PIP_CONFIG_FILE=/dev/null
export PIP_INDEX_URL="$GOOD_INDEX"
export HOMEBREW_PIP_INDEX_URL=
"$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV_DIR/bin/python" -m pip install --no-build-isolation -e "$SKILL_DIR[dev]"

# 4. Symlink the global command (idempotent; relink if it points elsewhere).
mkdir -p "$(dirname "$BIN_LINK")"
[ -e "$BIN_LINK" ] || [ -L "$BIN_LINK" ] && rm -f "$BIN_LINK" || true
ln -s "$VENV_DIR/bin/overleaf" "$BIN_LINK"
echo "==> Linked $BIN_LINK -> $VENV_DIR/bin/overleaf"

# 5. Idempotent TinyTeX install: skip if a TeX toolchain is already resolvable.
have_tex() {
  command -v latexmk >/dev/null 2>&1 && return 0
  command -v tlmgr   >/dev/null 2>&1 && return 0
  ls "$HOME"/Library/TinyTeX/bin/*/tlmgr >/dev/null 2>&1 && return 0
  [ -x "/Library/TeX/texbin/tlmgr" ] && return 0
  return 1
}
if have_tex; then
  echo "==> TeX toolchain already present; skipping TinyTeX install"
else
  echo "==> Installing TinyTeX from $TINYTEX_INSTALLER"
  curl -sL "$TINYTEX_INSTALLER" | sh
  TLMGR="$(ls "$HOME"/Library/TinyTeX/bin/*/tlmgr 2>/dev/null | head -n1 || true)"
  if [ -n "$TLMGR" ]; then
    echo "==> Ensuring latexmk + base packages"
    "$TLMGR" install latexmk latex-bin xetex || true
  fi
fi

# 6. Smoke check + next steps.
echo "==> Verifying: overleaf --version"
"$BIN_LINK" --version
cat <<'EOF'

==> Done. Next steps:
    overleaf login                       # store your Overleaf git token in Keychain
    overleaf clone <git-url> <alias>     # clone a project + register it
    overleaf sync  <alias>               # auto-commit -> pull --rebase -> push
    overleaf compile <alias> --open      # local latexmk build, open the PDF
EOF
```

- [ ] **Step 3: Verify it parses and is executable**

Run: `bash -n setup.sh && chmod +x setup.sh && echo PARSE_OK`
Expected: prints `PARSE_OK`.

- [ ] **Step 4: Manual end-to-end verification (run once, after the CLI lands in Group 7)**

- `bash setup.sh` completes without error (no `Could not find a version that satisfies the requirement setuptools`).
- `readlink ~/.local/bin/overleaf` → `<skill_dir>/.venv/bin/overleaf`.
- `~/.local/bin/overleaf --version` prints `overleaf, version 0.1.0`.
- Re-running `bash setup.sh` is idempotent (reuses venv, skips TinyTeX when present, relinks cleanly).

- [ ] **Step 5: Commit**

Run: `git add setup.sh && git commit -m "build: setup.sh (>=3.10 venv, mirror-safe --no-build-isolation install, symlink, idempotent TinyTeX)"`

---

## Group 2 — registry.py

### Task 6: registry.py — Project dataclass and load_registry (empty/missing -> {})

**Files:** Create `overleaf_sync/registry.py`; Create/Test `tests/test_registry.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_registry.py
from pathlib import Path

from overleaf_sync.registry import (
    Project,
    load_registry,
)


def test_project_dataclass_fields_and_defaults():
    p = Project(alias="paper", path="/tmp/paper", remote="https://git.overleaf.com/abc")
    assert p.alias == "paper"
    assert p.path == "/tmp/paper"
    assert p.remote == "https://git.overleaf.com/abc"
    assert p.main is None
    assert p.engine is None
    p2 = Project(alias="b", path="/p", remote="r", main="main.tex", engine="pdflatex")
    assert p2.main == "main.tex"
    assert p2.engine == "pdflatex"


def test_load_registry_missing_file_returns_empty(tmp_path: Path):
    missing = tmp_path / "does-not-exist" / "projects.json"
    assert load_registry(missing) == {}


def test_load_registry_empty_dict_when_file_absent_default_factory(tmp_path: Path):
    result = load_registry(tmp_path / "projects.json")
    assert isinstance(result, dict)
    assert result == {}
```

- [ ] **Step 2: Run test to verify it fails** (Run: `.venv/bin/python -m pytest tests/test_registry.py -q`; Expected: FAIL with `ModuleNotFoundError`/`ImportError` — `overleaf_sync.registry` does not exist yet)

- [ ] **Step 3: Write minimal implementation**
```python
# overleaf_sync/registry.py
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

REGISTRY_PATH: Path = Path.home() / ".config" / "overleaf-sync" / "projects.json"


class UnknownAliasError(KeyError):
    """Raised when an alias is not present in the registry."""


class AliasExistsError(ValueError):
    """Raised when adding a project whose alias already exists."""


@dataclass
class Project:
    alias: str
    path: str
    remote: str
    main: str | None = None
    engine: str | None = None


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Project]:
    path = Path(path)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    projects: dict[str, Project] = {}
    for alias, fields in raw.get("projects", {}).items():
        projects[alias] = Project(
            alias=alias,
            path=fields["path"],
            remote=fields["remote"],
            main=fields.get("main"),
            engine=fields.get("engine"),
        )
    return projects
```

- [ ] **Step 4: Run test to verify it passes** (Run: `.venv/bin/python -m pytest tests/test_registry.py -q`; Expected: PASS)

- [ ] **Step 5: Commit** (Run: `git add overleaf_sync/registry.py tests/test_registry.py && git commit -m "registry: Project dataclass + load_registry (missing file -> {})"`)

---

### Task 7: registry.py — save_registry round-trip with atomic write and perms (dir 0700 / file 0600)

**Files:** Modify `overleaf_sync/registry.py`; Modify/Test `tests/test_registry.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_registry.py  (append)
import stat

from overleaf_sync.registry import save_registry


def test_save_then_load_round_trip(tmp_path: Path):
    reg_path = tmp_path / "cfg" / "overleaf-sync" / "projects.json"
    projects = {
        "paper": Project(
            alias="paper",
            path="/Users/x/overleaf/paper",
            remote="https://git.overleaf.com/AAA",
            main="main.tex",
            engine="pdflatex",
        ),
        "thesis": Project(
            alias="thesis",
            path="/Users/x/overleaf/thesis",
            remote="https://git.overleaf.com/BBB",
        ),
    }
    save_registry(projects, reg_path)
    loaded = load_registry(reg_path)
    assert loaded == projects
    assert loaded["thesis"].main is None
    assert loaded["thesis"].engine is None


def test_save_registry_persists_version_and_alias_not_duplicated_in_fields(tmp_path: Path):
    reg_path = tmp_path / "projects.json"
    save_registry({"a": Project(alias="a", path="/p", remote="r")}, reg_path)
    raw = json.loads(reg_path.read_text(encoding="utf-8"))
    assert raw["version"] == 1
    assert "a" in raw["projects"]
    # alias is the JSON key, not stored redundantly inside the object
    assert "alias" not in raw["projects"]["a"]
    assert raw["projects"]["a"]["path"] == "/p"


def test_save_registry_file_and_dir_permissions(tmp_path: Path):
    reg_path = tmp_path / "secret" / "projects.json"
    save_registry({"a": Project(alias="a", path="/p", remote="r")}, reg_path)
    dir_mode = stat.S_IMODE(reg_path.parent.stat().st_mode)
    file_mode = stat.S_IMODE(reg_path.stat().st_mode)
    assert dir_mode == 0o700
    assert file_mode == 0o600


def test_save_registry_is_atomic_no_temp_leftover(tmp_path: Path):
    reg_path = tmp_path / "projects.json"
    save_registry({"a": Project(alias="a", path="/p", remote="r")}, reg_path)
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "projects.json"]
    assert leftovers == []
```

- [ ] **Step 2: Run test to verify it fails** (Run: `.venv/bin/python -m pytest tests/test_registry.py -q`; Expected: FAIL with `ImportError: cannot import name 'save_registry'`)

- [ ] **Step 3: Write minimal implementation** (add to `overleaf_sync/registry.py`)
```python
def _to_payload(projects: dict[str, Project]) -> dict:
    out: dict[str, dict] = {}
    for alias, project in projects.items():
        fields = asdict(project)
        fields.pop("alias", None)
        out[alias] = {k: v for k, v in fields.items() if v is not None}
    return {"version": 1, "projects": out}


def save_registry(projects: dict[str, Project], path: Path = REGISTRY_PATH) -> None:
    path = Path(path)
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    payload = _to_payload(projects)
    fd, tmp_name = tempfile.mkstemp(dir=directory, prefix=".projects.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise
```

> Note: the `load_registry` from Task 6 already reconstructs `main`/`engine` via `fields.get(...)`, so dropping `None` fields on save round-trips correctly.

- [ ] **Step 4: Run test to verify it passes** (Run: `.venv/bin/python -m pytest tests/test_registry.py -q`; Expected: PASS)

- [ ] **Step 5: Commit** (Run: `git add overleaf_sync/registry.py tests/test_registry.py && git commit -m "registry: save_registry atomic write, dir 0700/file 0600, round-trip"`)

---

### Task 8: registry.py — add_project / AliasExistsError

**Files:** Modify `overleaf_sync/registry.py`; Modify/Test `tests/test_registry.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_registry.py  (append)
import pytest

from overleaf_sync.registry import AliasExistsError, add_project


def test_add_project_writes_to_registry(tmp_path: Path):
    reg_path = tmp_path / "projects.json"
    add_project(Project(alias="paper", path="/p", remote="r"), reg_path)
    loaded = load_registry(reg_path)
    assert "paper" in loaded
    assert loaded["paper"].path == "/p"


def test_add_project_appends_without_clobbering(tmp_path: Path):
    reg_path = tmp_path / "projects.json"
    add_project(Project(alias="a", path="/a", remote="ra"), reg_path)
    add_project(Project(alias="b", path="/b", remote="rb"), reg_path)
    loaded = load_registry(reg_path)
    assert set(loaded) == {"a", "b"}


def test_add_project_duplicate_alias_raises(tmp_path: Path):
    reg_path = tmp_path / "projects.json"
    add_project(Project(alias="paper", path="/p1", remote="r1"), reg_path)
    with pytest.raises(AliasExistsError):
        add_project(Project(alias="paper", path="/p2", remote="r2"), reg_path)
    # original is untouched
    assert load_registry(reg_path)["paper"].path == "/p1"
```

- [ ] **Step 2: Run test to verify it fails** (Run: `.venv/bin/python -m pytest tests/test_registry.py -q`; Expected: FAIL with `ImportError: cannot import name 'add_project'`)

- [ ] **Step 3: Write minimal implementation** (add to `overleaf_sync/registry.py`)
```python
def add_project(project: Project, path: Path = REGISTRY_PATH) -> None:
    projects = load_registry(path)
    if project.alias in projects:
        raise AliasExistsError(
            f"alias {project.alias!r} already registered; "
            f"known aliases: {sorted(projects)}"
        )
    projects[project.alias] = project
    save_registry(projects, path)
```

- [ ] **Step 4: Run test to verify it passes** (Run: `.venv/bin/python -m pytest tests/test_registry.py -q`; Expected: PASS)

- [ ] **Step 5: Commit** (Run: `git add overleaf_sync/registry.py tests/test_registry.py && git commit -m "registry: add_project + AliasExistsError"`)

---

### Task 9: registry.py — get_project / UnknownAliasError lists known aliases

**Files:** Modify `overleaf_sync/registry.py`; Modify/Test `tests/test_registry.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_registry.py  (append)
from overleaf_sync.registry import UnknownAliasError, get_project


def test_get_project_returns_project(tmp_path: Path):
    reg_path = tmp_path / "projects.json"
    add_project(Project(alias="paper", path="/p", remote="r", main="m.tex"), reg_path)
    got = get_project("paper", reg_path)
    assert got == Project(alias="paper", path="/p", remote="r", main="m.tex")


def test_get_project_unknown_raises_and_lists_known(tmp_path: Path):
    reg_path = tmp_path / "projects.json"
    add_project(Project(alias="alpha", path="/a", remote="ra"), reg_path)
    add_project(Project(alias="beta", path="/b", remote="rb"), reg_path)
    with pytest.raises(UnknownAliasError) as excinfo:
        get_project("gamma", reg_path)
    msg = str(excinfo.value)
    assert "gamma" in msg
    assert "alpha" in msg
    assert "beta" in msg


def test_get_project_unknown_empty_registry(tmp_path: Path):
    reg_path = tmp_path / "projects.json"
    with pytest.raises(UnknownAliasError):
        get_project("nope", reg_path)
```

- [ ] **Step 2: Run test to verify it fails** (Run: `.venv/bin/python -m pytest tests/test_registry.py -q`; Expected: FAIL with `ImportError: cannot import name 'get_project'`)

- [ ] **Step 3: Write minimal implementation** (add to `overleaf_sync/registry.py`)
```python
def get_project(alias: str, path: Path = REGISTRY_PATH) -> Project:
    projects = load_registry(path)
    if alias not in projects:
        raise UnknownAliasError(
            f"unknown alias {alias!r}; known aliases: {sorted(projects)}"
        )
    return projects[alias]
```

- [ ] **Step 4: Run test to verify it passes** (Run: `.venv/bin/python -m pytest tests/test_registry.py -q`; Expected: PASS)

- [ ] **Step 5: Commit** (Run: `git add overleaf_sync/registry.py tests/test_registry.py && git commit -m "registry: get_project + UnknownAliasError listing known aliases"`)

---

### Task 10: registry.py — list_projects / remove_project

**Files:** Modify `overleaf_sync/registry.py`; Modify/Test `tests/test_registry.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_registry.py  (append)
from overleaf_sync.registry import list_projects, remove_project


def test_list_projects_empty(tmp_path: Path):
    assert list_projects(tmp_path / "projects.json") == []


def test_list_projects_returns_all(tmp_path: Path):
    reg_path = tmp_path / "projects.json"
    add_project(Project(alias="a", path="/a", remote="ra"), reg_path)
    add_project(Project(alias="b", path="/b", remote="rb"), reg_path)
    result = list_projects(reg_path)
    assert isinstance(result, list)
    assert {p.alias for p in result} == {"a", "b"}
    assert all(isinstance(p, Project) for p in result)


def test_remove_project_deletes_alias(tmp_path: Path):
    reg_path = tmp_path / "projects.json"
    add_project(Project(alias="a", path="/a", remote="ra"), reg_path)
    add_project(Project(alias="b", path="/b", remote="rb"), reg_path)
    remove_project("a", reg_path)
    loaded = load_registry(reg_path)
    assert set(loaded) == {"b"}


def test_remove_project_unknown_raises_and_lists_known(tmp_path: Path):
    reg_path = tmp_path / "projects.json"
    add_project(Project(alias="a", path="/a", remote="ra"), reg_path)
    with pytest.raises(UnknownAliasError) as excinfo:
        remove_project("zzz", reg_path)
    assert "zzz" in str(excinfo.value)
    assert "a" in str(excinfo.value)
    # registry unchanged
    assert set(load_registry(reg_path)) == {"a"}
```

- [ ] **Step 2: Run test to verify it fails** (Run: `.venv/bin/python -m pytest tests/test_registry.py -q`; Expected: FAIL with `ImportError: cannot import name 'list_projects'`)

- [ ] **Step 3: Write minimal implementation** (add to `overleaf_sync/registry.py`)
```python
def list_projects(path: Path = REGISTRY_PATH) -> list[Project]:
    return list(load_registry(path).values())


def remove_project(alias: str, path: Path = REGISTRY_PATH) -> None:
    projects = load_registry(path)
    if alias not in projects:
        raise UnknownAliasError(
            f"unknown alias {alias!r}; known aliases: {sorted(projects)}"
        )
    del projects[alias]
    save_registry(projects, path)
```

- [ ] **Step 4: Run test to verify it passes** (Run: `.venv/bin/python -m pytest tests/test_registry.py -q`; Expected: PASS)

- [ ] **Step 5: Commit** (Run: `git add overleaf_sync/registry.py tests/test_registry.py && git commit -m "registry: list_projects + remove_project (UnknownAliasError on missing)"`)

## Group 3 — gitops.py


### Task 11: gitops.GitError + is_git_repo

**Files:** Create `overleaf_sync/gitops.py` · Create `tests/test_gitops.py`

- [ ] **Step 1: Write the failing test**
```python
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
```

- [ ] **Step 2: Run test to verify it fails** — Run: `.venv/bin/pytest tests/test_gitops.py -q`; Expected: FAIL with `ModuleNotFoundError` / `AttributeError: module 'overleaf_sync.gitops' has no attribute 'GitError'` (module/symbols not yet defined).

- [ ] **Step 3: Write minimal implementation**
```python
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
```

- [ ] **Step 4: Run test to verify it passes** — Run: `.venv/bin/pytest tests/test_gitops.py -q`; Expected: PASS.

- [ ] **Step 5: Commit** — Run: `git add overleaf_sync/gitops.py tests/test_gitops.py && git commit -m "gitops: GitError + is_git_repo"`

---

### Task 12: gitops.get_remote_url

**Files:** Modify `overleaf_sync/gitops.py` · Modify `tests/test_gitops.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_gitops.py  (append)
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
```

- [ ] **Step 2: Run test to verify it fails** — Run: `.venv/bin/pytest tests/test_gitops.py -q -k remote_url`; Expected: FAIL with `AttributeError: module 'overleaf_sync.gitops' has no attribute 'get_remote_url'`.

- [ ] **Step 3: Write minimal implementation**
```python
# overleaf_sync/gitops.py  (append)
def get_remote_url(repo: str | Path, name: str = "origin") -> str | None:
    """Return the configured URL for remote <name>, or None if unset."""
    proc = _run(repo, ["remote", "get-url", name])
    if proc.returncode != 0:
        return None
    url = proc.stdout.strip()
    return url or None
```

- [ ] **Step 4: Run test to verify it passes** — Run: `.venv/bin/pytest tests/test_gitops.py -q -k remote_url`; Expected: PASS.

- [ ] **Step 5: Commit** — Run: `git add overleaf_sync/gitops.py tests/test_gitops.py && git commit -m "gitops: get_remote_url"`

---

### Task 13: gitops.rebase_in_progress + unmerged_files

**Files:** Modify `overleaf_sync/gitops.py` · Modify `tests/test_gitops.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_gitops.py  (append)
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
```

- [ ] **Step 2: Run test to verify it fails** — Run: `.venv/bin/pytest tests/test_gitops.py -q -k "rebase_in_progress or unmerged"`; Expected: FAIL with `AttributeError: module 'overleaf_sync.gitops' has no attribute 'rebase_in_progress'`.

- [ ] **Step 3: Write minimal implementation**
```python
# overleaf_sync/gitops.py  (append)
def rebase_in_progress(repo: str | Path) -> bool:
    """True if a rebase is paused (rebase-merge or rebase-apply dir exists)."""
    git_dir = Path(repo) / ".git"
    return (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists()


def unmerged_files(repo: str | Path) -> list[str]:
    """List paths with unresolved merge conflicts (staged as 'U')."""
    proc = _run(repo, ["diff", "--name-only", "--diff-filter=U"])
    return [line for line in proc.stdout.splitlines() if line.strip()]
```

- [ ] **Step 4: Run test to verify it passes** — Run: `.venv/bin/pytest tests/test_gitops.py -q -k "rebase_in_progress or unmerged"`; Expected: PASS.

- [ ] **Step 5: Commit** — Run: `git add overleaf_sync/gitops.py tests/test_gitops.py && git commit -m "gitops: rebase_in_progress + unmerged_files"`

---

### Task 14: gitops.RepoStatus + get_status (clean/dirty/ahead/behind)

**Files:** Modify `overleaf_sync/gitops.py` · Modify `tests/test_gitops.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_gitops.py  (append)
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
```

- [ ] **Step 2: Run test to verify it fails** — Run: `.venv/bin/pytest tests/test_gitops.py -q -k "repostatus or get_status"`; Expected: FAIL with `AttributeError: module 'overleaf_sync.gitops' has no attribute 'RepoStatus'`.

- [ ] **Step 3: Write minimal implementation**
```python
# overleaf_sync/gitops.py  (append)
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
```

- [ ] **Step 4: Run test to verify it passes** — Run: `.venv/bin/pytest tests/test_gitops.py -q -k "repostatus or get_status"`; Expected: PASS.

- [ ] **Step 5: Commit** — Run: `git add overleaf_sync/gitops.py tests/test_gitops.py && git commit -m "gitops: RepoStatus + get_status"`

---

### Task 15: gitops.auto_commit (False when clean)

**Files:** Modify `overleaf_sync/gitops.py` · Modify `tests/test_gitops.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_gitops.py  (append)
def test_auto_commit_returns_false_when_clean(local_clone):
    assert gitops.auto_commit(local_clone, "noop") is False


def test_auto_commit_commits_dirty_tree(local_clone):
    (Path(local_clone) / "draft.tex").write_text("hello")
    assert gitops.auto_commit(local_clone, "overleaf-sync: test") is True
    log = subprocess.run(
        ["git", "-C", str(local_clone), "log", "-1", "--pretty=%s"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert log == "overleaf-sync: test"
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
```

- [ ] **Step 2: Run test to verify it fails** — Run: `.venv/bin/pytest tests/test_gitops.py -q -k auto_commit`; Expected: FAIL with `AttributeError: module 'overleaf_sync.gitops' has no attribute 'auto_commit'`.

- [ ] **Step 3: Write minimal implementation**
```python
# overleaf_sync/gitops.py  (append)
def auto_commit(repo: str | Path, message: str) -> bool:
    """Stage all changes and commit. Return False if nothing to commit."""
    if not get_status(repo).dirty:
        return False
    _run(repo, ["add", "-A"], check=True)
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
```

- [ ] **Step 4: Run test to verify it passes** — Run: `.venv/bin/pytest tests/test_gitops.py -q -k auto_commit`; Expected: PASS.

- [ ] **Step 5: Commit** — Run: `git add overleaf_sync/gitops.py tests/test_gitops.py && git commit -m "gitops: auto_commit"`

---

### Task 16: gitops.PullResult + pull_rebase (happy path)

**Files:** Modify `overleaf_sync/gitops.py` · Modify `tests/test_gitops.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_gitops.py  (append)
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
```

- [ ] **Step 2: Run test to verify it fails** — Run: `.venv/bin/pytest tests/test_gitops.py -q -k "pullresult or pull_rebase"`; Expected: FAIL with `AttributeError: module 'overleaf_sync.gitops' has no attribute 'PullResult'`.

- [ ] **Step 3: Write minimal implementation**
```python
# overleaf_sync/gitops.py  (append)
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
```

- [ ] **Step 4: Run test to verify it passes** — Run: `.venv/bin/pytest tests/test_gitops.py -q -k "pullresult or pull_rebase"`; Expected: PASS.

- [ ] **Step 5: Commit** — Run: `git add overleaf_sync/gitops.py tests/test_gitops.py && git commit -m "gitops: PullResult + pull_rebase happy path"`

---

### Task 17: gitops.pull_rebase (conflict does NOT abort)

**Files:** Modify `overleaf_sync/gitops.py` (no impl change expected) · Modify `tests/test_gitops.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_gitops.py  (append)
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
```

- [ ] **Step 2: Run test to verify it fails** — Run: `.venv/bin/pytest tests/test_gitops.py -q -k pull_rebase_conflict`; Expected: PASS immediately if Task 16 impl is correct; if it FAILs (e.g. impl aborted the rebase or raised GitError), fix `pull_rebase` so a conflict returns `conflict=True` and never runs `rebase --abort`.

- [ ] **Step 3: Write minimal implementation** — No change needed; `pull_rebase` from Task 16 already detects `rebase_in_progress`/`unmerged_files` and returns `PullResult(ok=False, conflict=True, ...)` without aborting. (If Step 2 revealed a gap, the only allowed edit is to the conflict-detection branch of `pull_rebase`; never add a `rebase --abort` call.)

- [ ] **Step 4: Run test to verify it passes** — Run: `.venv/bin/pytest tests/test_gitops.py -q -k pull_rebase_conflict`; Expected: PASS.

- [ ] **Step 5: Commit** — Run: `git add tests/test_gitops.py && git commit -m "gitops: test pull_rebase conflict preserves state"`

---

### Task 18: gitops.rebase_continue

**Files:** Modify `overleaf_sync/gitops.py` · Modify `tests/test_gitops.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_gitops.py  (append)
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
```

- [ ] **Step 2: Run test to verify it fails** — Run: `.venv/bin/pytest tests/test_gitops.py -q -k rebase_continue`; Expected: FAIL with `AttributeError: module 'overleaf_sync.gitops' has no attribute 'rebase_continue'`.

- [ ] **Step 3: Write minimal implementation**
```python
# overleaf_sync/gitops.py  (append)
def rebase_continue(repo: str | Path) -> PullResult:
    """`git rebase --continue` with a no-op editor so it never blocks on a message."""
    proc = _run(repo, ["-c", "core.editor=true", "rebase", "--continue"])
    output = (proc.stdout + proc.stderr).strip()
    if proc.returncode == 0 and not rebase_in_progress(repo):
        return PullResult(ok=True, conflict=False, output=output)
    if rebase_in_progress(repo) or unmerged_files(repo) or _has_conflict_markers(output):
        return PullResult(ok=False, conflict=True, output=output)
    raise GitError(f"git rebase --continue failed (exit {proc.returncode}): {output}")
```

- [ ] **Step 4: Run test to verify it passes** — Run: `.venv/bin/pytest tests/test_gitops.py -q -k rebase_continue`; Expected: PASS.

- [ ] **Step 5: Commit** — Run: `git add overleaf_sync/gitops.py tests/test_gitops.py && git commit -m "gitops: rebase_continue"`

---

### Task 19: gitops.push

**Files:** Modify `overleaf_sync/gitops.py` · Modify `tests/test_gitops.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_gitops.py  (append)
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
```

- [ ] **Step 2: Run test to verify it fails** — Run: `.venv/bin/pytest tests/test_gitops.py -q -k push`; Expected: FAIL with `AttributeError: module 'overleaf_sync.gitops' has no attribute 'push'`.

- [ ] **Step 3: Write minimal implementation**
```python
# overleaf_sync/gitops.py  (append)
def push(repo: str | Path) -> str:
    """`git push`. Raise GitError on failure; return a one-line summary."""
    proc = _run(repo, ["push"])
    output = (proc.stdout + proc.stderr).strip()
    if proc.returncode != 0:
        raise GitError(f"git push failed (exit {proc.returncode}): {output}")
    return output or "Everything up-to-date"
```

- [ ] **Step 4: Run test to verify it passes** — Run: `.venv/bin/pytest tests/test_gitops.py -q -k push`; Expected: PASS.

- [ ] **Step 5: Commit** — Run: `git add overleaf_sync/gitops.py tests/test_gitops.py && git commit -m "gitops: push"`

---

### Task 20: gitops.clone

**Files:** Modify `overleaf_sync/gitops.py` · Modify `tests/test_gitops.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_gitops.py  (append)
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
```

- [ ] **Step 2: Run test to verify it fails** — Run: `.venv/bin/pytest tests/test_gitops.py -q -k clone`; Expected: FAIL with `AttributeError: module 'overleaf_sync.gitops' has no attribute 'clone'`.

- [ ] **Step 3: Write minimal implementation**
```python
# overleaf_sync/gitops.py  (append)
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
```

- [ ] **Step 4: Run test to verify it passes** — Run: `.venv/bin/pytest tests/test_gitops.py -q -k clone`; Expected: PASS.

- [ ] **Step 5: Commit** — Run: `git add overleaf_sync/gitops.py tests/test_gitops.py && git commit -m "gitops: clone"`

---

### Task 21: gitops full-module regression + conftest fixtures sanity

**Files:** Modify `tests/test_gitops.py` (no impl change) · depends on `tests/conftest.py` fixtures `bare_remote`, `local_clone`, `second_clone`, `conflict_repo` (defined in the scaffold task)

- [ ] **Step 1: Write the failing test**
```python
# tests/test_gitops.py  (append)
def test_fixtures_share_one_remote(local_clone, second_clone, bare_remote):
    # Both working clones point at the same bare remote.
    assert gitops.get_remote_url(local_clone) == str(bare_remote)
    assert gitops.get_remote_url(second_clone) == str(bare_remote)


def test_end_to_end_sync_round_trip(local_clone, second_clone):
    # local commits + pushes; second pulls; round-trip via the public gitops API only.
    (Path(local_clone) / "round.tex").write_text("trip")
    assert gitops.auto_commit(local_clone, "overleaf-sync: round") is True
    gitops.push(local_clone)
    r = gitops.pull_rebase(second_clone)
    assert r.ok is True and r.conflict is False
    assert (Path(second_clone) / "round.tex").read_text() == "trip"
    assert gitops.get_status(second_clone).dirty is False
```

- [ ] **Step 2: Run test to verify it fails** — Run: `.venv/bin/pytest tests/test_gitops.py -q -k "fixtures_share or round_trip"`; Expected: FAIL if the `conflict_repo`/`second_clone` fixtures are not yet wired in `conftest.py` (collection error) — confirms this task depends on the scaffold fixtures.

- [ ] **Step 3: Write minimal implementation** — No `gitops.py` change. Ensure `tests/conftest.py` (from the scaffold task) provides: `bare_remote` (a `git init --bare` repo seeded with one initial commit), `local_clone` (clone of `bare_remote`), `second_clone` (independent clone of the same `bare_remote`), and `conflict_repo` (a `local_clone` driven through `pull_rebase` into an unresolved conflict on `conflict.tex`). All clones must set `user.email`/`user.name` locally so commits succeed in CI.

- [ ] **Step 4: Run test to verify it passes** — Run: `.venv/bin/pytest tests/test_gitops.py -q`; Expected: PASS (entire gitops suite green).

- [ ] **Step 5: Commit** — Run: `git add tests/test_gitops.py && git commit -m "gitops: end-to-end round-trip regression"`

## Group 4 — auth.py


### Task 22: auth.py — `ensure_credential_helper` sets osxkeychain only when unset

**Files:**
- Create: `overleaf_sync/auth.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_auth.py
from unittest import mock

import overleaf_sync.auth as auth


def test_default_host_constant():
    assert auth.DEFAULT_HOST == "git.overleaf.com"


def test_ensure_credential_helper_sets_when_unset():
    """If credential.helper is unset, set it to osxkeychain via git config --global."""
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        # `git config --global credential.helper` returns empty + nonzero when unset
        if cmd[:3] == ["git", "config", "--global"] and cmd[-1] == "credential.helper":
            return mock.Mock(returncode=1, stdout="", stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")

    with mock.patch.object(auth.subprocess, "run", side_effect=fake_run):
        auth.ensure_credential_helper()

    # First call reads the value; a later call must SET it to osxkeychain.
    set_calls = [
        c for (c, _) in calls
        if c[:3] == ["git", "config", "--global"]
        and "credential.helper" in c
        and "osxkeychain" in c
    ]
    assert set_calls, f"expected a set call to osxkeychain, got {calls}"
    assert set_calls[0] == ["git", "config", "--global", "credential.helper", "osxkeychain"]


def test_ensure_credential_helper_noop_when_already_set():
    """If credential.helper already has a value, do NOT overwrite it."""
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:3] == ["git", "config", "--global"] and cmd[-1] == "credential.helper":
            return mock.Mock(returncode=0, stdout="osxkeychain\n", stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")

    with mock.patch.object(auth.subprocess, "run", side_effect=fake_run):
        auth.ensure_credential_helper()

    set_calls = [
        c for c in calls
        if c[:3] == ["git", "config", "--global"]
        and "credential.helper" in c
        and len(c) == 5
    ]
    assert not set_calls, f"must not overwrite existing helper, got {set_calls}"
```

- [ ] **Step 2: Run test to verify it fails**
  - Run: `.venv/bin/python -m pytest tests/test_auth.py -q`
  - Expected: FAIL with `ModuleNotFoundError` / `AttributeError: module 'overleaf_sync.auth' has no attribute 'DEFAULT_HOST'` (auth.py does not yet exist).

- [ ] **Step 3: Write minimal implementation**
```python
# overleaf_sync/auth.py
"""Store the Overleaf git token into the macOS Keychain via git credential helper.

Security invariant: the token is NEVER written to disk, the registry, git config,
process arguments, or any log. It is only handed to `git credential approve` over
stdin, which persists it in the macOS Keychain through the osxkeychain helper.
"""
from __future__ import annotations

import subprocess

DEFAULT_HOST = "git.overleaf.com"


def ensure_credential_helper() -> None:
    """Ensure `git config --global credential.helper` is set.

    If it is already set to anything, leave it untouched. Only when unset do we
    set it to ``osxkeychain`` so that subsequent git operations persist/read the
    token from the macOS Keychain.
    """
    result = subprocess.run(
        ["git", "config", "--global", "credential.helper"],
        capture_output=True,
        text=True,
    )
    current = result.stdout.strip()
    if result.returncode != 0 or not current:
        subprocess.run(
            ["git", "config", "--global", "credential.helper", "osxkeychain"],
            check=True,
        )
```

- [ ] **Step 4: Run test to verify it passes**
  - Run: `.venv/bin/python -m pytest tests/test_auth.py -q`
  - Expected: PASS (3 tests).

- [ ] **Step 5: Commit**
  - Run: `git add overleaf_sync/auth.py tests/test_auth.py && git commit -m "auth: ensure_credential_helper sets osxkeychain only when unset"`

### Task 23: auth.py — `store_token` feeds `git credential approve` over stdin (token never logged/persisted)

**Files:**
- Modify: `overleaf_sync/auth.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_auth.py  (append)
def test_store_token_feeds_credential_approve_stdin():
    """store_token must pipe the exact credential payload to `git credential approve`."""
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["input"] = kwargs.get("input")
        captured["kwargs"] = kwargs
        return mock.Mock(returncode=0, stdout="", stderr="")

    with mock.patch.object(auth.subprocess, "run", side_effect=fake_run):
        auth.store_token("olp_secrettoken123")

    # Command is `git credential approve` — token must NOT be in argv.
    assert captured["cmd"] == ["git", "credential", "approve"]
    assert all("olp_secrettoken123" not in part for part in captured["cmd"])

    # Exact stdin payload format (trailing blank line terminates the request).
    assert captured["input"] == (
        "protocol=https\n"
        "host=git.overleaf.com\n"
        "username=git\n"
        "password=olp_secrettoken123\n"
        "\n"
    )
    # Payload must be passed as text (not bytes) on stdin.
    assert captured["kwargs"].get("text") is True


def test_store_token_honors_host_and_username():
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["input"] = kwargs.get("input")
        return mock.Mock(returncode=0, stdout="", stderr="")

    with mock.patch.object(auth.subprocess, "run", side_effect=fake_run):
        auth.store_token("tok", host="git.example.org", username="alice")

    assert captured["input"] == (
        "protocol=https\n"
        "host=git.example.org\n"
        "username=alice\n"
        "password=tok\n"
        "\n"
    )


def test_store_token_raises_on_git_failure():
    def fake_run(cmd, **kwargs):
        return mock.Mock(returncode=1, stdout="", stderr="boom")

    with mock.patch.object(auth.subprocess, "run", side_effect=fake_run):
        try:
            auth.store_token("tok")
        except RuntimeError as exc:
            # Error message must NOT leak the token.
            assert "tok" not in str(exc)
        else:
            raise AssertionError("expected RuntimeError on git credential failure")


def test_store_token_never_logs_or_persists_token(tmp_path, capsys):
    """The token must not appear in stdout/stderr nor be written to any file."""
    def fake_run(cmd, **kwargs):
        return mock.Mock(returncode=0, stdout="", stderr="")

    with mock.patch.object(auth.subprocess, "run", side_effect=fake_run):
        auth.store_token("olp_supersecret")

    out = capsys.readouterr()
    assert "olp_supersecret" not in out.out
    assert "olp_supersecret" not in out.err

    # No file under tmp_path (or cwd) should contain the token.
    leaked = []
    for p in tmp_path.rglob("*"):
        if p.is_file() and "olp_supersecret" in p.read_text(errors="ignore"):
            leaked.append(str(p))
    assert not leaked, f"token leaked into files: {leaked}"
```

- [ ] **Step 2: Run test to verify it fails**
  - Run: `.venv/bin/python -m pytest tests/test_auth.py -q`
  - Expected: FAIL with `AttributeError: module 'overleaf_sync.auth' has no attribute 'store_token'`.

- [ ] **Step 3: Write minimal implementation**
```python
# overleaf_sync/auth.py  (append after ensure_credential_helper)
def store_token(token: str, host: str = DEFAULT_HOST, username: str = "git") -> None:
    """Persist ``token`` into the macOS Keychain via ``git credential approve``.

    The credential is supplied only on stdin in git-credential format; the token
    never appears in argv, and on failure the raised error never echoes it.
    """
    payload = (
        f"protocol=https\n"
        f"host={host}\n"
        f"username={username}\n"
        f"password={token}\n"
        f"\n"
    )
    result = subprocess.run(
        ["git", "credential", "approve"],
        input=payload,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "git credential approve failed "
            f"(exit {result.returncode}): {result.stderr.strip()}"
        )
```

- [ ] **Step 4: Run test to verify it passes**
  - Run: `.venv/bin/python -m pytest tests/test_auth.py -q`
  - Expected: PASS (7 tests total in the file).

- [ ] **Step 5: Commit**
  - Run: `git add overleaf_sync/auth.py tests/test_auth.py && git commit -m "auth: store_token feeds git credential approve via stdin, never logs token"`

## Group 5 — tex.py


### Task 24: tex.py — locate_tool (PATH → TinyTeX glob → MacTeX)

**Files:** Create `overleaf_sync/tex.py` · Test `tests/test_tex.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_tex.py
from pathlib import Path

import overleaf_sync.tex as tex


def test_locate_tool_prefers_path(monkeypatch):
    """shutil.which hit wins over any fallback."""
    monkeypatch.setattr(tex.shutil, "which", lambda name: "/usr/local/bin/latexmk")
    assert tex.locate_tool("latexmk") == "/usr/local/bin/latexmk"


def test_locate_tool_falls_back_to_tinytex(monkeypatch, tmp_path):
    """When not on PATH, glob ~/Library/TinyTeX/bin/*/ for the tool."""
    monkeypatch.setattr(tex.shutil, "which", lambda name: None)
    bindir = tmp_path / "Library" / "TinyTeX" / "bin" / "universal-darwin"
    bindir.mkdir(parents=True)
    tool = bindir / "tlmgr"
    tool.write_text("#!/bin/sh\n")
    monkeypatch.setattr(tex.Path, "home", classmethod(lambda cls: tmp_path))
    # MacTeX dir must not exist for this machine
    monkeypatch.setattr(tex, "MACTEX_BIN", tmp_path / "nope")
    assert tex.locate_tool("tlmgr") == str(tool)


def test_locate_tool_falls_back_to_mactex(monkeypatch, tmp_path):
    """When not on PATH and no TinyTeX, use MacTeX texbin."""
    monkeypatch.setattr(tex.shutil, "which", lambda name: None)
    monkeypatch.setattr(tex.Path, "home", classmethod(lambda cls: tmp_path))  # no TinyTeX under here
    mactex = tmp_path / "texbin"
    mactex.mkdir(parents=True)
    tool = mactex / "latexmk"
    tool.write_text("#!/bin/sh\n")
    monkeypatch.setattr(tex, "MACTEX_BIN", mactex)
    assert tex.locate_tool("latexmk") == str(tool)


def test_locate_tool_returns_none_when_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(tex.shutil, "which", lambda name: None)
    monkeypatch.setattr(tex.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(tex, "MACTEX_BIN", tmp_path / "nope")
    assert tex.locate_tool("latexmk") is None
```

- [ ] **Step 2: Run test to verify it fails** (Run: `.venv/bin/python -m pytest tests/test_tex.py -q`; Expected: FAIL — `ModuleNotFoundError`/`AttributeError`: `overleaf_sync.tex` and `locate_tool`/`MACTEX_BIN` do not yet exist)

- [ ] **Step 3: Write minimal implementation**
```python
# overleaf_sync/tex.py
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

TINYTEX_BIN_GLOB = "Library/TinyTeX/bin/*"      # joined under Path.home()
MACTEX_BIN = Path("/Library/TeX/texbin")


class TexNotFoundError(RuntimeError):
    """Raised when a required TeX tool cannot be located."""


def locate_tool(name: str) -> str | None:
    """Return absolute path to `name`: PATH -> TinyTeX glob -> MacTeX, else None."""
    found = shutil.which(name)
    if found:
        return found
    for bindir in sorted(Path.home().glob(TINYTEX_BIN_GLOB)):
        cand = bindir / name
        if cand.exists():
            return str(cand)
    cand = MACTEX_BIN / name
    if cand.exists():
        return str(cand)
    return None
```

- [ ] **Step 4: Run test to verify it passes** (Run: `.venv/bin/python -m pytest tests/test_tex.py -q`; Expected: PASS — all 4 locate_tool tests green)

- [ ] **Step 5: Commit** (Run: `git add overleaf_sync/tex.py tests/test_tex.py && git commit -m "tex: locate_tool (PATH -> TinyTeX -> MacTeX)"`)

### Task 25: tex.py — require_tool (raise TexNotFoundError with setup hint)

**Files:** Modify `overleaf_sync/tex.py` · Test `tests/test_tex.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_tex.py  (append)
import pytest


def test_require_tool_returns_path_when_found(monkeypatch):
    monkeypatch.setattr(tex, "locate_tool", lambda name: "/abs/bin/latexmk")
    assert tex.require_tool("latexmk") == "/abs/bin/latexmk"


def test_require_tool_raises_with_setup_hint(monkeypatch):
    monkeypatch.setattr(tex, "locate_tool", lambda name: None)
    with pytest.raises(tex.TexNotFoundError) as ei:
        tex.require_tool("latexmk")
    msg = str(ei.value)
    assert "latexmk" in msg
    assert "setup.sh" in msg
```

- [ ] **Step 2: Run test to verify it fails** (Run: `.venv/bin/python -m pytest tests/test_tex.py -q -k require_tool`; Expected: FAIL — `AttributeError`: `require_tool` not defined)

- [ ] **Step 3: Write minimal implementation**
```python
# overleaf_sync/tex.py  (append)
def require_tool(name: str) -> str:
    """Locate `name` or raise TexNotFoundError pointing at setup.sh."""
    path = locate_tool(name)
    if path is None:
        raise TexNotFoundError(
            f"找不到 TeX 工具 {name!r}。请先运行 setup.sh 安装 TinyTeX，"
            f"或确认 TinyTeX/MacTeX 已安装。"
        )
    return path
```

- [ ] **Step 4: Run test to verify it passes** (Run: `.venv/bin/python -m pytest tests/test_tex.py -q -k require_tool`; Expected: PASS — both require_tool tests green)

- [ ] **Step 5: Commit** (Run: `git add overleaf_sync/tex.py tests/test_tex.py && git commit -m "tex: require_tool raises TexNotFoundError with setup.sh hint"`)

### Task 26: tex.py — tlmgr_search_file (parse package names from tlmgr output)

**Files:** Modify `overleaf_sync/tex.py` · Test `tests/test_tex.py`

- [ ] **Step 1: Write the failing test** (table-driven against real `tlmgr search --global --file` output)
```python
# tests/test_tex.py  (append)

# Real `tlmgr search --global --file "/tikz.sty"` output shape:
#   each matching package starts flush-left with "<pkg>:" then indented file lines.
TLMGR_TIKZ_OUTPUT = """\
tlmgr: package repository https://mirror.ctan.org/systems/texlive/tlnet
pgf:
\ttexmf-dist/tex/generic/pgf/frontendlayer/tikz.sty
\ttexmf-dist/tex/latex/pgf/frontendlayer/tikz.sty
"""

# `tlmgr search --global --file "/algorithm.sty"` returns multiple packages:
TLMGR_MULTI_OUTPUT = """\
tlmgr: package repository https://mirror.ctan.org/systems/texlive/tlnet
algorithm2e:
\ttexmf-dist/tex/latex/algorithm2e/algorithm2e.sty
algorithms:
\ttexmf-dist/tex/latex/algorithms/algorithm.sty
"""

TLMGR_EMPTY_OUTPUT = """\
tlmgr: package repository https://mirror.ctan.org/systems/texlive/tlnet
"""


def _run_tlmgr_stub(output):
    class _CP:
        def __init__(self, out):
            self.stdout = out
            self.returncode = 0
    def runner(*args, **kwargs):
        return _CP(output)
    return runner


def test_tlmgr_search_file_single_package(monkeypatch):
    monkeypatch.setattr(tex, "require_tool", lambda name: "/abs/bin/tlmgr")
    monkeypatch.setattr(tex.subprocess, "run", _run_tlmgr_stub(TLMGR_TIKZ_OUTPUT))
    assert tex.tlmgr_search_file("tikz.sty") == ["pgf"]


def test_tlmgr_search_file_multiple_packages_order_preserving(monkeypatch):
    monkeypatch.setattr(tex, "require_tool", lambda name: "/abs/bin/tlmgr")
    monkeypatch.setattr(tex.subprocess, "run", _run_tlmgr_stub(TLMGR_MULTI_OUTPUT))
    assert tex.tlmgr_search_file("algorithm.sty") == ["algorithm2e", "algorithms"]


def test_tlmgr_search_file_no_match(monkeypatch):
    monkeypatch.setattr(tex, "require_tool", lambda name: "/abs/bin/tlmgr")
    monkeypatch.setattr(tex.subprocess, "run", _run_tlmgr_stub(TLMGR_EMPTY_OUTPUT))
    assert tex.tlmgr_search_file("nope.sty") == []


def test_tlmgr_search_file_invokes_global_file_flags(monkeypatch):
    """Argv must use --global --file with a leading-slash filename."""
    captured = {}
    monkeypatch.setattr(tex, "require_tool", lambda name: "/abs/bin/tlmgr")

    class _CP:
        stdout = TLMGR_TIKZ_OUTPUT
        returncode = 0

    def runner(argv, *a, **k):
        captured["argv"] = argv
        return _CP()

    monkeypatch.setattr(tex.subprocess, "run", runner)
    tex.tlmgr_search_file("tikz.sty")
    argv = captured["argv"]
    assert argv[0] == "/abs/bin/tlmgr"
    assert "--global" in argv
    assert "--file" in argv
    assert "/tikz.sty" in argv  # leading slash anchors the basename
```

- [ ] **Step 2: Run test to verify it fails** (Run: `.venv/bin/python -m pytest tests/test_tex.py -q -k tlmgr_search`; Expected: FAIL — `AttributeError`: `tlmgr_search_file` not defined)

- [ ] **Step 3: Write minimal implementation**
```python
# overleaf_sync/tex.py  (append)
def tlmgr_search_file(filename: str) -> list[str]:
    """Run `tlmgr search --global --file "/<filename>"`; return package names.

    Package names are the flush-left lines ending in ':' in tlmgr output;
    indented lines are matched file paths. Deduped, order-preserving.
    """
    tlmgr = require_tool("tlmgr")
    query = filename if filename.startswith("/") else "/" + filename
    proc = subprocess.run(
        [tlmgr, "search", "--global", "--file", query],
        capture_output=True,
        text=True,
    )
    packages: list[str] = []
    for line in proc.stdout.splitlines():
        if not line or line[0] in (" ", "\t"):
            continue  # indented file path, skip
        if line.startswith("tlmgr:"):
            continue  # repository banner / diagnostics
        stripped = line.rstrip()
        if stripped.endswith(":"):
            pkg = stripped[:-1].strip()
            if pkg and pkg not in packages:
                packages.append(pkg)
    return packages
```

- [ ] **Step 4: Run test to verify it passes** (Run: `.venv/bin/python -m pytest tests/test_tex.py -q -k tlmgr_search`; Expected: PASS — all 4 tlmgr_search_file tests green)

- [ ] **Step 5: Commit** (Run: `git add overleaf_sync/tex.py tests/test_tex.py && git commit -m "tex: tlmgr_search_file parses package names from tlmgr output"`)

### Task 27: tex.py — tlmgr_install

**Files:** Modify `overleaf_sync/tex.py` · Test `tests/test_tex.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_tex.py  (append)


def test_tlmgr_install_invokes_tlmgr_install_with_packages(monkeypatch):
    captured = {}
    monkeypatch.setattr(tex, "require_tool", lambda name: "/abs/bin/tlmgr")

    def runner(argv, *a, **k):
        captured["argv"] = argv
        captured["check"] = k.get("check")
        class _CP:
            returncode = 0
        return _CP()

    monkeypatch.setattr(tex.subprocess, "run", runner)
    tex.tlmgr_install(["pgf", "algorithm2e"])
    assert captured["argv"] == ["/abs/bin/tlmgr", "install", "pgf", "algorithm2e"]


def test_tlmgr_install_empty_list_is_noop(monkeypatch):
    """No packages -> do not invoke tlmgr at all."""
    called = {"ran": False}
    monkeypatch.setattr(tex, "require_tool", lambda name: "/abs/bin/tlmgr")

    def runner(*a, **k):
        called["ran"] = True
        class _CP:
            returncode = 0
        return _CP()

    monkeypatch.setattr(tex.subprocess, "run", runner)
    tex.tlmgr_install([])
    assert called["ran"] is False
```

- [ ] **Step 2: Run test to verify it fails** (Run: `.venv/bin/python -m pytest tests/test_tex.py -q -k tlmgr_install`; Expected: FAIL — `AttributeError`: `tlmgr_install` not defined)

- [ ] **Step 3: Write minimal implementation**
```python
# overleaf_sync/tex.py  (append)
def tlmgr_install(packages: list[str]) -> None:
    """Install the given TeX Live packages via `tlmgr install`. No-op if empty."""
    if not packages:
        return
    tlmgr = require_tool("tlmgr")
    subprocess.run([tlmgr, "install", *packages], check=True)
```

- [ ] **Step 4: Run test to verify it passes** (Run: `.venv/bin/python -m pytest tests/test_tex.py -q -k tlmgr_install`; Expected: PASS — both tlmgr_install tests green)

- [ ] **Step 5: Commit** (Run: `git add overleaf_sync/tex.py tests/test_tex.py && git commit -m "tex: tlmgr_install runs tlmgr install for packages"`)

### Task 28: tex.py — install_tinytex (thin wrapper)

**Files:** Modify `overleaf_sync/tex.py` · Test `tests/test_tex.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_tex.py  (append)


def test_install_tinytex_pipes_installer_to_shell(monkeypatch):
    captured = {}

    def runner(cmd, *a, **k):
        captured["cmd"] = cmd
        captured["shell"] = k.get("shell")
        captured["check"] = k.get("check")
        class _CP:
            returncode = 0
        return _CP()

    monkeypatch.setattr(tex.subprocess, "run", runner)
    tex.install_tinytex()
    cmd = captured["cmd"]
    assert "https://yihui.org/tinytex/install-bin-unix.sh" in cmd
    assert "curl" in cmd and "| sh" in cmd
    assert captured["shell"] is True
    assert captured["check"] is True
```

- [ ] **Step 2: Run test to verify it fails** (Run: `.venv/bin/python -m pytest tests/test_tex.py -q -k install_tinytex`; Expected: FAIL — `AttributeError`: `install_tinytex` not defined)

- [ ] **Step 3: Write minimal implementation**
```python
# overleaf_sync/tex.py  (append)
TINYTEX_INSTALL_URL = "https://yihui.org/tinytex/install-bin-unix.sh"


def install_tinytex() -> None:
    """Install TinyTeX (thin wrapper; mostly invoked by setup.sh)."""
    subprocess.run(
        f'curl -sL "{TINYTEX_INSTALL_URL}" | sh',
        shell=True,
        check=True,
    )
```

- [ ] **Step 4: Run test to verify it passes** (Run: `.venv/bin/python -m pytest tests/test_tex.py -q -k install_tinytex`; Expected: PASS — install_tinytex test green)

- [ ] **Step 5: Commit** (Run: `git add overleaf_sync/tex.py tests/test_tex.py && git commit -m "tex: install_tinytex thin wrapper over install-bin-unix.sh"`)

## Group 6 — compile.py


### Task 29: compile.py — `engine_flag` (engine name → latexmk switch)

**Files:**
- Create: `overleaf_sync/compile.py`
- Test: `tests/test_compile_engine_flag.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_compile_engine_flag.py
import pytest

from overleaf_sync.compile import engine_flag


@pytest.mark.parametrize(
    "engine,expected",
    [
        ("pdflatex", "-pdf"),
        ("xelatex", "-xelatex"),
        ("lualatex", "-lualatex"),
    ],
)
def test_engine_flag_maps_known_engines(engine, expected):
    assert engine_flag(engine) == expected


def test_engine_flag_rejects_unknown_engine():
    with pytest.raises(ValueError):
        engine_flag("dvipdf")
```

- [ ] **Step 2: Run test to verify it fails**
  - Run: `.venv/bin/python -m pytest tests/test_compile_engine_flag.py -q`
  - Expected: FAIL with `ModuleNotFoundError` / `ImportError` (no `overleaf_sync/compile.py` yet, `engine_flag` undefined).

- [ ] **Step 3: Write minimal implementation**
```python
# overleaf_sync/compile.py
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import tex

_ENGINE_FLAGS: dict[str, str] = {
    "pdflatex": "-pdf",
    "xelatex": "-xelatex",
    "lualatex": "-lualatex",
}


def engine_flag(engine: str) -> str:
    """Map a TeX engine name to its latexmk switch."""
    try:
        return _ENGINE_FLAGS[engine]
    except KeyError:
        raise ValueError(
            f"unknown engine {engine!r}; expected one of {sorted(_ENGINE_FLAGS)}"
        ) from None
```

- [ ] **Step 4: Run test to verify it passes**
  - Run: `.venv/bin/python -m pytest tests/test_compile_engine_flag.py -q`
  - Expected: PASS (4 parametrized cases pass).

- [ ] **Step 5: Commit**
  - Run: `git add overleaf_sync/compile.py tests/test_compile_engine_flag.py && git commit -m "compile: engine_flag maps engine names to latexmk switches"`

---

### Task 30: compile.py — `parse_missing_files` + `MISSING_FILE_RE` (real .log snippets, dedup, order-preserving)

**Files:**
- Modify: `overleaf_sync/compile.py`
- Test: `tests/test_compile_parse_missing.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_compile_parse_missing.py
import pytest

from overleaf_sync.compile import parse_missing_files

# Real latexmk/pdflatex .log fragments.
LOG_MISSING_STY = r"""
This is pdfTeX, Version 3.141592653-2.6-1.40.25 (TeX Live 2025)
(./main.tex
LaTeX2e <2024-11-01>
(/usr/local/texlive/2025/texmf-dist/tex/latex/base/article.cls
Document Class: article 2024/06/29 v1.4n Standard LaTeX document class)

! LaTeX Error: File `tikz.sty' not found.

Type X to quit or <RETURN> to proceed,
or enter new name. (Default extension: sty)
"""

LOG_MISSING_CLS = r"""
(./main.tex
LaTeX2e <2024-11-01>

! LaTeX Error: File `IEEEtran.cls' not found.

Type X to quit or <RETURN> to proceed,
or enter new name. (Default extension: cls)
"""

LOG_MISSING_FD = r"""
LaTeX Font Warning: Font shape `OT1/cmbr/m/n' undefined

! Font OT1/cmtt/m/n/10=cmtt10 at 10.0pt not loadable: Metric (TFM) file not foun
d.

! LaTeX Error: File `t1pcr.fd' not found.

Type X to quit or <RETURN> to proceed.
"""

LOG_MULTI_AND_DUP = r"""
! LaTeX Error: File `tikz.sty' not found.

! LaTeX Error: File `pgfplots.sty' not found.

! LaTeX Error: File `tikz.sty' not found.

! LaTeX Error: File `algorithm2e.sty' not found.
"""

LOG_CLEAN = r"""
This is pdfTeX, Version 3.141592653 (TeX Live 2025)
Output written on main.pdf (3 pages, 123456 bytes).
Transcript written on main.log.
"""


@pytest.mark.parametrize(
    "log_text,expected",
    [
        (LOG_MISSING_STY, ["tikz.sty"]),
        (LOG_MISSING_CLS, ["IEEEtran.cls"]),
        (LOG_MISSING_FD, ["t1pcr.fd"]),
        (LOG_MULTI_AND_DUP, ["tikz.sty", "pgfplots.sty", "algorithm2e.sty"]),
        (LOG_CLEAN, []),
    ],
)
def test_parse_missing_files(log_text, expected):
    assert parse_missing_files(log_text) == expected


def test_parse_missing_files_is_order_preserving_and_deduped():
    log = (
        "! LaTeX Error: File `beta.sty' not found.\n"
        "! LaTeX Error: File `alpha.sty' not found.\n"
        "! LaTeX Error: File `beta.sty' not found.\n"
    )
    # first-seen order, no dup of beta.sty
    assert parse_missing_files(log) == ["beta.sty", "alpha.sty"]
```

- [ ] **Step 2: Run test to verify it fails**
  - Run: `.venv/bin/python -m pytest tests/test_compile_parse_missing.py -q`
  - Expected: FAIL with `ImportError: cannot import name 'parse_missing_files'`.

- [ ] **Step 3: Write minimal implementation** (add to `overleaf_sync/compile.py`, after `engine_flag`)
```python
# Patterns that match latexmk/pdflatex "file not found" diagnostics.
# Covers missing .sty (packages), .cls (document classes), and .fd (font defs).
MISSING_FILE_RE: list[re.Pattern] = [
    re.compile(r"! LaTeX Error: File `([^']+\.(?:sty|cls|fd))' not found\."),
    re.compile(r"! LaTeX Error: File `([^']+\.(?:sty|cls|fd))' not found"),
]


def parse_missing_files(log_text: str) -> list[str]:
    """Extract missing TeX input filenames from a latexmk/pdflatex log.

    Returns filenames (e.g. ["tikz.sty", "IEEEtran.cls"]) in first-seen
    order, deduplicated.
    """
    found: list[str] = []
    seen: set[str] = set()
    for pattern in MISSING_FILE_RE:
        for match in pattern.finditer(log_text):
            name = match.group(1)
            if name not in seen:
                seen.add(name)
                found.append(name)
    return found
```

- [ ] **Step 4: Run test to verify it passes**
  - Run: `.venv/bin/python -m pytest tests/test_compile_parse_missing.py -q`
  - Expected: PASS (6 cases: 5 parametrized + 1 order/dedup case).

- [ ] **Step 5: Commit**
  - Run: `git add overleaf_sync/compile.py tests/test_compile_parse_missing.py && git commit -m "compile: parse_missing_files extracts missing sty/cls/fd from logs"`

---

### Task 31: compile.py — `detect_main` + `AmbiguousMainError` (override wins; scan for documentclass+begin{document}; list candidates)

**Files:**
- Modify: `overleaf_sync/compile.py`
- Test: `tests/test_compile_detect_main.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_compile_detect_main.py
import pytest

from overleaf_sync.compile import AmbiguousMainError, detect_main

MAIN_TEX = r"""
\documentclass{article}
\begin{document}
Hello.
\end{document}
"""

PREAMBLE_ONLY = r"""
\documentclass{article}
% no begin document here
"""

SNIPPET = r"""
\section{Intro}
Some text without a documentclass.
"""


def test_detect_main_override_wins(tmp_path):
    (tmp_path / "main.tex").write_text(MAIN_TEX)
    (tmp_path / "other.tex").write_text(MAIN_TEX)
    # override is returned verbatim, no scanning
    assert detect_main(tmp_path, override="other.tex") == "other.tex"


def test_detect_main_single_candidate(tmp_path):
    (tmp_path / "paper.tex").write_text(MAIN_TEX)
    (tmp_path / "section1.tex").write_text(SNIPPET)
    (tmp_path / "preamble.tex").write_text(PREAMBLE_ONLY)
    assert detect_main(tmp_path) == "paper.tex"


def test_detect_main_ambiguous_lists_candidates(tmp_path):
    (tmp_path / "paper.tex").write_text(MAIN_TEX)
    (tmp_path / "poster.tex").write_text(MAIN_TEX)
    with pytest.raises(AmbiguousMainError) as exc:
        detect_main(tmp_path)
    msg = str(exc.value)
    assert "paper.tex" in msg and "poster.tex" in msg


def test_detect_main_no_candidate_raises_ambiguous(tmp_path):
    (tmp_path / "section1.tex").write_text(SNIPPET)
    with pytest.raises(AmbiguousMainError):
        detect_main(tmp_path)
```

- [ ] **Step 2: Run test to verify it fails**
  - Run: `.venv/bin/python -m pytest tests/test_compile_detect_main.py -q`
  - Expected: FAIL with `ImportError: cannot import name 'AmbiguousMainError'` / `detect_main`.

- [ ] **Step 3: Write minimal implementation** (add to `overleaf_sync/compile.py`, after `parse_missing_files`)
```python
class AmbiguousMainError(RuntimeError):
    """Raised when the main .tex file cannot be uniquely determined."""


_DOCUMENTCLASS_RE = re.compile(r"\\documentclass")
_BEGIN_DOCUMENT_RE = re.compile(r"\\begin\{document\}")


def detect_main(repo: str | Path, override: str | None = None) -> str:
    """Determine the main .tex filename for a project.

    Precedence: an explicit ``override`` wins outright. Otherwise scan the
    repo root for .tex files containing both ``\\documentclass`` and
    ``\\begin{document}``; exactly one candidate is the main file. Zero or
    more than one candidate raises :class:`AmbiguousMainError` listing what
    was (or wasn't) found.
    """
    if override is not None:
        return override

    root = Path(repo)
    candidates: list[str] = []
    for tex_path in sorted(root.glob("*.tex")):
        try:
            text = tex_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _DOCUMENTCLASS_RE.search(text) and _BEGIN_DOCUMENT_RE.search(text):
            candidates.append(tex_path.name)

    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise AmbiguousMainError(
            f"no .tex file with \\documentclass and \\begin{{document}} found "
            f"in {root}; specify one with --main"
        )
    raise AmbiguousMainError(
        "multiple main-file candidates: "
        + ", ".join(candidates)
        + "; specify one with --main"
    )
```

- [ ] **Step 4: Run test to verify it passes**
  - Run: `.venv/bin/python -m pytest tests/test_compile_detect_main.py -q`
  - Expected: PASS (4 cases).

- [ ] **Step 5: Commit**
  - Run: `git add overleaf_sync/compile.py tests/test_compile_detect_main.py && git commit -m "compile: detect_main with override + documentclass/begin scan"`

---

### Task 32: compile.py — `run_latexmk` (mock subprocess; reads <main>.log)

**Files:**
- Modify: `overleaf_sync/compile.py`
- Test: `tests/test_compile_run_latexmk.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_compile_run_latexmk.py
from overleaf_sync import compile as cmpl


def test_run_latexmk_invokes_latexmk_with_engine_flag(tmp_path, monkeypatch):
    calls = {}

    def fake_require_tool(name):
        assert name == "latexmk"
        return "/fake/bin/latexmk"

    class FakeCompleted:
        returncode = 0

    def fake_run(argv, cwd=None, **kwargs):
        calls["argv"] = argv
        calls["cwd"] = cwd
        return FakeCompleted()

    monkeypatch.setattr(cmpl.tex, "require_tool", fake_require_tool)
    monkeypatch.setattr(cmpl.subprocess, "run", fake_run)

    # latexmk writes <main>.log into the repo; simulate it.
    (tmp_path / "main.log").write_text("Output written on main.pdf (1 page)")

    rc, log_text = cmpl.run_latexmk(tmp_path, "main.tex", "xelatex")

    assert rc == 0
    assert log_text == "Output written on main.pdf (1 page)"
    argv = calls["argv"]
    assert argv[0] == "/fake/bin/latexmk"
    assert "-xelatex" in argv
    assert "-interaction=nonstopmode" in argv
    assert "-halt-on-error" in argv
    assert argv[-1] == "main.tex"
    assert str(calls["cwd"]) == str(tmp_path)


def test_run_latexmk_returns_returncode_and_missing_log_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(cmpl.tex, "require_tool", lambda name: "/fake/bin/latexmk")

    class FakeCompleted:
        returncode = 12

    monkeypatch.setattr(cmpl.subprocess, "run", lambda *a, **k: FakeCompleted())

    # No main.log written -> log_text should be "" (not crash).
    rc, log_text = cmpl.run_latexmk(tmp_path, "main.tex", "pdflatex")
    assert rc == 12
    assert log_text == ""
```

- [ ] **Step 2: Run test to verify it fails**
  - Run: `.venv/bin/python -m pytest tests/test_compile_run_latexmk.py -q`
  - Expected: FAIL with `AttributeError: module 'overleaf_sync.compile' has no attribute 'run_latexmk'`.

- [ ] **Step 3: Write minimal implementation** (add to `overleaf_sync/compile.py`, after `detect_main`)
```python
def run_latexmk(repo: str | Path, main: str, engine: str) -> tuple[int, str]:
    """Run ``latexmk`` once for ``main`` in ``repo`` and return (rc, log_text).

    The log text is read from ``<main-stem>.log`` in the repo (latexmk's
    transcript); if absent, an empty string is returned.
    """
    root = Path(repo)
    latexmk = tex.require_tool("latexmk")
    argv = [
        latexmk,
        engine_flag(engine),
        "-interaction=nonstopmode",
        "-halt-on-error",
        main,
    ]
    completed = subprocess.run(
        argv,
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    log_path = root / (Path(main).stem + ".log")
    log_text = ""
    if log_path.exists():
        log_text = log_path.read_text(encoding="utf-8", errors="ignore")
    return completed.returncode, log_text
```

- [ ] **Step 4: Run test to verify it passes**
  - Run: `.venv/bin/python -m pytest tests/test_compile_run_latexmk.py -q`
  - Expected: PASS (2 cases).

- [ ] **Step 5: Commit**
  - Run: `git add overleaf_sync/compile.py tests/test_compile_run_latexmk.py && git commit -m "compile: run_latexmk invokes latexmk and reads transcript log"`

---

### Task 33: compile.py — `CompileResult` + `compile_project` (auto-install loop, max_retries cap, auto_install=False path)

**Files:**
- Modify: `overleaf_sync/compile.py`
- Test: `tests/test_compile_project.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_compile_project.py
from overleaf_sync import compile as cmpl
from overleaf_sync.compile import CompileResult

MISSING_TIKZ_LOG = "! LaTeX Error: File `tikz.sty' not found.\n"
CLEAN_LOG = "Output written on main.pdf (1 page, 1234 bytes).\n"


def test_compile_succeeds_first_try_no_install(tmp_path, monkeypatch):
    (tmp_path / "main.pdf").write_bytes(b"%PDF-1.5\n")
    monkeypatch.setattr(cmpl, "run_latexmk", lambda repo, main, engine: (0, CLEAN_LOG))

    installed_calls = []
    monkeypatch.setattr(cmpl.tex, "tlmgr_install", lambda pkgs: installed_calls.append(pkgs))
    monkeypatch.setattr(cmpl.tex, "tlmgr_search_file", lambda f: [])

    result = cmpl.compile_project(tmp_path, "main.tex", engine="pdflatex")

    assert isinstance(result, CompileResult)
    assert result.ok is True
    assert result.installed == []
    assert result.pdf_path == str(tmp_path / "main.pdf")
    assert installed_calls == []  # nothing installed on clean success


def test_compile_installs_missing_pkg_then_retries_and_succeeds(tmp_path, monkeypatch):
    # 1st run fails with missing tikz.sty; 2nd run succeeds.
    runs = iter([(12, MISSING_TIKZ_LOG), (0, CLEAN_LOG)])
    monkeypatch.setattr(cmpl, "run_latexmk", lambda repo, main, engine: next(runs))

    searched = []
    installed = []
    monkeypatch.setattr(cmpl.tex, "tlmgr_search_file", lambda f: (searched.append(f) or ["pgf"]))
    monkeypatch.setattr(cmpl.tex, "tlmgr_install", lambda pkgs: installed.append(list(pkgs)))

    (tmp_path / "main.pdf").write_bytes(b"%PDF-1.5\n")

    result = cmpl.compile_project(tmp_path, "main.tex", engine="pdflatex", auto_install=True)

    assert result.ok is True
    assert searched == ["tikz.sty"]
    assert installed == [["pgf"]]
    assert result.installed == ["pgf"]
    assert result.pdf_path == str(tmp_path / "main.pdf")


def test_compile_respects_max_retries_cap(tmp_path, monkeypatch):
    # Always fails with the same missing package -> never converges.
    monkeypatch.setattr(cmpl, "run_latexmk", lambda repo, main, engine: (12, MISSING_TIKZ_LOG))

    run_count = {"n": 0}
    real_run = cmpl.run_latexmk

    def counting_run(repo, main, engine):
        run_count["n"] += 1
        return (12, MISSING_TIKZ_LOG)

    monkeypatch.setattr(cmpl, "run_latexmk", counting_run)
    monkeypatch.setattr(cmpl.tex, "tlmgr_search_file", lambda f: ["pgf"])
    monkeypatch.setattr(cmpl.tex, "tlmgr_install", lambda pkgs: None)

    result = cmpl.compile_project(tmp_path, "main.tex", auto_install=True, max_retries=3)

    assert result.ok is False
    # initial attempt + up to max_retries retries == max_retries + 1 latexmk runs
    assert run_count["n"] == 4
    assert result.pdf_path is None
    assert MISSING_TIKZ_LOG.strip() in result.log_tail


def test_compile_no_auto_install_does_not_install(tmp_path, monkeypatch):
    monkeypatch.setattr(cmpl, "run_latexmk", lambda repo, main, engine: (12, MISSING_TIKZ_LOG))

    install_calls = []
    search_calls = []
    monkeypatch.setattr(cmpl.tex, "tlmgr_install", lambda pkgs: install_calls.append(pkgs))
    monkeypatch.setattr(cmpl.tex, "tlmgr_search_file", lambda f: search_calls.append(f) or [])

    result = cmpl.compile_project(tmp_path, "main.tex", auto_install=False)

    assert result.ok is False
    assert install_calls == []  # no install attempts
    assert search_calls == []   # no search either when auto_install off
    assert result.installed == []
    assert result.pdf_path is None
    assert MISSING_TIKZ_LOG.strip() in result.log_tail
```

- [ ] **Step 2: Run test to verify it fails**
  - Run: `.venv/bin/python -m pytest tests/test_compile_project.py -q`
  - Expected: FAIL with `ImportError: cannot import name 'CompileResult'` / no attribute `compile_project`.

- [ ] **Step 3: Write minimal implementation** (add `CompileResult` near top of `overleaf_sync/compile.py` and `compile_project` at the end)
```python
@dataclass
class CompileResult:
    ok: bool
    pdf_path: str | None
    installed: list[str] = field(default_factory=list)
    log_tail: str = ""


def _log_tail(log_text: str, lines: int = 40) -> str:
    """Return the last ``lines`` lines of a log, for user-facing diagnostics."""
    return "\n".join(log_text.splitlines()[-lines:])


def compile_project(
    repo: str | Path,
    main: str,
    engine: str = "pdflatex",
    auto_install: bool = True,
    max_retries: int = 5,
) -> CompileResult:
    """Compile ``main`` with latexmk, auto-installing missing packages.

    Loop: run latexmk; on failure, if ``auto_install`` is on, parse the log
    for missing files, resolve each to a TeX Live package via
    ``tex.tlmgr_search_file`` and install via ``tex.tlmgr_install``, then
    retry. At most ``max_retries`` retries follow the initial attempt; if the
    set of missing packages cannot be reduced (search yields nothing new) or
    the cap is hit, give up and surface the log tail.
    """
    root = Path(repo)
    installed: list[str] = []
    pdf_path = root / (Path(main).stem + ".pdf")

    attempts = 0
    last_log = ""
    while True:
        rc, log_text = run_latexmk(root, main, engine)
        last_log = log_text
        attempts += 1

        if rc == 0:
            return CompileResult(
                ok=True,
                pdf_path=str(pdf_path) if pdf_path.exists() else None,
                installed=installed,
                log_tail=_log_tail(log_text),
            )

        if not auto_install or attempts > max_retries:
            return CompileResult(
                ok=False,
                pdf_path=None,
                installed=installed,
                log_tail=_log_tail(log_text),
            )

        missing = parse_missing_files(log_text)
        newly_installed: list[str] = []
        for filename in missing:
            for pkg in tex.tlmgr_search_file(filename):
                if pkg not in installed and pkg not in newly_installed:
                    newly_installed.append(pkg)

        if not newly_installed:
            # Nothing actionable left to install -> stop to avoid a dead loop.
            return CompileResult(
                ok=False,
                pdf_path=None,
                installed=installed,
                log_tail=_log_tail(log_text),
            )

        tex.tlmgr_install(newly_installed)
        installed.extend(newly_installed)
```

- [ ] **Step 4: Run test to verify it passes**
  - Run: `.venv/bin/python -m pytest tests/test_compile_project.py -q`
  - Expected: PASS (4 cases). Note: the `max_retries=3` case expects exactly 4 latexmk runs (1 initial + 3 retries) because `tlmgr_search_file` always returns the not-yet-installed `pgf` on the first retry but `pgf` is recorded as installed thereafter — verify the loop terminates via the `attempts > max_retries` cap, not the "nothing new" guard.

- [ ] **Step 5: Commit**
  - Run: `git add overleaf_sync/compile.py tests/test_compile_project.py && git commit -m "compile: compile_project auto-install loop with max_retries cap"`

---

### Task 34: compile.py — full-module test run (regression gate before moving to cli)

**Files:**
- Test: (no new file) run all `tests/test_compile_*.py`

- [ ] **Step 1: Write the failing test** — N/A (aggregation step; no new test, gate on the 4 suites above).
- [ ] **Step 2: Run test to verify it fails** — N/A.
- [ ] **Step 3: Write minimal implementation** — N/A (no code change; this task only confirms the module is internally consistent).
- [ ] **Step 4: Run all compile tests to verify they pass**
  - Run: `.venv/bin/python -m pytest tests/test_compile_engine_flag.py tests/test_compile_parse_missing.py tests/test_compile_detect_main.py tests/test_compile_run_latexmk.py tests/test_compile_project.py -q`
  - Expected: PASS (all compile.py suites green; `engine_flag`, `parse_missing_files`, `detect_main`, `run_latexmk`, `compile_project` all exercised).
- [ ] **Step 5: Commit** — N/A (nothing new to commit; proceed to cli.py tasks).

## Group 7 — cli.py


### Task 35: cli.py scaffold — click group `main` and `--version`

**Files:**
- Create: `overleaf_sync/cli.py`
- Test: `tests/test_cli_scaffold.py`

- [ ] **Step 1: Write the failing test**
```python
from click.testing import CliRunner

from overleaf_sync.cli import main


def test_main_is_a_group_with_subcommands():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    for cmd in [
        "login", "clone", "register", "list",
        "sync", "pull", "push", "status", "open", "compile",
    ]:
        assert cmd in result.output


def test_main_reports_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output
```

- [ ] **Step 2: Run test to verify it fails** (Run: `.venv/bin/python -m pytest tests/test_cli_scaffold.py -q`; Expected: FAIL with `ImportError`/`ModuleNotFoundError` — `overleaf_sync/cli.py` does not yet exist)

- [ ] **Step 3: Write minimal implementation**
```python
from __future__ import annotations

import os
import subprocess
from datetime import datetime
from getpass import getpass
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from . import __version__
from . import auth, compile as compile_mod, gitops, registry
from .registry import Project

console = Console()
err_console = Console(stderr=True)


@click.group()
@click.version_option(__version__, prog_name="overleaf")
def main() -> None:
    """Overleaf 本地同步 CLI：本地 VSCode 编辑 + git 双向同步 + 本地编译。"""
```

- [ ] **Step 4: Run test to verify it passes** (Run: `.venv/bin/python -m pytest tests/test_cli_scaffold.py -q`; Expected: PASS — group exists but has no subcommands yet, so the subcommand-name assertions will still fail. NOTE: this step only asserts `test_main_reports_version` passes; `test_main_is_a_group_with_subcommands` is expected to keep failing until later tasks register the commands. Run only the version test: `.venv/bin/python -m pytest tests/test_cli_scaffold.py::test_main_reports_version -q`; Expected: PASS)

- [ ] **Step 5: Commit** (Run: `git add overleaf_sync/cli.py tests/test_cli_scaffold.py && git commit -m "feat(cli): scaffold click group main with --version"`)

---

### Task 36: `overleaf login` — token via getpass or stdin

**Files:**
- Modify: `overleaf_sync/cli.py`
- Test: `tests/test_cli_login.py`

- [ ] **Step 1: Write the failing test**
```python
from click.testing import CliRunner

import overleaf_sync.cli as cli_mod
from overleaf_sync.cli import main


def test_login_token_via_stdin(monkeypatch):
    calls = {}

    monkeypatch.setattr(cli_mod.auth, "ensure_credential_helper",
                        lambda: calls.setdefault("ensure", True))

    def fake_store(token, host="git.overleaf.com", username="git"):
        calls["token"] = token
        calls["host"] = host

    monkeypatch.setattr(cli_mod.auth, "store_token", fake_store)

    runner = CliRunner()
    result = runner.invoke(main, ["login", "--token-stdin"], input="olp_secret123\n")

    assert result.exit_code == 0
    assert calls["ensure"] is True
    assert calls["token"] == "olp_secret123"
    assert calls["host"] == "git.overleaf.com"
    # token must never be echoed
    assert "olp_secret123" not in result.output


def test_login_token_via_getpass_and_host_override(monkeypatch):
    calls = {}
    monkeypatch.setattr(cli_mod.auth, "ensure_credential_helper", lambda: None)
    monkeypatch.setattr(cli_mod.auth, "store_token",
                        lambda token, host="git.overleaf.com", username="git": calls.update(token=token, host=host))
    monkeypatch.setattr(cli_mod, "getpass", lambda prompt="": "olp_fromprompt")

    runner = CliRunner()
    result = runner.invoke(main, ["login", "--host", "git.example.com"])

    assert result.exit_code == 0
    assert calls["token"] == "olp_fromprompt"
    assert calls["host"] == "git.example.com"
    assert "olp_fromprompt" not in result.output
```

- [ ] **Step 2: Run test to verify it fails** (Run: `.venv/bin/python -m pytest tests/test_cli_login.py -q`; Expected: FAIL — `main` has no `login` command (`No such command 'login'`))

- [ ] **Step 3: Write minimal implementation** (append to `overleaf_sync/cli.py`)
```python
@main.command()
@click.option("--host", default=auth.DEFAULT_HOST, show_default=True,
              help="Overleaf git 主机名。")
@click.option("--token-stdin", "token_stdin", is_flag=True,
              help="从 stdin 读取 token（适合管道）。")
def login(host: str, token_stdin: bool) -> None:
    """读取 Overleaf git token 并存入 macOS Keychain（绝不落盘）。"""
    auth.ensure_credential_helper()
    if token_stdin:
        token = click.get_text_stream("stdin").readline().strip()
    else:
        token = getpass("Overleaf git token: ").strip()
    if not token:
        err_console.print("[red]token 为空，已取消。[/red]")
        raise SystemExit(1)
    auth.store_token(token, host=host)
    console.print(f"[green]已为 {host} 存入凭据（Keychain）。[/green]")
```

- [ ] **Step 4: Run test to verify it passes** (Run: `.venv/bin/python -m pytest tests/test_cli_login.py -q`; Expected: PASS)

- [ ] **Step 5: Commit** (Run: `git add overleaf_sync/cli.py tests/test_cli_login.py && git commit -m "feat(cli): add login command (getpass/stdin token, no echo)"`)

---

### Task 37: `overleaf clone` — git clone + register

**Files:**
- Modify: `overleaf_sync/cli.py`
- Test: `tests/test_cli_clone.py`

- [ ] **Step 1: Write the failing test**
```python
from pathlib import Path

from click.testing import CliRunner

import overleaf_sync.cli as cli_mod
from overleaf_sync.cli import main
from overleaf_sync.registry import Project


def test_clone_default_path_and_registers(monkeypatch, tmp_path):
    clone_calls = {}
    added = {}

    monkeypatch.setattr(cli_mod.gitops, "clone",
                        lambda url, dest: clone_calls.update(url=url, dest=str(dest)))
    monkeypatch.setattr(cli_mod.registry, "add_project",
                        lambda project: added.update(project=project))
    # default dest is ~/overleaf/<alias>; redirect HOME so the test is hermetic
    monkeypatch.setattr(cli_mod.Path, "home", staticmethod(lambda: tmp_path))

    runner = CliRunner()
    result = runner.invoke(
        main, ["clone", "https://git.overleaf.com/PID", "mypaper"])

    assert result.exit_code == 0, result.output
    expected_dest = tmp_path / "overleaf" / "mypaper"
    assert clone_calls["url"] == "https://git.overleaf.com/PID"
    assert clone_calls["dest"] == str(expected_dest)
    proj = added["project"]
    assert isinstance(proj, Project)
    assert proj.alias == "mypaper"
    assert proj.remote == "https://git.overleaf.com/PID"
    assert proj.path == str(expected_dest)


def test_clone_custom_path(monkeypatch, tmp_path):
    added = {}
    monkeypatch.setattr(cli_mod.gitops, "clone", lambda url, dest: None)
    monkeypatch.setattr(cli_mod.registry, "add_project",
                        lambda project: added.update(project=project))

    dest = tmp_path / "custom"
    runner = CliRunner()
    result = runner.invoke(
        main, ["clone", "https://git.overleaf.com/PID", "mypaper", "--path", str(dest)])

    assert result.exit_code == 0, result.output
    assert added["project"].path == str(dest)
```

- [ ] **Step 2: Run test to verify it fails** (Run: `.venv/bin/python -m pytest tests/test_cli_clone.py -q`; Expected: FAIL — `No such command 'clone'`)

- [ ] **Step 3: Write minimal implementation** (append to `overleaf_sync/cli.py`)
```python
@main.command()
@click.argument("url")
@click.argument("alias")
@click.option("--path", "dest", type=click.Path(file_okay=False),
              default=None, help="克隆目标目录，默认 ~/overleaf/<别名>。")
def clone(url: str, alias: str, dest: str | None) -> None:
    """克隆 Overleaf 项目到本地并登记到 registry。"""
    target = Path(dest) if dest else Path.home() / "overleaf" / alias
    gitops.clone(url, target)
    registry.add_project(Project(alias=alias, path=str(target), remote=url))
    console.print(f"[green]已克隆 {alias} -> {target}[/green]")
```

- [ ] **Step 4: Run test to verify it passes** (Run: `.venv/bin/python -m pytest tests/test_cli_clone.py -q`; Expected: PASS)

- [ ] **Step 5: Commit** (Run: `git add overleaf_sync/cli.py tests/test_cli_clone.py && git commit -m "feat(cli): add clone command (git clone + registry)"`)

---

### Task 38: `overleaf register` — validate git repo + overleaf remote

**Files:**
- Modify: `overleaf_sync/cli.py`
- Test: `tests/test_cli_register.py`

- [ ] **Step 1: Write the failing test**
```python
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
```

- [ ] **Step 2: Run test to verify it fails** (Run: `.venv/bin/python -m pytest tests/test_cli_register.py -q`; Expected: FAIL — `No such command 'register'`)

- [ ] **Step 3: Write minimal implementation** (append to `overleaf_sync/cli.py`)
```python
@main.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False))
@click.argument("alias")
def register(path: str, alias: str) -> None:
    """把已有的本地 Overleaf git 仓库登记到 registry。"""
    if not gitops.is_git_repo(path):
        err_console.print(f"[red]{path} 不是 git 仓库，无法登记。[/red]")
        raise SystemExit(1)
    remote = gitops.get_remote_url(path)
    if not remote or "overleaf.com" not in remote:
        err_console.print(
            f"[red]remote 不是 Overleaf（{remote or '无 remote'}），拒绝登记。[/red]")
        raise SystemExit(1)
    registry.add_project(Project(alias=alias, path=str(path), remote=remote))
    console.print(f"[green]已登记 {alias} -> {path}[/green]")
```

- [ ] **Step 4: Run test to verify it passes** (Run: `.venv/bin/python -m pytest tests/test_cli_register.py -q`; Expected: PASS)

- [ ] **Step 5: Commit** (Run: `git add overleaf_sync/cli.py tests/test_cli_register.py && git commit -m "feat(cli): add register command (validate git + overleaf remote)"`)

---

### Task 39: `overleaf list` — rich table from registry + per-project status

**Files:**
- Modify: `overleaf_sync/cli.py`
- Test: `tests/test_cli_list.py`

- [ ] **Step 1: Write the failing test**
```python
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
```

- [ ] **Step 2: Run test to verify it fails** (Run: `.venv/bin/python -m pytest tests/test_cli_list.py -q`; Expected: FAIL — `No such command 'list'`)

- [ ] **Step 3: Write minimal implementation** (append to `overleaf_sync/cli.py`)
```python
@main.command(name="list")
def list_cmd() -> None:
    """列出所有已登记项目及其状态。"""
    projects = registry.list_projects()
    if not projects:
        console.print("[yellow]registry 为空，先 overleaf clone/register。[/yellow]")
        return
    table = Table(title="overleaf projects")
    table.add_column("别名", style="cyan")
    table.add_column("路径")
    table.add_column("远端")
    table.add_column("状态")
    for proj in projects:
        try:
            st = gitops.get_status(proj.path)
            state = "dirty" if st.dirty else "clean"
            if st.ahead:
                state += f" ↑{st.ahead}"
            if st.behind:
                state += f" ↓{st.behind}"
        except Exception:
            state = "?"
        table.add_row(proj.alias, proj.path, proj.remote, state)
    console.print(table)
```

- [ ] **Step 4: Run test to verify it passes** (Run: `.venv/bin/python -m pytest tests/test_cli_list.py -q`; Expected: PASS)

- [ ] **Step 5: Commit** (Run: `git add overleaf_sync/cli.py tests/test_cli_list.py && git commit -m "feat(cli): add list command (rich table + per-project status)"`)

---

### Task 40: `overleaf sync` — rebase-continue path (continue then push)

**Files:**
- Modify: `overleaf_sync/cli.py`
- Test: `tests/test_cli_sync.py`

- [ ] **Step 1: Write the failing test**
```python
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
    assert "overleaf sync" in result.output
```

- [ ] **Step 2: Run test to verify it fails** (Run: `.venv/bin/python -m pytest tests/test_cli_sync.py -q`; Expected: FAIL — `No such command 'sync'`)

- [ ] **Step 3: Write minimal implementation** (append to `overleaf_sync/cli.py`)
```python
@main.command()
@click.argument("alias")
@click.option("--no-commit", "no_commit", is_flag=True,
              help="不自动提交（脏工作区时拒绝执行）。")
@click.option("--message", "message", default=None, help="自定义提交信息。")
def sync(alias: str, no_commit: bool, message: str | None) -> None:
    """核心：auto-commit → pull --rebase → push；冲突永远停下让用户解决。"""
    proj = registry.get_project(alias)
    repo = proj.path

    # Step 1: unfinished rebase -> continue mode
    if gitops.rebase_in_progress(repo):
        unmerged = gitops.unmerged_files(repo)
        if unmerged:
            err_console.print("[red]仍有未解决冲突：[/red]")
            for f in unmerged:
                err_console.print(f"  - {f}")
            err_console.print(
                f"[yellow]在 VSCode 解决后重跑 overleaf sync {alias}[/yellow]")
            raise SystemExit(1)
        gitops.rebase_continue(repo)
        _finish_push(repo)
        return

    # Step 2: commit
    status = gitops.get_status(repo)
    if status.dirty:
        if no_commit:
            err_console.print("[red]工作区有改动，--no-commit 模式下请先 git commit/stash。[/red]")
            raise SystemExit(1)
        msg = message or f"overleaf-sync: {datetime.now().astimezone().isoformat()}"
        gitops.auto_commit(repo, msg)

    # Step 3: pull --rebase
    r = gitops.pull_rebase(repo)
    if r.conflict:
        err_console.print("[red]pull --rebase 冲突，已保留现场（未 abort）：[/red]")
        for f in gitops.unmerged_files(repo):
            err_console.print(f"  - {f}")
        err_console.print(
            f"[yellow]在 VSCode 解决后重跑 overleaf sync {alias}[/yellow]")
        raise SystemExit(1)

    # Step 4: push
    _finish_push(repo)


def _finish_push(repo: str) -> None:
    summary = gitops.push(repo)
    console.print(f"[green]同步完成：{summary}[/green]")
```

- [ ] **Step 4: Run test to verify it passes** (Run: `.venv/bin/python -m pytest tests/test_cli_sync.py -q`; Expected: PASS)

- [ ] **Step 5: Commit** (Run: `git add overleaf_sync/cli.py tests/test_cli_sync.py && git commit -m "feat(cli): add sync command — rebase-continue path"`)

---

### Task 41: `overleaf sync` — dirty → auto_commit → pull → push happy path

**Files:**
- Modify: `tests/test_cli_sync.py`
- Test: `tests/test_cli_sync.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_cli_sync.py`)
```python
def test_sync_dirty_commits_pulls_pushes(monkeypatch):
    _stub_resolve(monkeypatch)
    order = []
    monkeypatch.setattr(cli_mod.gitops, "rebase_in_progress", lambda repo: False)
    monkeypatch.setattr(cli_mod.gitops, "get_status",
                        lambda repo: RepoStatus(dirty=True, ahead=0, behind=0,
                                                conflicts=[], rebase_in_progress=False))

    def fake_commit(repo, message):
        order.append(("commit", message))
        assert message.startswith("overleaf-sync: ")
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
```

- [ ] **Step 2: Run test to verify it fails** (Run: `.venv/bin/python -m pytest tests/test_cli_sync.py -k "dirty_commits or custom_message or clean_skips" -q`; Expected: PASS for all three since Task 40 already implemented the full algorithm. NOTE: if any fails, the algorithm in `sync` is wrong — fix `cli.py`, not the test. These tests lock in the happy-path branch ordering.)

- [ ] **Step 3: Write minimal implementation** (no new code needed — Task 40 implemented the dirty→commit→pull→push branch. If a test fails, correct `sync`/`_finish_push` in `overleaf_sync/cli.py` to satisfy the asserted ordering.)

- [ ] **Step 4: Run test to verify it passes** (Run: `.venv/bin/python -m pytest tests/test_cli_sync.py -q`; Expected: PASS — all sync tests so far)

- [ ] **Step 5: Commit** (Run: `git add tests/test_cli_sync.py && git commit -m "test(cli): lock sync happy path (commit->pull->push, custom msg, clean skip)"`)

---

### Task 42: `overleaf sync` — pull conflict exit 1 & `--no-commit`+dirty refusal

**Files:**
- Modify: `tests/test_cli_sync.py`
- Test: `tests/test_cli_sync.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_cli_sync.py`)
```python
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
    assert "overleaf sync" in result.output


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
```

- [ ] **Step 2: Run test to verify it fails** (Run: `.venv/bin/python -m pytest tests/test_cli_sync.py -k "pull_conflict or no_commit" -q`; Expected: PASS if Task 40's algorithm is complete and correct. If `test_sync_no_commit_with_dirty_refuses` or `test_sync_pull_conflict_exits_1_without_abort` FAILS, the conflict/refusal branches in `sync` are wrong — fix `cli.py`.)

- [ ] **Step 3: Write minimal implementation** (no new code expected — Task 40 already implemented the conflict-exit-1 and `--no-commit`+dirty refusal branches. If a test fails, correct the relevant branch in `sync` in `overleaf_sync/cli.py`.)

- [ ] **Step 4: Run test to verify it passes** (Run: `.venv/bin/python -m pytest tests/test_cli_sync.py -q`; Expected: PASS — entire sync suite green)

- [ ] **Step 5: Commit** (Run: `git add tests/test_cli_sync.py && git commit -m "test(cli): lock sync conflict-exit-1 and --no-commit dirty refusal"`)

---

### Task 43: `overleaf pull` / `overleaf push`

**Files:**
- Modify: `overleaf_sync/cli.py`
- Test: `tests/test_cli_pull_push.py`

- [ ] **Step 1: Write the failing test**
```python
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
```

- [ ] **Step 2: Run test to verify it fails** (Run: `.venv/bin/python -m pytest tests/test_cli_pull_push.py -q`; Expected: FAIL — `No such command 'pull'`)

- [ ] **Step 3: Write minimal implementation** (append to `overleaf_sync/cli.py`)
```python
@main.command()
@click.argument("alias")
def pull(alias: str) -> None:
    """git pull --rebase（冲突时停下让用户解决）。"""
    repo = registry.get_project(alias).path
    r = gitops.pull_rebase(repo)
    if r.conflict:
        err_console.print("[red]pull --rebase 冲突，已保留现场：[/red]")
        for f in gitops.unmerged_files(repo):
            err_console.print(f"  - {f}")
        err_console.print(f"[yellow]解决后重跑 overleaf sync {alias}[/yellow]")
        raise SystemExit(1)
    console.print(r.output)


@main.command()
@click.argument("alias")
def push(alias: str) -> None:
    """git push。"""
    repo = registry.get_project(alias).path
    try:
        summary = gitops.push(repo)
    except gitops.GitError as exc:
        err_console.print(f"[red]push 失败：{exc}[/red]")
        raise SystemExit(1)
    console.print(summary)
```

- [ ] **Step 4: Run test to verify it passes** (Run: `.venv/bin/python -m pytest tests/test_cli_pull_push.py -q`; Expected: PASS)

- [ ] **Step 5: Commit** (Run: `git add overleaf_sync/cli.py tests/test_cli_pull_push.py && git commit -m "feat(cli): add pull and push commands"`)

---

### Task 44: `overleaf status` — pretty-print RepoStatus

**Files:**
- Modify: `overleaf_sync/cli.py`
- Test: `tests/test_cli_status.py`

- [ ] **Step 1: Write the failing test**
```python
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
```

- [ ] **Step 2: Run test to verify it fails** (Run: `.venv/bin/python -m pytest tests/test_cli_status.py -q`; Expected: FAIL — `No such command 'status'`)

- [ ] **Step 3: Write minimal implementation** (append to `overleaf_sync/cli.py`)
```python
@main.command()
@click.argument("alias")
def status(alias: str) -> None:
    """打印工作区状态：dirty/clean、ahead/behind、冲突文件、rebase 进行中。"""
    proj = registry.get_project(alias)
    st = gitops.get_status(proj.path)
    console.print(f"[cyan]{proj.alias}[/cyan]  {proj.path}")
    console.print(f"  工作区: {'dirty' if st.dirty else 'clean'}")
    console.print(f"  ahead: {st.ahead}  behind: {st.behind}")
    if st.rebase_in_progress:
        console.print("  [yellow]rebase 进行中[/yellow]")
    if st.conflicts:
        console.print("  [red]冲突文件:[/red]")
        for f in st.conflicts:
            console.print(f"    - {f}")
```

- [ ] **Step 4: Run test to verify it passes** (Run: `.venv/bin/python -m pytest tests/test_cli_status.py -q`; Expected: PASS)

- [ ] **Step 5: Commit** (Run: `git add overleaf_sync/cli.py tests/test_cli_status.py && git commit -m "feat(cli): add status command (pretty-print RepoStatus)"`)

---

### Task 45: `overleaf open` — launch VSCode

**Files:**
- Modify: `overleaf_sync/cli.py`
- Test: `tests/test_cli_open.py`

- [ ] **Step 1: Write the failing test**
```python
from click.testing import CliRunner

import overleaf_sync.cli as cli_mod
from overleaf_sync.cli import main
from overleaf_sync.registry import Project


def _stub_resolve(monkeypatch, path="/repo/path"):
    monkeypatch.setattr(
        cli_mod.registry, "get_project",
        lambda alias: Project(alias=alias, path=path,
                              remote="https://git.overleaf.com/PID"))


def test_open_invokes_code(monkeypatch):
    _stub_resolve(monkeypatch, path="/repo/path")
    captured = {}
    monkeypatch.setattr(cli_mod.subprocess, "run",
                        lambda args, **kw: captured.update(args=args))
    runner = CliRunner()
    result = runner.invoke(main, ["open", "mypaper"])
    assert result.exit_code == 0, result.output
    assert captured["args"] == ["code", "/repo/path"]
```

- [ ] **Step 2: Run test to verify it fails** (Run: `.venv/bin/python -m pytest tests/test_cli_open.py -q`; Expected: FAIL — `No such command 'open'`)

- [ ] **Step 3: Write minimal implementation** (append to `overleaf_sync/cli.py`)
```python
@main.command(name="open")
@click.argument("alias")
def open_cmd(alias: str) -> None:
    """用 VSCode 打开项目目录（code <path>）。"""
    repo = registry.get_project(alias).path
    subprocess.run(["code", repo])
    console.print(f"[green]已用 VSCode 打开 {repo}[/green]")
```

- [ ] **Step 4: Run test to verify it passes** (Run: `.venv/bin/python -m pytest tests/test_cli_open.py -q`; Expected: PASS)

- [ ] **Step 5: Commit** (Run: `git add overleaf_sync/cli.py tests/test_cli_open.py && git commit -m "feat(cli): add open command (code <path>)"`)

---

### Task 46: `overleaf compile` — resolve registry main/engine, compile, `--open`

**Files:**
- Modify: `overleaf_sync/cli.py`
- Test: `tests/test_cli_compile.py`

- [ ] **Step 1: Write the failing test**
```python
from click.testing import CliRunner

import overleaf_sync.cli as cli_mod
from overleaf_sync.cli import main
from overleaf_sync.compile import CompileResult
from overleaf_sync.registry import Project


def _stub_resolve(monkeypatch, path="/repo", main_tex=None, engine=None):
    monkeypatch.setattr(
        cli_mod.registry, "get_project",
        lambda alias: Project(alias=alias, path=path,
                              remote="https://git.overleaf.com/PID",
                              main=main_tex, engine=engine))


def test_compile_uses_registry_main_and_engine(monkeypatch):
    _stub_resolve(monkeypatch, path="/repo", main_tex="paper.tex", engine="xelatex")
    captured = {}

    def fake_detect(repo, override=None):
        captured["detect_override"] = override
        return override or "auto.tex"

    def fake_compile(repo, main, engine="pdflatex", auto_install=True, max_retries=5):
        captured.update(repo=str(repo), main=main, engine=engine, auto_install=auto_install)
        return CompileResult(ok=True, pdf_path="/repo/paper.pdf", installed=[], log_tail="")

    monkeypatch.setattr(cli_mod.compile_mod, "detect_main", fake_detect)
    monkeypatch.setattr(cli_mod.compile_mod, "compile_project", fake_compile)

    runner = CliRunner()
    result = runner.invoke(main, ["compile", "mypaper"])

    assert result.exit_code == 0, result.output
    # registry main feeds detect_main as override; registry engine is used
    assert captured["detect_override"] == "paper.tex"
    assert captured["main"] == "paper.tex"
    assert captured["engine"] == "xelatex"
    assert captured["auto_install"] is True
    assert "/repo/paper.pdf" in result.output


def test_compile_flags_override_registry_and_no_auto_install(monkeypatch):
    _stub_resolve(monkeypatch, path="/repo", main_tex="paper.tex", engine="xelatex")
    captured = {}
    monkeypatch.setattr(cli_mod.compile_mod, "detect_main",
                        lambda repo, override=None: override)
    monkeypatch.setattr(
        cli_mod.compile_mod, "compile_project",
        lambda repo, main, engine="pdflatex", auto_install=True, max_retries=5:
            captured.update(main=main, engine=engine, auto_install=auto_install)
            or CompileResult(ok=True, pdf_path="/repo/m.pdf", installed=[], log_tail=""))

    runner = CliRunner()
    result = runner.invoke(
        main, ["compile", "mypaper", "--main", "m.tex",
               "--engine", "lualatex", "--no-auto-install"])

    assert result.exit_code == 0, result.output
    assert captured["main"] == "m.tex"
    assert captured["engine"] == "lualatex"
    assert captured["auto_install"] is False


def test_compile_open_opens_pdf(monkeypatch):
    _stub_resolve(monkeypatch, path="/repo", main_tex="paper.tex", engine=None)
    opened = {}
    monkeypatch.setattr(cli_mod.compile_mod, "detect_main",
                        lambda repo, override=None: override or "paper.tex")
    monkeypatch.setattr(
        cli_mod.compile_mod, "compile_project",
        lambda repo, main, engine="pdflatex", auto_install=True, max_retries=5:
            CompileResult(ok=True, pdf_path="/repo/paper.pdf", installed=["tikz"], log_tail=""))
    monkeypatch.setattr(cli_mod.subprocess, "run",
                        lambda args, **kw: opened.update(args=args))

    runner = CliRunner()
    result = runner.invoke(main, ["compile", "mypaper", "--open"])

    assert result.exit_code == 0, result.output
    # default engine when registry engine is None
    assert opened["args"] == ["open", "/repo/paper.pdf"]
    assert "tikz" in result.output


def test_compile_failure_exits_1_and_prints_log(monkeypatch):
    _stub_resolve(monkeypatch, path="/repo", main_tex="paper.tex", engine=None)
    monkeypatch.setattr(cli_mod.compile_mod, "detect_main",
                        lambda repo, override=None: override or "paper.tex")
    monkeypatch.setattr(
        cli_mod.compile_mod, "compile_project",
        lambda repo, main, engine="pdflatex", auto_install=True, max_retries=5:
            CompileResult(ok=False, pdf_path=None, installed=[],
                          log_tail="! Undefined control sequence."))
    runner = CliRunner()
    result = runner.invoke(main, ["compile", "mypaper"])
    assert result.exit_code == 1
    assert "Undefined control sequence" in result.output
```

- [ ] **Step 2: Run test to verify it fails** (Run: `.venv/bin/python -m pytest tests/test_cli_compile.py -q`; Expected: FAIL — `No such command 'compile'`)

- [ ] **Step 3: Write minimal implementation** (append to `overleaf_sync/cli.py`)
```python
@main.command(name="compile")
@click.argument("alias")
@click.option("--main", "main_override", default=None, help="主文件，覆盖 registry。")
@click.option("--engine", "engine_override", default=None,
              help="引擎 pdflatex|xelatex|lualatex，覆盖 registry。")
@click.option("--open", "open_pdf", is_flag=True, help="编译成功后打开 PDF。")
@click.option("--no-auto-install", "no_auto_install", is_flag=True,
              help="关闭缺包自动补。")
def compile_cmd(alias: str, main_override: str | None, engine_override: str | None,
                open_pdf: bool, no_auto_install: bool) -> None:
    """本地 latexmk 编译（缺包自动补），可选 --open 打开 PDF。"""
    proj = registry.get_project(alias)
    main_tex = compile_mod.detect_main(proj.path, override=main_override or proj.main)
    engine = engine_override or proj.engine or "pdflatex"
    result = compile_mod.compile_project(
        proj.path, main_tex, engine=engine, auto_install=not no_auto_install)
    if result.installed:
        console.print(f"[cyan]自动安装：{', '.join(result.installed)}[/cyan]")
    if not result.ok:
        err_console.print("[red]编译失败，日志末尾：[/red]")
        err_console.print(result.log_tail)
        raise SystemExit(1)
    console.print(f"[green]编译成功：{result.pdf_path}[/green]")
    if open_pdf and result.pdf_path:
        subprocess.run(["open", result.pdf_path])
```

- [ ] **Step 4: Run test to verify it passes** (Run: `.venv/bin/python -m pytest tests/test_cli_compile.py -q`; Expected: PASS)

- [ ] **Step 5: Commit** (Run: `git add overleaf_sync/cli.py tests/test_cli_compile.py && git commit -m "feat(cli): add compile command (resolve main/engine, auto-install, --open)"`)

---

### Task 47: `overleaf` — unknown-alias error surfaces known aliases

**Files:**
- Modify: `overleaf_sync/cli.py`
- Test: `tests/test_cli_unknown_alias.py`

- [ ] **Step 1: Write the failing test**
```python
from click.testing import CliRunner

import overleaf_sync.cli as cli_mod
from overleaf_sync.cli import main
from overleaf_sync.registry import UnknownAliasError


def test_status_unknown_alias_lists_known(monkeypatch):
    def boom(alias):
        raise UnknownAliasError("未知别名 'nope'；已登记: paperA, paperB")
    monkeypatch.setattr(cli_mod.registry, "get_project", boom)

    runner = CliRunner()
    result = runner.invoke(main, ["status", "nope"])

    assert result.exit_code != 0
    assert "paperA" in result.output
    assert "paperB" in result.output


def test_sync_unknown_alias_lists_known(monkeypatch):
    def boom(alias):
        raise UnknownAliasError("未知别名 'x'；已登记: paperA")
    monkeypatch.setattr(cli_mod.registry, "get_project", boom)

    runner = CliRunner()
    result = runner.invoke(main, ["sync", "x"])

    assert result.exit_code != 0
    assert "paperA" in result.output
```

- [ ] **Step 2: Run test to verify it fails** (Run: `.venv/bin/python -m pytest tests/test_cli_unknown_alias.py -q`; Expected: FAIL — without a handler the `UnknownAliasError` propagates as an uncaught exception (`result.exit_code == 1` but the message text from `str(exc)` is not printed to `result.output`; the assertion on `paperA` fails))

- [ ] **Step 3: Write minimal implementation** (wrap `main` group invocation to convert registry errors into clean exits; add a decorator and apply it to alias commands. Modify `overleaf_sync/cli.py`: add helper near top, after the `main` group definition)
```python
import functools


def _handle_registry_errors(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (registry.UnknownAliasError, registry.AliasExistsError) as exc:
            # UnknownAliasError subclasses KeyError, whose str() wraps the message
            # in repr quotes; print the raw message instead.
            msg = exc.args[0] if exc.args else str(exc)
            err_console.print(f"[red]{msg}[/red]")
            raise SystemExit(2)
    return wrapper
```
Then apply `@_handle_registry_errors` as the innermost decorator (directly above each `def`) on every command that calls `registry.get_project` or `registry.add_project`: `clone`, `register`, `sync`, `pull`, `push`, `status`, `open_cmd`, `compile_cmd`. Example for `status`:
```python
@main.command()
@click.argument("alias")
@_handle_registry_errors
def status(alias: str) -> None:
    ...
```

- [ ] **Step 4: Run test to verify it passes** (Run: `.venv/bin/python -m pytest tests/test_cli_unknown_alias.py -q`; Expected: PASS)

- [ ] **Step 5: Commit** (Run: `git add overleaf_sync/cli.py tests/test_cli_unknown_alias.py && git commit -m "feat(cli): surface known aliases on unknown-alias error"`)

---

### Task 48: cli — full command suite green (regression gate)

**Files:**
- Test: all `tests/test_cli_*.py`

- [ ] **Step 1: Write the failing test** (add the now-satisfiable subcommand-presence assertion as a dedicated regression test in `tests/test_cli_scaffold.py`)
```python
def test_all_subcommands_registered():
    from overleaf_sync.cli import main
    expected = {
        "login", "clone", "register", "list",
        "sync", "pull", "push", "status", "open", "compile",
    }
    assert expected.issubset(set(main.commands.keys()))
```

- [ ] **Step 2: Run test to verify it fails** (Run: `.venv/bin/python -m pytest tests/test_cli_scaffold.py::test_all_subcommands_registered -q`; Expected: PASS now that all commands are registered — if it FAILS, a command was registered under the wrong name; fix the `@main.command(name=...)` so the registry key matches the contract name.)

- [ ] **Step 3: Write minimal implementation** (no new implementation — this task is a regression gate. If `test_all_subcommands_registered` or the earlier `test_main_is_a_group_with_subcommands` fails, reconcile command names in `overleaf_sync/cli.py` with the contract.)

- [ ] **Step 4: Run test to verify it passes** (Run: `.venv/bin/python -m pytest tests/ -q`; Expected: PASS — entire CLI suite plus all prior module suites green)

- [ ] **Step 5: Commit** (Run: `git add tests/test_cli_scaffold.py && git commit -m "test(cli): regression gate — all subcommands registered, full suite green"`)

## Group 8 — Docs (SKILL.md / README.md / LEGAL.md)


### Task 49: SKILL.md (frontmatter + trigger words + body)

**Files:**
- Create: `SKILL.md`
- Test: manual (no pytest — markdown content + frontmatter validity)

- [ ] **Step 1: Write the file** — Create `SKILL.md` at the repo root with this exact content:

```markdown
---
name: overleaf-sync
description: "Overleaf 论文项目的本地同步与编译 CLI。通过 `overleaf` 命令走 Overleaf 原生 git（git.overleaf.com）双向同步本地 .tex 项目，并用本地 TinyTeX 跑 latexmk 编译出 PDF、缺包自动补。适用于：同步/上传/下载/拉取/推送 Overleaf 论文、克隆 git.overleaf.com 链接、在 VSCode 里编辑 tex 后同步回 Overleaf、本地编译 latex/pdflatex、解决 Overleaf 同步冲突。命令：overleaf login/clone/register/list/sync/pull/push/status/open/compile。\n\n⚠️ 不要与 yuque 混淆：yuque 读写蚂蚁内部语雀（yuque.antfin.com）富文本文档；本 skill 只管 Overleaf 的 LaTeX 项目通过原生 git 的本地同步与编译，二者无关。判断标准：对象是「Overleaf / .tex / git.overleaf.com / latex 编译」→ 本 skill；是「语雀 / 内部文档 / 知识库」→ yuque。"
---

# overleaf — Overleaf 本地同步与编译 CLI

`overleaf` 把 Overleaf 写作流变成「本地 VSCode 编辑 + git 双向同步 + 本地 TinyTeX 编译」：

- **同步**走 Overleaf 付费版的原生 git（`https://git.overleaf.com/<project-id>`），双向同步、冲突合并全交给 git。
- **编译**在本地用 TinyTeX（对齐 Overleaf 的 pdflatex 引擎）跑 `latexmk`，缺包自动 `tlmgr install` 补上。
- **sync 语义是自动提交式（类 Dropbox）**：auto-commit → `pull --rebase` → `push`。冲突时**永远停下让你手动解决，绝不自动覆盖**。

`overleaf --version` 应输出 **0.1.0**。

## 环境准备

SKILL.md 中的 `<skill_dir>` 指本 skill 的安装目录（SKILL.md 所在目录）。Claude Code 触发 skill 时会告知 base directory，用它替换所有 `<skill_dir>`。

本机已把 `overleaf` 软链到 PATH 上（`~/.local/bin/overleaf` → `<skill_dir>/.venv/bin/overleaf`），所以**直接用 `overleaf`** 即可。执行前确认一下：

```bash
overleaf --version    # 应输出 0.1.0

# 万一软链丢了/没装，重建：
test -x <skill_dir>/.venv/bin/overleaf || bash <skill_dir>/setup.sh
ln -sfn <skill_dir>/.venv/bin/overleaf ~/.local/bin/overleaf && overleaf --version
```

setup.sh 会在 skill 目录建 `.venv`、`pip install -e .`（依赖 `click`/`rich`，用清华镜像绕开本机坏掉的 `~/.pip/pip.conf`），软链全局命令，并幂等安装 TinyTeX。手动 pip 时请加 `--index-url https://pypi.tuna.tsinghua.edu.cn/simple`。

> ⚠️ **token 只进 macOS Keychain。** registry、`.git/config`、日志里都不出现 token。Overleaf git token 形如 `olp_xxxx`，在 Overleaf → Account Settings → Git Integration → Create Token 生成。

## 命令速查

```bash
overleaf login [--host H] [--token-stdin]            # 存 git token 到 Keychain（见下「认证」）
overleaf clone <url> <别名> [--path DIR]             # git clone（默认 ~/overleaf/<别名>）+ 登记 registry
overleaf register <路径> <别名>                       # 已有本地 git 仓库登记进 registry
overleaf list                                         # 表格：别名 / 路径 / 远端 / 状态
overleaf sync <别名> [--no-commit] [--message M]      # 核心：auto-commit → pull --rebase → push
overleaf pull <别名>                                  # git pull --rebase
overleaf push <别名>                                  # git push
overleaf status <别名>                                # 工作区状态 + ahead/behind + 冲突文件
overleaf open <别名>                                  # code <path>（VSCode 打开）
overleaf compile <别名> [--main F] [--engine E] [--open] [--no-auto-install]  # 本地 latexmk 编译
```

- 针对单项目的命令第一个参数都是**别名**；别名不存在时会列出已登记的别名。
- registry 在 `~/.config/overleaf-sync/projects.json`（目录 0700 / 文件 0600），只存 `path`/`remote`/`main`/`engine`，**不存 token**。

## 认证（一次性，token 进 Keychain）

```bash
overleaf login                       # 隐藏输入读取 token（推荐）
overleaf login --token-stdin         # 从 stdin 读 token（CI / 脚本）
echo "$OVERLEAF_TOKEN" | overleaf login --token-stdin
overleaf login --host git.overleaf.com   # 默认 host，自建实例可覆盖（v1 只验证 overleaf.com）
```

`login` 做两件事：确保 `git config --global credential.helper osxkeychain`，再把 `username=git` + `password=<token>` 喂给 `git credential approve` 写进 Keychain。之后所有 git 操作免输入。token 失效/更换：重跑 `overleaf login` 覆盖即可。

> 出现 `401`/`403`/`Unauthorized` → 提示先 `overleaf login`（或 token 过期，重跑 login 覆盖）。

## 典型流程

**首次接入一个 Overleaf 项目：**
```bash
overleaf login                                       # 1. 存 token（一次性）
overleaf clone https://git.overleaf.com/PROJECT_ID mypaper   # 2. clone + 登记
overleaf open mypaper                                # 3. VSCode 打开开始写
```
已经在本地 clone 过的仓库，用 `overleaf register <路径> <别名>` 登记即可（会校验是 git 仓库且 remote 指向 overleaf）。

**日常同步（写完一轮）：**
```bash
overleaf sync mypaper                                # auto-commit → pull --rebase → push
overleaf sync mypaper --message "改 intro"            # 自定义提交信息
overleaf sync mypaper --no-commit                    # 不自动提交（要求工作区已 clean，否则拒绝执行）
```

**本地编译出 PDF：**
```bash
overleaf compile mypaper                             # 默认 pdflatex，缺包自动补，最多重试 5 次
overleaf compile mypaper --open                      # 编译后用系统默认程序打开 PDF
overleaf compile mypaper --main paper.tex --engine xelatex   # 指定主文件 / 引擎
overleaf compile mypaper --no-auto-install           # 关掉缺包自动补
```
主文件探测顺序：registry 里的 `main` / `--main` > 扫 `.tex` 取同时含 `\documentclass` 与 `\begin{document}` 的那个。多个候选时报错并要求用 `--main` 指定。缺 `latexmk`/`tlmgr` → 提示跑 `bash <skill_dir>/setup.sh` 装 TinyTeX。

## 冲突处理（sync 的关键路径）

`overleaf sync` **绝不 abort、绝不 force**。`pull --rebase` 遇冲突时保留 rebase 现场并退出（非 0），打印冲突文件：

1. 在 **VSCode 里逐个解决冲突文件**（搜 `<<<<<<<`），`git add` 标记已解决。
2. 重跑 `overleaf sync <别名>`：它检测到未完成的 rebase 会自动 `git rebase --continue` 然后 `push`。
3. 如果还有未解决冲突（`git diff --diff-filter=U` 非空），sync 会再次打印冲突文件并提示「解决后重跑 overleaf sync <别名>」。

绝不替用户 `git stash` 或丢弃改动。`--no-commit` 且工作区脏时，sync 直接拒绝并提示先 `git commit`/`git stash`。
```

- [ ] **Step 2: Verify frontmatter + structure manually** — Run:
  ```bash
  python3 -c "import re,sys,pathlib; t=pathlib.Path('/Users/falcary/.agents/skills/overleaf-sync/SKILL.md').read_text(); m=re.match(r'^---\n(.*?)\n---\n',t,re.S); assert m,'no frontmatter'; fm=m.group(1); assert 'name: overleaf-sync' in fm,'name missing'; assert 'description:' in fm,'desc missing'; assert 'overleaf sync' in t and 'overleaf login' in t and 'overleaf compile' in t,'commands missing'; assert '<skill_dir>' in t,'skill_dir convention missing'; assert '0.1.0' in t,'version missing'; print('SKILL.md OK')"
  ```
  Expected: prints `SKILL.md OK` (frontmatter parses, name/description present, command quick-ref + `<skill_dir>` convention + version present).

- [ ] **Step 3: Commit** — Run:
  ```bash
  git -C /Users/falcary/.agents/skills/overleaf-sync add SKILL.md && git -C /Users/falcary/.agents/skills/overleaf-sync commit -m "docs: add SKILL.md (triggers, command quick-ref, sync/compile flows, conflict handling)"
  ```

### Task 50: README.md (robby-skills house-style front door)

**Files:**
- Create: `README.md`
- Test: manual (no pytest — markdown renders, all spec §11 sections present)

- [ ] **Step 1: Write the file** — Create `README.md` at the repo root with this exact content:

```markdown
# overleaf

**Overleaf 本地同步 CLI** — 把 Overleaf 论文项目变成「本地 VSCode 编辑 + git 双向同步 + 本地 TinyTeX 编译」。

走 Overleaf 付费版原生 git 同步，本地 pdflatex 编译对齐云端，token 只进 macOS Keychain。

```bash
overleaf login                                       # 存 git token 到 Keychain（一次性）
overleaf clone https://git.overleaf.com/PROJECT_ID mypaper   # clone + 登记别名
overleaf sync mypaper                                # auto-commit → pull --rebase → push
overleaf compile mypaper --open                      # 本地 latexmk 编译并打开 PDF
```

---

## Table of Contents

- [1. Architecture](#1-architecture)
  - [1.1 Design Goal](#11-design-goal)
  - [1.2 System Architecture](#12-system-architecture)
  - [1.3 Auth Model](#13-auth-model)
- [2. Installation](#2-installation)
  - [2.1 Install overleaf CLI](#21-install-overleaf-cli)
  - [2.2 Install TinyTeX](#22-install-tinytex)
- [3. Login](#3-login)
- [4. Quick Start](#4-quick-start)
- [5. Command Reference](#5-command-reference)
  - [5.1 login](#51-login)
  - [5.2 clone](#52-clone)
  - [5.3 register](#53-register)
  - [5.4 list](#54-list)
  - [5.5 sync](#55-sync)
  - [5.6 pull](#56-pull)
  - [5.7 push](#57-push)
  - [5.8 status](#58-status)
  - [5.9 open](#59-open)
  - [5.10 compile](#510-compile)
- [6. Registry & Config](#6-registry--config)
- [7. Local Compile](#7-local-compile)
- [8. Roadmap](#8-roadmap)
- [Releases](#releases)
- [Links](#links)

---

## 1. Architecture

### 1.1 Design Goal

`overleaf` 的目标是让 Overleaf 写作不离开本地工具链：在 VSCode 里改 `.tex`，用 git 双向同步回 Overleaf，本地编译出 PDF，整个 sync/compile 流程封装成一个 robbyctl 风格的 CLI。

| 维度 | 决策 |
|------|------|
| Overleaf 账号 | 付费版，有 Git 入口 → 走原生 git |
| 同步机制 | Overleaf git over HTTPS + token |
| sync 语义 | 自动提交式（类 Dropbox）：auto-commit → pull --rebase → push |
| 冲突 | 永远停下让用户手动解决，绝不自动覆盖 / force |
| 本地编译 | TinyTeX（TeX Live 2025），对齐 Overleaf 的 pdflatex，缺包自动补 |
| 项目管理 | 多项目，CLI 维护 registry（别名表，JSON） |
| token 存储 | macOS Keychain（git credential helper），绝不落盘 |

### 1.2 System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                          User's Machine                          │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                       overleaf CLI                          │  │
│  │                                                             │  │
│  │  login ─ clone ─ register ─ list ─ status ─ open            │  │
│  │  sync ─ pull ─ push                ─ compile                │  │
│  └───┬─────────────┬──────────────┬─────────────────┬──────────┘  │
│      │             │              │                 │             │
│      ▼             ▼              ▼                 ▼             │
│  ┌────────┐  ┌──────────┐  ┌─────────────┐  ┌──────────────┐      │
│  │ auth   │  │ registry │  │   gitops    │  │   compile    │      │
│  │Keychain│  │projects  │  │git -C <repo>│  │latexmk+tlmgr │      │
│  │(token) │  │ .json    │  │ commit/pull │  │ (TinyTeX)    │      │
│  └───┬────┘  └──────────┘  │ rebase/push │  └──────┬───────┘      │
│      │                     └──────┬──────┘         │              │
└──────┼────────────────────────────┼────────────────┼─────────────┘
       │ git credential             │ https + token  │ local PDF
       ▼                            ▼                ▼
  ┌─────────────┐          ┌────────────────────┐  ┌──────────────┐
  │ macOS       │          │  Overleaf git       │  │ ~/Library/   │
  │ Keychain    │          │ git.overleaf.com/   │  │ TinyTeX      │
  │ (osxkeychain)│         │   <project-id>      │  │ (TeX Live)   │
  └─────────────┘          └────────────────────┘  └──────────────┘
```

### 1.3 Auth Model

Overleaf 付费版 git 用 HTTPS Basic：`username = git`，`password = token`（在 Overleaf → Account Settings → Git Integration → Create Token 生成，形如 `olp_xxxx`）。

| 环节 | 做法 |
|------|------|
| 凭据存储 | git credential helper（macOS 默认 `osxkeychain`），存一次后 pull/push 免输入 |
| 写入方式 | `overleaf login` 把凭据喂给 `git credential approve`（stdin），写进 Keychain |
| 安全底线 | token 只进 Keychain；registry、`.git/config`、日志里都不出现 token；不支持把 token 写进 remote URL |
| 失效处理 | token 过期/更换重跑 `overleaf login` 覆盖即可 |

---

## 2. Installation

### 2.1 Install overleaf CLI

```bash
bash setup.sh
```

`setup.sh` 会：
1. 在 skill 目录建 `.venv`（`python3 -m venv .venv`）。
2. `pip install -e .`（依赖 `click`/`rich`），用 `--index-url https://pypi.tuna.tsinghua.edu.cn/simple` 绕开本机坏掉的 `~/.pip/pip.conf`。
3. 软链 `~/.local/bin/overleaf` → `.venv/bin/overleaf`，之后**直接敲 `overleaf`** 即可。
4. 幂等安装 TinyTeX（见 2.2）。

```bash
overleaf --version    # 应输出 0.1.0
```

### 2.2 Install TinyTeX

`setup.sh` 在检测不到可用 `latexmk`/`tlmgr` 时自动安装 TinyTeX（已有 TinyTeX 或系统 MacTeX 则跳过）：

```bash
curl -sL "https://yihui.org/tinytex/install-bin-unix.sh" | sh
tlmgr install latexmk        # 确保关键工具
```

装到 `~/Library/TinyTeX`，二进制在 `~/Library/TinyTeX/bin/<arch>/`。CLI 按 `PATH → ~/Library/TinyTeX → /Library/TeX/texbin` 的顺序定位工具，不依赖 shell PATH 重载。

---

## 3. Login

token 只存一次，进 macOS Keychain：

```bash
overleaf login                       # 隐藏输入读取 token（推荐）
overleaf login --token-stdin         # 从 stdin 读 token（CI / 脚本）
echo "$OVERLEAF_TOKEN" | overleaf login --token-stdin
overleaf login --host git.overleaf.com   # 默认 host，可覆盖（v1 只验证 overleaf.com）
```

`login` 确保 `git config --global credential.helper osxkeychain`，再用 `git credential approve` 把 `username=git` + `password=<token>` 写进 Keychain。之后所有 git 操作免输入。

> `401`/`403`/`Unauthorized` 一般是没 login 或 token 过期 → 重跑 `overleaf login`。

---

## 4. Quick Start

```bash
# 1. 一次性：存 token
overleaf login

# 2. clone 一个 Overleaf 项目并登记别名
overleaf clone https://git.overleaf.com/PROJECT_ID mypaper

# 3. VSCode 打开开始写
overleaf open mypaper

# 4. 写完一轮，双向同步回 Overleaf
overleaf sync mypaper

# 5. 本地编译并打开 PDF
overleaf compile mypaper --open
```

已经在本地 clone 过的仓库改用 `overleaf register <路径> <别名>` 登记即可。`overleaf list` 随时查看所有项目和状态。

---

## 5. Command Reference

| 命令 | 签名 | 行为 |
|------|------|------|
| `login` | `overleaf login [--host H] [--token-stdin]` | 读 token → 存 Keychain |
| `clone` | `overleaf clone <url> <别名> [--path DIR]` | `git clone` + 写 registry |
| `register` | `overleaf register <路径> <别名>` | 已有本地仓库登记进 registry |
| `list` | `overleaf list` | 表格：别名 / 路径 / 远端 / 状态 |
| `sync` | `overleaf sync <别名> [--no-commit] [--message M]` | 核心，见 §7 / [SKILL.md] |
| `pull` | `overleaf pull <别名>` | `git pull --rebase` |
| `push` | `overleaf push <别名>` | `git push` |
| `status` | `overleaf status <别名>` | 工作区状态 + ahead/behind + 冲突文件 |
| `open` | `overleaf open <别名>` | `code <path>`（VSCode 打开） |
| `compile` | `overleaf compile <别名> [--main F] [--engine E] [--open] [--no-auto-install]` | 本地 latexmk 编译 |

### 5.1 login

读取 Overleaf git token 并存进 Keychain。`--token-stdin` 从标准输入读（脚本友好），否则隐藏输入。`--host` 默认 `git.overleaf.com`。详见 [3. Login](#3-login)。

### 5.2 clone

```bash
overleaf clone <url> <别名> [--path DIR]
```

`git clone <url>` 到 `DIR`（默认 `~/overleaf/<别名>`），然后把 `别名 → {path, remote}` 写进 registry。`<url>` 形如 `https://git.overleaf.com/<project-id>`。

### 5.3 register

```bash
overleaf register <路径> <别名>
```

把一个**已有的本地 git 仓库**登记进 registry。会校验该路径是 git 仓库、且 remote 指向 overleaf；不满足则拒绝并说明原因。

### 5.4 list

```bash
overleaf list
```

rich 表格列出所有登记项目：别名 / 路径 / 远端 / 状态（clean / dirty / ahead N / behind N）。状态逐项目实时从 git 取。

### 5.5 sync

```bash
overleaf sync <别名> [--no-commit] [--message M]
```

核心命令，自动提交式同步（见 [7. Local Compile](#7-local-compile) 上方的「sync 算法」逻辑 / SKILL.md「冲突处理」）：

1. 若有未完成的 rebase：有未解决冲突 → 打印并退出；否则 `git rebase --continue` 后直接 push。
2. 工作区有改动且非 `--no-commit`：`git add -A` + `git commit -m "overleaf-sync: <ISO 时间戳>"`（或 `--message`）。
3. `git pull --rebase`：冲突时**保留现场、不 abort、不 force**，打印冲突文件 + 指引后退出（非 0）。
4. `git push`，打印摘要。

`--no-commit` 且工作区脏时，sync **拒绝执行**并提示先 `git commit`/`git stash`（不擅自 stash）。

### 5.6 pull

```bash
overleaf pull <别名>      # git -C <path> pull --rebase
```

### 5.7 push

```bash
overleaf push <别名>      # git -C <path> push
```

### 5.8 status

```bash
overleaf status <别名>
```

打印工作区状态：dirty/clean、ahead/behind 计数、未合并（冲突）文件、是否处于 rebase 中。

### 5.9 open

```bash
overleaf open <别名>      # code <path>，用 VSCode 打开项目目录
```

### 5.10 compile

```bash
overleaf compile <别名> [--main F] [--engine E] [--open] [--no-auto-install]
```

本地用 `latexmk` 编译出 PDF。主文件 / 引擎从 registry 取，`--main` / `--engine` 覆盖。默认引擎 `pdflatex`（对齐 Overleaf），可选 `xelatex` / `lualatex`。默认开启缺包自动补（`--no-auto-install` 关）。`--open` 编译成功后用系统默认程序打开 PDF。详见 [7. Local Compile](#7-local-compile)。

---

## 6. Registry & Config

文件：`~/.config/overleaf-sync/projects.json`（目录 0700 / 文件 0600，原子写入）。

```json
{
  "version": 1,
  "projects": {
    "mypaper": {
      "path": "/Users/you/overleaf/mypaper",
      "remote": "https://git.overleaf.com/PROJECT_ID",
      "main": "main.tex",
      "engine": "pdflatex"
    }
  }
}
```

- `path`、`remote` 必填；`main`、`engine` 可选（缺省时编译走自动探测 / pdflatex）。
- 别名（alias）是唯一 key。`clone` / `register` 写入，`list` 读出，其余命令按别名解析到 `path`。
- **不存 token。** token 只在 macOS Keychain。

---

## 7. Local Compile

本地编译用 TinyTeX，引擎默认 `pdflatex` 对齐 Overleaf，缺包自动补。

**工具定位**（不依赖 shell PATH 重载）：`shutil.which` → `~/Library/TinyTeX/bin/*/` → `/Library/TeX/texbin/`。都找不到 → 提示跑 `setup.sh` 装 TinyTeX。

**主文件探测：** registry 的 `main` / `--main` 优先；否则扫项目根 `.tex` 取同时含 `\documentclass` 与 `\begin{document}` 的那个；仍唯一不了则报错列出候选，要求 `--main` 指定。

**引擎映射：** `pdflatex → -pdf`、`xelatex → -xelatex`、`lualatex → -lualatex`。编译命令：

```
latexmk <engine-flag> -interaction=nonstopmode -halt-on-error <main.tex>
```

**缺包自动补**（默认开，`--no-auto-install` 关）：

1. 编译失败 → 读 `<main>.log`，匹配缺失文件（`! LaTeX Error: File \`xxx.sty' not found.` / `.cls` / 字体 `.fd` 等）。
2. 每个缺失文件：`tlmgr search --global --file "/xxx.sty"` 拿包名 → `tlmgr install <pkg>`。
3. 重试编译，最多循环 5 次，避免死循环；补不上则把 latexmk 日志关键段落打给用户。

成功后打印 PDF 路径；`--open` 用 `open <pdf>` 打开。

---

## 8. Roadmap

- v1（当前）：clone / register / list / sync / pull / push / status / open / compile，TinyTeX 编译 + 缺包自动补。
- 待验证：Overleaf git 对 username 的要求（`git` vs 任意）；TinyTeX 是否自带 `latexmk`；`tlmgr search --global --file` 输出格式。
- 明确不做（YAGNI）：Overleaf websocket 实时协同、免费账号 cookie/API 回退、Dropbox/GitHub bridge、PDF 并排预览、多账号 / 图形化冲突解决。

---

## Releases

### v0.1.0 — 2026-06-06

- 初始版本：`login` / `clone` / `register` / `list` / `sync` / `pull` / `push` / `status` / `open` / `compile`。
- 自动提交式 `sync`：auto-commit → pull --rebase → push；冲突永远停下手动解决，rebase 现场可续接。
- 本地 TinyTeX 编译：主文件自动探测、pdflatex 对齐 Overleaf、缺包 `tlmgr` 自动补（最多重试 5 次）。
- 多项目 registry（`~/.config/overleaf-sync/projects.json`，0700/0600）。
- token 只进 macOS Keychain（`git credential approve`），绝不落盘。

---

## Links

- [Overleaf Git Integration](https://www.overleaf.com/learn/how-to/Git_integration)
- [TinyTeX](https://yihui.org/tinytex/)
- [latexmk](https://ctan.org/pkg/latexmk)
- [SKILL.md](SKILL.md) — 给 Claude 的触发条件与命令速查
```

- [ ] **Step 2: Verify all spec §11 sections render manually** — Run:
  ```bash
  python3 -c "import pathlib; t=pathlib.Path('/Users/falcary/.agents/skills/overleaf-sync/README.md').read_text(); req=['# overleaf','## 1. Architecture','### 1.1 Design Goal','### 1.2 System Architecture','### 1.3 Auth Model','## 2. Installation','### 2.1 Install overleaf CLI','### 2.2 Install TinyTeX','## 3. Login','## 4. Quick Start','## 5. Command Reference','## 6. Registry & Config','## 7. Local Compile','## 8. Roadmap','## Releases','v0.1.0','## Links']; missing=[s for s in req if s not in t]; assert not missing, f'missing: {missing}'; print('README.md OK')"
  ```
  Expected: prints `README.md OK` (all robby-skills house-style sections from spec §11 present, including the ASCII architecture diagram, v0.1.0 release, and Links).

- [ ] **Step 3: Commit** — Run:
  ```bash
  git -C /Users/falcary/.agents/skills/overleaf-sync add README.md && git -C /Users/falcary/.agents/skills/overleaf-sync commit -m "docs: add README.md (robby-skills house-style front door)"
  ```

### Task 51: LEGAL.md (short disclaimer)

**Files:**
- Create: `LEGAL.md`
- Test: manual (no pytest — short bilingual disclaimer, mirrors aistudio-jobs)

- [ ] **Step 1: Write the file** — Create `LEGAL.md` at the repo root with this exact content:

```markdown
Legal Disclaimer

Within this source code, the comments in Chinese shall be the original, governing version. Any comment in other languages are for reference only. In the event of any conflict between the Chinese language version comments and other language version comments, the Chinese language version shall prevail.

法律免责声明

关于代码注释部分，中文注释为官方版本，其它语言注释仅做参考。中文注释可能与其它语言注释存在不一致，当中文注释与其它语言注释存在不一致时，请以中文注释为准。
```

- [ ] **Step 2: Verify content manually** — Run:
  ```bash
  python3 -c "import pathlib; t=pathlib.Path('/Users/falcary/.agents/skills/overleaf-sync/LEGAL.md').read_text(); assert 'Legal Disclaimer' in t and '法律免责声明' in t and '中文注释' in t; print('LEGAL.md OK')"
  ```
  Expected: prints `LEGAL.md OK` (short bilingual disclaimer present, mirroring aistudio-jobs/LEGAL.md).

- [ ] **Step 3: Commit** — Run:
  ```bash
  git -C /Users/falcary/.agents/skills/overleaf-sync add LEGAL.md && git -C /Users/falcary/.agents/skills/overleaf-sync commit -m "docs: add LEGAL.md (bilingual disclaimer)"
  ```

---

## Final Verification

After all 51 tasks, confirm the whole skill works end-to-end.

- [ ] **Step 1: Full test suite is green**

Run: `.venv/bin/python -m pytest -q`
Expected: all module suites pass (registry, gitops, auth, tex, compile, cli, conftest, packaging).

- [ ] **Step 2: Install + version smoke test**

Run: `bash setup.sh && ~/.local/bin/overleaf --version`
Expected: setup completes; prints `overleaf, version 0.1.0`.

- [ ] **Step 3: Token never leaks to disk (security invariant)**

The token must live only in the Keychain — never in the registry, a project's `.git/config`, or a remote URL.
Run:
```bash
grep -rn 'olp_' ~/.config/overleaf-sync/ ~/overleaf/*/.git/config 2>/dev/null && echo "LEAK!" || echo "no token on disk"
for d in ~/overleaf/*/; do [ -d "$d/.git" ] && git -C "$d" remote -v; done
```
Expected: prints `no token on disk`, and no remote URL contains `olp_` / an embedded token (`https://git@git.overleaf.com/<id>`, never `https://git:<token>@...`).

- [ ] **Step 4: Live round-trip against a real Overleaf project (manual)**

- `overleaf login` (paste a real token), `overleaf clone https://git.overleaf.com/<id> demo`.
- Edit a `.tex` in VSCode (`overleaf open demo`), then `overleaf sync demo` → auto-commits, pulls, pushes; the change appears on Overleaf.
- Make a conflicting edit on Overleaf + locally → `overleaf sync demo` stops, lists `conflict.tex`, and does NOT overwrite; after resolving in VSCode, `overleaf sync demo` continues and pushes.
- `overleaf compile demo --open` produces and opens the PDF (TinyTeX auto-installs any missing package).

- [ ] **Step 5: Confirm sync never auto-resolves / force-pushes (code audit)**

Run: `grep -rn 'rebase --abort\|push.*--force\|push.*-f\b' overleaf_sync/`
Expected: no matches (the conflict path preserves state; pushes are never forced).
