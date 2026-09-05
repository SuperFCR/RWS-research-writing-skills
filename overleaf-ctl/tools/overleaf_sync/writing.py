"""Non-destructive writing workspace initialization for registered paper repos."""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import gitops, publish

SECTIONS = [
    ("0_abstract.tex", "Abstract"),
    ("1_intro.tex", "Introduction"),
    ("2_related_work.tex", "Related Work"),
    ("3_method.tex", "Method"),
    ("4_experiments.tex", "Experiments"),
    ("5_conclusion.tex", "Conclusion"),
    ("6_broader_impact.tex", "Broader Impact"),
    ("X_appendix.tex", "Appendix"),
]


def _write_new(path: Path, text: str) -> bool:
    if path.is_symlink():
        raise ValueError(f"Refusing to write through symlink: {path}")
    if path.exists():
        if not path.is_file():
            raise ValueError(f"Expected a regular file: {path}")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(text)
    return True


def _check_root(repo: Path) -> None:
    root = gitops._run(repo, ["rev-parse", "--show-toplevel"], check=True).stdout.strip()
    if Path(root).resolve() != repo:
        raise ValueError("Writing initialization requires the repository root.")
    state = repo / ".writing"
    if state.is_symlink() or (state.exists() and not state.is_dir()):
        raise ValueError(".writing must be a real local directory.")
    if state.exists() and any(p.is_symlink() for p in state.rglob("*")):
        raise ValueError("Remove or relocate symlinks from .writing before initialization.")


def inspect_layout(repo: Path) -> dict:
    def usable(path: Path) -> bool:
        relative = path.relative_to(repo)
        return not ({".git", ".writing", ".outputs"} & set(relative.parts)) and not path.is_symlink()

    tex_files = sorted(p.relative_to(repo).as_posix() for p in repo.rglob("*.tex") if usable(p))
    mains = []
    inputs = {}
    for name in tex_files:
        text = (repo / name).read_text(encoding="utf-8", errors="replace")
        text = re.sub(r"(?<!\\)%[^\n]*", "", text)
        if re.search(r"\\documentclass(?:\[.*?\])?\s*\{", text) and "\\begin{document}" in text:
            mains.append(name)
            inputs[name] = re.findall(r"\\(?:input|include)\s*\{([^}]+)\}", text)
    return {
        "schema_version": 1,
        "main_candidates": mains,
        "inputs": inputs,
        "section_files": [p for p in tex_files if any(part in {"sections", "sec"} for part in Path(p).parts[:-1])],
        "tex_files": tex_files,
    }


def scaffold_files() -> dict[str, str]:
    files = {}
    for name, title in SECTIONS:
        if name == "0_abstract.tex":
            text = "% Write the abstract after the main claims and results are established.\n"
        elif name == "X_appendix.tex":
            text = "\\section{Additional Details}\n"
        else:
            text = f"\\section{{{title}}}\n"
        files["sections/" + name] = text
    files["main.tex"] = (
        "\\documentclass{article}\n"
        "\\title{Research Paper}\n\\author{}\n\\date{}\n"
        "\\begin{document}\n\\maketitle\n"
        "\\begin{abstract}\n\\input{sections/0_abstract}\n\\end{abstract}\n"
        + "".join(f"\\input{{sections/{Path(name).stem}}}\n" for name, _ in SECTIONS[1:6])
        + "% Enable when required by the venue:\n% \\input{sections/6_broader_impact}\n"
        "% Add verified citations and the venue's bibliography configuration before enabling:\n"
        "% \\bibliographystyle{plain}\n% \\bibliography{references}\n"
        "% \\appendix\n% \\input{sections/X_appendix}\n"
        "\\end{document}\n"
    )
    files["references.bib"] = "% Add verified bibliography entries here.\n"
    return files


def initialize(repo: str | Path, scaffold: bool = False, local_only: list[str] | None = None) -> dict:
    repo = Path(repo).resolve()
    _check_root(repo)
    paths = [publish.validate_local_path(p) for p in (local_only or [])]
    layout = inspect_layout(repo)
    # Check all scaffold conditions before creating any files, even .writing.
    generated = scaffold_files() if scaffold else {}
    templates = [p for p in repo.rglob("*") if p.suffix.lower() in {".cls", ".sty", ".bst"}
                 and not ({".git", ".writing", ".outputs"} & set(p.relative_to(repo).parts))] if scaffold else []
    if scaffold and (layout["tex_files"] or templates or any((repo / p).exists() or (repo / p).is_symlink() for p in generated)
                     or (repo / "sections").exists() or (repo / "sections").is_symlink()):
        raise ValueError("Existing TeX sources/template detected. Initialize records without --scaffold; preserve the current layout.")
    gitops.ensure_local_excludes(repo, gitops.TEX_LOCAL_EXCLUDES)
    if paths:
        publish.add_local_paths(repo, paths)
    publish.assert_index_safe(repo)
    created = []
    for name, text in generated.items():
        if _write_new(repo / name, text):
            created.append(name)
    if scaffold:
        layout = inspect_layout(repo)
    state = repo / ".writing"
    records = {
        "project.md": "# Paper requirements\n\nRecord the research question, venue/template, language, constraints, available materials, and unresolved decisions. Use supplied information before asking questions.\n",
        "outline.md": "# Chapter plan\n\nMap each active TeX input to its role, required claims, evidence, and completion criteria. Preserve the existing main file and numbering.\n",
        "progress.md": "# Progress\n\n## Current state\nWriting workspace initialized; manuscript content has not been reviewed.\n\n## Next action\nRead the project requirements and active TeX inputs, then record the scoped task.\n\n## Decisions and handoffs\nRecord completed edits, consumed evidence, checks run, outstanding gaps, and the next action.\n",
        "layout.json": json.dumps(layout, indent=2, ensure_ascii=False) + "\n",
    }
    for name, text in records.items():
        if _write_new(state / name, text):
            created.append(".writing/" + name)
    return {"created": created, "state_directory": str(state), "layout": layout,
            "note": "Existing records are preserved. Reconcile layout.json with current TeX inputs on resume."}
