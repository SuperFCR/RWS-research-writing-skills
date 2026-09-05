# overleaf-ctl Progress Snapshot

Date: 2026-06-10

This document summarizes the current implementation state for cross-checking in Claude Code. It describes the working tree snapshot, not a tagged release.

## Current Paths

- Active toolkit repo: `/Users/falcary/code/ant_proj/overleaf-toolkits`
- Former/original skill path still present: `/Users/falcary/.agents/skills/overleaf-sync`
- New skill entrypoint in repo: `SKILL.md`
- Python package module: `overleaf_sync/`
- npm CLI wrapper: `bin/overleaf-ctl.js`
- npm helper scripts: `scripts/bootstrap-python.js`, `scripts/link-skill.js`
- README workflow image: `docs/assets/overleaf-ctl-workflow.png`
- Progress docs: `docs/progress/`
- User paper project used during validation: `/Users/falcary/overleaf/paper`

## Naming and Packaging Decision

- User-facing command is now `overleaf-ctl`.
- Python distribution name is `overleaf-ctl`.
- Python module name remains `overleaf_sync` to avoid unnecessary internal churn.
- Compatibility alias remains available:
  - Python console scripts: `overleaf-ctl`, `overleaf`
  - npm bin entries: `overleaf-ctl`, `overleaf`
- `bin/overleaf-ctl.js` calls the Python CLI and sets `sys.argv[0]` to `overleaf-ctl`, so help/version output uses the new command name.

## Current Implementation

### Implemented Native Backend

The current v0.1 implementation supports Overleaf native Git integration through top-level commands:

```bash
overleaf-ctl login
overleaf-ctl clone <https://git.overleaf.com/PROJECT_ID> <alias>
overleaf-ctl register <path> <alias>
overleaf-ctl list
overleaf-ctl status <alias>
overleaf-ctl open <alias>
overleaf-ctl pull <alias>
overleaf-ctl push <alias>
overleaf-ctl sync <alias>
overleaf-ctl compile <alias>
```

Important behavior:

- `login` stores the Overleaf Git token through git credential helper / macOS Keychain.
- Registry lives at `~/.config/overleaf-sync/projects.json`.
- `sync` follows auto-commit -> `pull --rebase` -> `push`.
- Rebase conflicts are preserved; the tool does not abort, force push, stash, or discard user changes.

### Local Compile Outputs

Compile outputs now go under project-local `.outputs/`:

- `overleaf_sync/compile.py` defines `OUTPUT_DIR_NAME = ".outputs"`.
- `latexmk` runs with `-outdir=.outputs`.
- PDF path is `.outputs/<main>.pdf`.
- Aux/log/bbl/blg/fls/fdb_latexmk files also stay in `.outputs/`.
- Missing-package parsing reads `.outputs/<main>.log` and `.outputs/<main>.blg`.
- `overleaf_sync/gitops.py` local excludes include `.outputs/`, so sync should not push compile artifacts.

This was validated against `/Users/falcary/overleaf/paper`; compile produced `/Users/falcary/overleaf/paper/.outputs/main.pdf`.

### npm Wrapper and Skill Installation

`package.json` now defines:

```bash
npm run setup
npm run setup:dev
npm run setup:full
npm test
npm run check:skill
npm run link:skill
npm run link:skill:codex
npm run link:skill:cc
npm run link:skill:agents
npm run link:skill:legacy-agents
```

Installation helper behavior:

- `npm run check:skill` is a dry-run check only.
- `npm run link:skill:codex` links to `${CODEX_HOME:-~/.codex}/skills/overleaf-ctl`.
- `npm run link:skill:cc` links to `${CLAUDE_HOME:-~/.claude}/skills/overleaf-ctl`.
- `npm run link:skill` links codex + cc + `~/.agents/skills/overleaf-ctl`.
- `npm run link:skill:legacy-agents` explicitly targets old `~/.agents/skills/overleaf-sync`.
- The script refuses to overwrite an existing target if it does not already point to this repo.

Current dry-run result:

- Codex target is installable.
- Claude Code target is installable.
- Agents target is installable.
- Legacy `~/.agents/skills/overleaf-sync` already exists separately, so it is intentionally not part of default `all`.

### README and Skill Documentation

README now includes:

- `overleaf-ctl` command usage.
- Premium/Git-enabled boundary.
- npm-managed wrapper installation.
- environment requirements: Node, Python, click/rich, git, Keychain, latexmk, tlmgr, VSCode `code`.
- TinyTeX and MacTeX install/check instructions.
- automatic and manual TeX package installation via `tlmgr`.
- compile outputs under `.outputs/`.
- native backend implemented vs github backend planned.
- workflow diagram at `docs/assets/overleaf-ctl-workflow.png`.
- Team Collaboration Rules.

`SKILL.md` now mirrors the main operational instructions for agent use:

- skill name: `overleaf-ctl`
- trigger description for Overleaf Git-enabled LaTeX sync/compile
- environment setup
- command quick reference
- login/token guidance
- compile and `.outputs/`
- TeX missing-package handling
- sync conflict handling

