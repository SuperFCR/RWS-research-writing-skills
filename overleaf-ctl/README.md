# overleaf-ctl 0.3.1

**English** | [简体中文](README.zh-CN.md)

LaTeX writing skills with a Python CLI for local compilation and guarded Overleaf Git sync.

```text
overleaf-ctl/
├── SKILL.md                 # Routes tasks to tools or writings
├── tools/overleaf_sync/     # Python CLI
├── tools/SKILL.md           # Sync and compilation workflow
├── writings/               # Records, evidence, drafting, review
├── scripts/                # Installation and skill linking
└── tests/                  # Unit and local Git integration tests
```

<a id="接入与使用"></a>

## Install

Requires **Python ≥ 3.10** with pip/venv and **Git** on `PATH`. Run from this directory:

```bash
python3 scripts/install.py --link-skill codex --link-cli
source .venv/bin/activate
overleaf-ctl --version
python3 scripts/install.py --check
```

The installer creates `.venv` and installs `click ≥ 8.2` and `rich ≥ 13`. Pip handles `setuptools` and `wheel` in an isolated build environment. Keep the full skill directory, including `tools/` and `writings/`.

- **Command access:** activate the venv, use `.venv/bin/overleaf-ctl`, or add `~/.local/bin` to `PATH`. The installer does not edit shell configuration.
- **Optional npm:** Node.js ≥ 18; run `npm run setup`, then `npm link` and `npm run link:skill:codex` as needed. `setup.sh` also invokes the Python installer.
- **Environment check:** `--check` is read-only, requires no network or credentials, and reports missing optional TeX tools separately.

On Windows PowerShell, select an installed Python ≥ 3.10, for example:

```powershell
py -3.11 scripts/install.py --link-skill codex
.\.venv\Scripts\overleaf-ctl.exe --version
py -3.11 scripts/install.py --check
```

Windows links skills through a directory junction; `--link-cli` is for macOS/Linux.

### Optional TeX

Local PDF compilation needs the template's LaTeX engine and `latexmk`, provided by distributions such as TinyTeX, TeX Live, or MacTeX. The CLI installer does not install TeX. Compilation may install missing TeX packages when `tlmgr` is available; use `--no-auto-install` to disable this.

## Use

Overleaf Git credentials are separate from GitHub SSH authentication:

```bash
overleaf-ctl login
overleaf-ctl clone https://git.overleaf.com/PROJECT_ID paper
overleaf-ctl writing init paper
```

For an existing checkout, use `overleaf-ctl register /path/to/paper paper`. Local projects need no Overleaf account or remote:

```bash
git init /path/to/paper
overleaf-ctl writing init --path /path/to/paper
overleaf-ctl compile --path /path/to/paper --no-auto-install
```

Skip `git init` for existing Git projects. Add `--scaffold` to initialize a new numbered `sections/` template; existing `.tex/.cls/.sty/.bst` files or section directories prevent scaffolding. Initialization does not push.

```bash
overleaf-ctl list
overleaf-ctl status paper
overleaf-ctl compile paper --no-auto-install
overleaf-ctl check-push paper
overleaf-ctl sync paper --message "Revise introduction"
```

Invoke `$overleaf-ctl` for the combined workflow. Writing uses project records, evidence maps, paragraph plans, and two-stage review. Full drafts delegate major sections; local edits stay scoped. Existing file names and input/include chains are preserved. See [writing instructions](writings/SKILL.md), [project layout](writings/references/project-layout.md), and the [CLI reference](tools/references/cli.md).

## Local files and push checks

`.writing/` holds project records; `.outputs/` holds local build files. Git's local `info/exclude` keeps them out of routine staging. Paper figures, templates, and bibliography remain eligible for sync.

`sync` checks the index and staging candidates before committing. `push` fetches the target branch and checks every outgoing commit tree, catching forced additions and files added then deleted. A failure blocks publication without deleting files or rewriting history. Direct Git commands, other clients, and web uploads bypass these checks.

Pushes target only the current branch's `origin` upstream, without automatic tags. Missing upstreams, mismatched fetch/push URLs, or absent target branches require resolution. `check-push` uses the local upstream snapshot; an actual push fetches and checks again. `sync` automatically commits all non-ignored changes, so review the scope first.

To exclude additional local directories after checking their contents:

```bash
overleaf-ctl writing init paper --local-only plan --local-only latex_outputs
```

Exact paths are stored in Git's `info/overleaf-ctl-local-only.json`; wildcards are unsupported. Existing tracked files are reported, not automatically untracked. Worktrees use the resolved Git paths.

## Update and troubleshoot

Pull the source with `git pull --ff-only`, then rerun `python3 scripts/install.py` and `--check`.

- **Missing command:** activate the venv or use its CLI path. A skill link alone does not expose the command.
- **Old Python / missing venv:** select Python ≥ 3.10 and install its venv support through your system package manager.
- **Download failure:** pip configuration is respected; optionally pass `--index-url https://pypi.org/simple` or a trusted mirror.
- **Existing link:** update the installation it points to. The installer refuses to overwrite another installation.
- **Missing TeX:** install the required TeX tools separately; reinstalling the CLI will not supply them.

## Development

```bash
python3 scripts/install.py --dev
.venv/bin/python -m pytest -q
node scripts/link-skill.js codex --dry-run
npm pack --dry-run
```

`--dev` adds test dependencies (`pytest`, plus `tomli` on Python < 3.11). `npm test` runs tests without installing dependencies. `overleaf` remains a CLI alias. Historical designs live in `docs/`; current skills and code take precedence.

Version 0.3.1 passed **228 tests**, a fresh macOS installation, skill/CLI linking, and local paper initialization with PDF compilation. Tests use temporary local Git remotes. Windows/Linux have not had native end-to-end validation.

## Sources

The records, evidence, and chapter-review workflow draws on [research-writing-skill](https://github.com/Norman-bury/research-writing-skill), adapted for existing TeX projects. Contribution-focused prose draws on [anti-defensive-writing-en](https://github.com/Adkid-Zephyr/anti-defensive-writing-Skill/blob/main/skills/anti-defensive-writing-en/SKILL.md), retaining material adverse results, uncertainty, and scope limits. Its [MIT license](writings/references/anti-defensive-LICENSE.txt) is included. Neither upstream skill is installed by this package.
