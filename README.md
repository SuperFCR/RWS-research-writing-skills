# RWS Research Writing Skills

**English** | [简体中文](README.zh-CN.md)

Evidence-first writing for Overleaf and local LaTeX projects. Keep project records, map claims to sources, draft by section, and review the result. Includes **overleaf-ctl 0.3.1**.

## What it does

- **Resume work:** store requirements, outlines, and progress in `.writing/`.
- **Write from evidence:** connect sources to claims and paragraph plans before drafting.
- **Review by section:** delegate major sections for full drafts, then integrate and review centrally.
- **Make contributions clear:** remove defensive phrasing while retaining uncertainty and material limitations.
- **Preserve your project:** keep existing `sections/` or `sec/` layouts; offer numbered TeX sections for new papers.

## Requirements

| Component | Needed for |
|---|---|
| Python ≥ 3.10 with pip/venv, Git | CLI and project initialization |
| `click`, `rich` | Installed automatically in a local `.venv` |
| LaTeX engine + `latexmk` | Local PDF compilation only |
| Node.js ≥ 18 / npm | Optional npm wrapper |

The writing instructions can be read without installation. AI reasoning, literature access, and subagents come from your agent environment.

## Quick start

On macOS / Linux:

```bash
git clone https://github.com/SuperFCR/RWS-research-writing-skills.git
cd RWS-research-writing-skills
python3 overleaf-ctl/scripts/install.py --link-skill codex --link-cli
source overleaf-ctl/.venv/bin/activate
python3 overleaf-ctl/scripts/install.py --check
```

The installer links the skill to Codex and the CLI to `~/.local/bin`. It installs runtime dependencies only. For later terminals, activate the venv or add `~/.local/bin` to `PATH`. See [Windows and other installation options](overleaf-ctl/README.md#install).

Create a local paper:

```bash
git init /path/to/paper
overleaf-ctl writing init --path /path/to/paper --scaffold
overleaf-ctl compile --path /path/to/paper --no-auto-install
```

Compilation requires TeX. For an existing Git paper, skip `git init` and omit `--scaffold`. For Overleaf, [log in and clone the project](overleaf-ctl/README.md#use). Then ask your agent to write or revise with `$overleaf-ctl`.

## Structure and local files

```text
overleaf-ctl/
├── SKILL.md      # Entry point
├── tools/        # CLI, Git sync, compilation, push checks
└── writings/     # Records, evidence, drafting, review
```

Paper records in `.writing/` and build files in `.outputs/` stay local. `overleaf-ctl sync/push` also checks staged files and outgoing commits. Direct `git push` and other clients bypass these checks. Paper sources, bibliography, templates, and figures sync normally.

## Update

From the repository root:

```bash
git pull --ff-only
python3 overleaf-ctl/scripts/install.py
python3 overleaf-ctl/scripts/install.py --check
```

[Usage, troubleshooting, and sources](overleaf-ctl/README.md) · [Writing workflow](overleaf-ctl/writings/SKILL.md) · [Tool workflow](overleaf-ctl/tools/SKILL.md)