## GitHub Backend Design State

GitHub backend is documented as a planned mode, not implemented.

Current documented intent:

- common project commands work regardless of backend:
  - `overleaf-ctl compile paper`
  - `overleaf-ctl status paper`
  - `overleaf-ctl open paper`
  - `overleaf-ctl list`
- native backend path:
  - local `<->` `git.overleaf.com` `<->` Overleaf
- github backend path:
  - local `<->` GitHub repo
  - Overleaf `<->` GitHub sync is still triggered manually through the Overleaf web UI by the premium owner

Potential future command shape:

```bash
overleaf-ctl native sync paper
overleaf-ctl github sync paper
```

Do not assume these subcommands exist yet.

## Team Collaboration Rules Added

README now recommends:

- Treat GitHub `main` as the team source of truth.
- Use branch + PR for multi-person writing.
- Use Overleaf mainly for preview, final checks, and limited web editing.
- Owner manually pulls GitHub changes into Overleaf after PR merge.
- Owner manually pushes Overleaf web changes back to GitHub if web edits happen.
- Avoid simultaneous edits to the same text in Overleaf Web and GitHub.
- Avoid submodules, Git LFS, symlinks, oversized repos, and large generated files.
- Keep `.outputs/` and compile artifacts out of sync.
- Resolve:
  - GitHub PR conflicts in GitHub/local Git.
  - Overleaf GitHub sync branches by PR-merging them back to main.
  - `overleaf-ctl sync` rebase conflicts manually, then rerun `overleaf-ctl sync <alias>`.

## Validation Already Performed

Known successful checks during this work:

```bash
.venv/bin/overleaf-ctl --version
.venv/bin/overleaf --version
node bin/overleaf-ctl.js --version
node bin/overleaf-ctl.js status paper
node bin/overleaf-ctl.js compile paper
npm run check:skill
npm pack --dry-run
npm test
```

Observed results:

- `overleaf-ctl, version 0.1.0`
- `paper` status reported clean.
- compile output landed in `.outputs/main.pdf`.
- `npm pack --dry-run` includes README, SKILL.md, Python package files, npm wrapper/scripts, setup.sh, and `docs/assets/overleaf-ctl-workflow.png`.
- earlier full test run passed: `158 passed`.

Note: after the full test run, later changes were mostly README/docs/package/link-script additions. A fresh `npm test` before commit/release is still recommended.

## Current Working Tree State

As of this snapshot, the repo has uncommitted changes. Relevant changed/new areas:

- Modified:
  - `.gitignore`
  - `README.md`
  - `SKILL.md`
  - `overleaf_sync/__init__.py`
  - `overleaf_sync/cli.py`
  - `overleaf_sync/compile.py`
  - `overleaf_sync/gitops.py`
  - `pyproject.toml`
  - `setup.sh`
  - tests covering CLI, compile, packaging
- New:
  - `bin/overleaf-ctl.js`
  - `package.json`
  - `scripts/bootstrap-python.js`
  - `scripts/link-skill.js`
  - `docs/assets/overleaf-ctl-workflow.png`
  - `docs/progress/2026-06-10-overleaf-ctl-status.md`

## Cross-Check Checklist for Claude Code

Please independently verify:

1. `overleaf-ctl` naming is consistent in README, SKILL.md, CLI help, setup.sh, pyproject scripts, and tests.
2. Compatibility alias `overleaf` is intentional and does not reintroduce old wording in docs.
3. `compile` always writes to `.outputs/` and all log/missing-package parsing reads from that directory.
4. `.outputs/` is excluded from sync through `.git/info/exclude` and package/project ignore rules.
5. `overleaf-ctl sync` still preserves conflict state and never force-pushes, aborts, stashes, or discards.
6. npm wrapper correctly uses the repo-local Python environment when present and gives actionable setup errors.
7. `npm run check:skill` is non-mutating; `link:skill:*` refuses to overwrite unrelated skill dirs.
8. `npm pack --dry-run` contains all files needed by a fresh install, especially `SKILL.md`, `README.md`, `setup.sh`, `bin/`, `scripts/`, `overleaf_sync/*.py`, and `docs/assets/`.
9. README does not imply github backend is currently implemented.
10. Team Collaboration Rules match Overleaf limitations: GitHub sync is manual, Overleaf Git does not support branches, and submodules/LFS/symlinks are not safe assumptions.
11. Tests cover output-dir behavior, packaging names, and conflict guidance.
12. No user token or private credential appears in docs, registry examples, setup scripts, or logs.

## Known Open Items

- GitHub backend commands are planned but not implemented.
- No real GitHub backend sync test exists yet.
- No automated end-to-end test against a live Overleaf Git remote is included.
- Skill installation has only been dry-run checked; it has not been installed in this session.
- The legacy skill path remains separate and may need manual migration/removal later.
- README includes an AI-generated PNG workflow; text is useful but should be visually rechecked before publication.
