#!/usr/bin/env python3
"""Install the CLI into its own venv; optionally link the skill and command.

Python-only entry point. No TeX installation, login, global pip changes, or
shell-profile edits. --check is read-only and does not contact the network.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def venv_python(root: Path) -> Path:
    return root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def validate_root(root: Path) -> None:
    for name in ("SKILL.md", "tools/SKILL.md", "writings/SKILL.md", "pyproject.toml",
                 "tools/overleaf_sync/cli.py"):
        if not (root / name).is_file():
            raise ValueError(f"Incomplete source checkout: missing {name}")
    if (root / ".venv").is_symlink():
        raise ValueError("Refusing to install into a symlinked .venv; use a dedicated environment.")


def expected_version(root: Path) -> str:
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    return re.search(r'^version = "([^"]+)"', text, re.M).group(1)


def check_environment(root: Path) -> dict:
    """Probe the venv, including runtime minimum versions, without importing host packages."""
    python = venv_python(root)
    report = {"python": str(python), "git": shutil.which("git"),
              "node_optional": shutil.which("node"), "runtime_ready": False}
    if python.is_file():
        probe = subprocess.run([str(python), "-I", "-B", "-c", """
import json, sys
from importlib.metadata import version
from overleaf_sync import __version__, tex
import click, rich
print(json.dumps({'python_version': list(sys.version_info[:3]),
    'version': __version__, 'package_version': version('overleaf-ctl'),
    'click': version('click'), 'rich': version('rich'),
    'latexmk_optional': tex.locate_tool('latexmk'),
    'pdflatex_optional': tex.locate_tool('pdflatex'),
    'xelatex_optional': tex.locate_tool('xelatex'),
    'lualatex_optional': tex.locate_tool('lualatex'),
    'tlmgr_optional': tex.locate_tool('tlmgr')}))
"""], capture_output=True, text=True)
        if probe.returncode == 0:
            try:
                data = json.loads(probe.stdout)
                report.update(data)
                def numeric(value):
                    return tuple(int(p) for p in re.findall(r"\d+", value)[:2])
                report["runtime_ready"] = bool(
                    data["python_version"] >= [3, 10]
                    and data["version"] == data["package_version"] == expected_version(root)
                    and numeric(data["click"]) >= (8, 2)
                    and numeric(data["rich"]) >= (13,)
                    and report["git"]
                )
            except (ValueError, KeyError):
                report["error"] = "Unexpected venv probe output. Rerun this installer."
        else:
            report["error"] = "Venv dependencies are missing/incompatible. Rerun this installer."
    else:
        report["error"] = "No usable .venv. Run this installer without --check."
    return report


def check_link(destination: Path, source: Path) -> None:
    """Preserve unrelated files, directories, and broken symlinks."""
    if os.path.lexists(destination) and destination.resolve() != source.resolve():
        raise ValueError(f"Refusing to replace existing path: {destination}\n"
                         f"Requested target: {source}\nReview the existing installation first.")


def link_path(destination: Path, source: Path, directory: bool = False) -> None:
    check_link(destination, source)
    if os.path.lexists(destination):
        print(f"Already linked: {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt" and directory:
        subprocess.run(["cmd", "/c", "mklink", "/J", str(destination), str(source)], check=True)
    else:
        destination.symlink_to(source, target_is_directory=directory)
    print(f"Linked: {destination} -> {source}")


def skill_destination(target: str) -> Path:
    if target == "codex":
        base = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    elif target == "claude":
        base = Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude"))
    else:
        base = Path.home() / ".agents"
    return base.expanduser().absolute() / "skills" / "overleaf-ctl"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Read-only environment check; no install or links.")
    parser.add_argument("--dev", action="store_true", help="Also install pytest and test dependencies.")
    parser.add_argument("--index-url", help="Optional pip package index; defaults to the user's pip configuration.")
    targets = parser.add_mutually_exclusive_group()
    targets.add_argument("--link-skill", choices=["codex", "claude", "agents"])
    targets.add_argument("--skill-path", type=Path, help="Explicit skill link destination (e.g. an isolated test directory).")
    parser.add_argument("--link-cli", action="store_true", help="Link overleaf-ctl in --bin-dir (macOS/Linux).")
    parser.add_argument("--bin-dir", type=Path, default=Path.home() / ".local/bin")
    args = parser.parse_args(argv)
    try:
        if sys.version_info < (3, 10):
            raise ValueError("Python >= 3.10 is required; invoke this script with a newer Python executable.")
        validate_root(ROOT)
        if args.check:
            report = check_environment(ROOT)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["runtime_ready"] else 1
        if not shutil.which("git"):
            raise ValueError("Git is required. Install Git before running this installer.")
        if args.link_cli and os.name == "nt":
            raise ValueError("On Windows, activate .venv/Scripts/Activate.ps1 or use .venv/Scripts/overleaf-ctl.exe.")
        skill = (args.skill_path.expanduser().absolute() if args.skill_path else
                 skill_destination(args.link_skill) if args.link_skill else None)
        command = ROOT / ".venv/bin/overleaf-ctl"
        bin_link = args.bin_dir.expanduser().absolute() / "overleaf-ctl"
        if skill:
            check_link(skill, ROOT)
        if args.link_cli:
            check_link(bin_link, command)
        python = venv_python(ROOT)
        if not (ROOT / ".venv").exists():
            subprocess.run([sys.executable, "-m", "venv", str(ROOT / ".venv")], check=True)
        elif not python.is_file():
            raise ValueError("Existing .venv is incomplete; repair or move it before retrying. It was not deleted.")
        requirement = str(ROOT) + ("[dev]" if args.dev else "")
        pip_args = [str(python), "-I", "-m", "pip", "install", "-e", requirement]
        if args.index_url:
            pip_args += ["--index-url", args.index_url]
        subprocess.run(pip_args, check=True)
        report = check_environment(ROOT)
        if not report["runtime_ready"]:
            print(json.dumps(report, indent=2, ensure_ascii=False))
            raise ValueError("Installation verification failed; no new links were created.")
        if skill:
            link_path(skill, ROOT, directory=True)
        if args.link_cli:
            link_path(bin_link, command)
        print(f"Installed overleaf-ctl {report['version']}. TeX was not installed; credentials were not accessed.")
        print("Activate .venv/Scripts/Activate.ps1" if os.name == "nt" else f"Activate: source {ROOT}/.venv/bin/activate")
        if args.link_cli:
            print(f"Ensure {bin_link.parent} is on PATH, or invoke {bin_link} directly.")
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Installation/check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
