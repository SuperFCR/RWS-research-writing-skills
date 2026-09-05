# overleaf_sync/compile.py
from __future__ import annotations

import os
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

OUTPUT_DIR_NAME = ".outputs"


@dataclass
class CompileResult:
    ok: bool
    pdf_path: str | None
    installed: list[str] = field(default_factory=list)
    log_tail: str = ""


def _log_tail(log_text: str, lines: int = 40) -> str:
    """Return the last ``lines`` lines of a log, for user-facing diagnostics."""
    return "\n".join(log_text.splitlines()[-lines:])


def output_dir(repo: str | Path) -> Path:
    """Return the local-only directory used for LaTeX build outputs."""
    return Path(repo) / OUTPUT_DIR_NAME


def engine_flag(engine: str) -> str:
    """Map a TeX engine name to its latexmk switch."""
    try:
        return _ENGINE_FLAGS[engine]
    except KeyError:
        raise ValueError(
            f"unknown engine {engine!r}; expected one of {sorted(_ENGINE_FLAGS)}"
        ) from None


# Patterns that match latexmk/pdflatex "file not found" diagnostics.
# Covers missing .sty (packages), .cls (document classes), and .fd (font defs).
MISSING_FILE_RE: list[re.Pattern] = [
    re.compile(r"! LaTeX Error: File `([^']+\.(?:sty|cls|fd))' not found\."),
    re.compile(r"! LaTeX Error: File `([^']+\.(?:sty|cls|fd))' not found"),
]

# Missing font metrics surface as a different error shape, e.g.
#   ! Font OT1/ppl/m/n/10=pplr7t at 10.0pt not loadable: Metric (TFM) file not
#   found.
# (the log wraps lines, so "not / found" may span a newline). The captured
# font name maps to "<name>.tfm" for tlmgr file search.
_FONT_TFM_RE = re.compile(
    r"! Font [^=\n]+=([A-Za-z0-9\-]+)[^\n]*not loadable: "
    r"Metric \(TFM\) file not\s+found"
)

# bibtex reports a missing bibliography style in the .blg transcript:
#   I couldn't open style file IEEEtran.bst
_BST_MISSING_RE = re.compile(r"I couldn't open style file (\S+\.bst)")

# babel reports a missing language definition (<lang>.ldf) as an option error:
#   ! Package babel Error: Unknown option 'latin'.
# Map the option to <lang>.ldf so tlmgr file search resolves the language
# package (e.g. latin.ldf -> babel-latin). Tolerate ` or ' as the open quote.
_BABEL_OPTION_RE = re.compile(
    r"! Package babel Error: Unknown option [`']([A-Za-z0-9\-]+)'"
)


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
    for match in _FONT_TFM_RE.finditer(log_text):
        name = match.group(1) + ".tfm"
        if name not in seen:
            seen.add(name)
            found.append(name)
    for match in _BST_MISSING_RE.finditer(log_text):
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            found.append(name)
    for match in _BABEL_OPTION_RE.finditer(log_text):
        name = match.group(1) + ".ldf"
        if name not in seen:
            seen.add(name)
            found.append(name)
    return found


class AmbiguousMainError(RuntimeError):
    """Raised when the main .tex file cannot be uniquely determined.

    ``candidates`` carries the root-relative candidate paths (empty when none
    were found) so interactive callers can offer a choice.
    """

    def __init__(self, message: str, candidates: list[str] | None = None):
        super().__init__(message)
        self.candidates: list[str] = candidates or []


_DOCUMENTCLASS_RE = re.compile(r"\\documentclass")
_BEGIN_DOCUMENT_RE = re.compile(r"\\begin\{document\}")

# Directories never containing user sources: VCS data and our build outputs.
_DETECT_SKIP_DIRS = {".git", ".writing", OUTPUT_DIR_NAME}


def _is_main_candidate(tex_path: Path) -> bool:
    try:
        text = tex_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return bool(_DOCUMENTCLASS_RE.search(text) and _BEGIN_DOCUMENT_RE.search(text))


def detect_main(repo: str | Path, override: str | None = None) -> str:
    """Determine the main .tex file for a project (root-relative path).

    Precedence: an explicit ``override`` wins outright. Otherwise look for
    .tex files containing both ``\\documentclass`` and ``\\begin{document}``:
    first in the repo root (a unique root candidate wins), then recursively in
    subdirectories (Overleaf projects often keep content in a folder, e.g.
    ``T2V/main.tex``), skipping ``.git`` and the build-output dir. Exactly one
    candidate overall is the main file; zero or several raise
    :class:`AmbiguousMainError` (with ``.candidates`` filled in).
    """
    if override is not None:
        return override

    root = Path(repo)
    candidates = [
        p.name for p in sorted(root.glob("*.tex")) if _is_main_candidate(p)
    ]
    if not candidates:
        candidates = [
            str(p.relative_to(root))
            for p in sorted(root.rglob("*.tex"))
            if not (set(p.relative_to(root).parts[:-1]) & _DETECT_SKIP_DIRS)
            and _is_main_candidate(p)
        ]

    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise AmbiguousMainError(
            f"no .tex file with \\documentclass and \\begin{{document}} found "
            f"in {root} (searched subdirectories too); specify one with --main"
        )
    raise AmbiguousMainError(
        "multiple main-file candidates: "
        + ", ".join(candidates)
        + "; specify one with --main",
        candidates=candidates,
    )


def run_latexmk(repo: str | Path, main: str, engine: str) -> tuple[int, str]:
    """Run ``latexmk`` once for ``main`` in ``repo`` and return (rc, log_text).

    latexmk writes all build outputs under ``.outputs/``. The log text is read
    from ``.outputs/<main-stem>.log``; if absent, an empty string is returned.
    """
    root = Path(repo)
    # The main file may live in a project subfolder (Overleaf folder layouts,
    # e.g. T2V/main.tex). Run latexmk from THAT folder so the document's
    # relative \input/\bibliography paths resolve; outputs go to
    # <that folder>/.outputs/.
    workdir = root / Path(main).parent
    main_name = Path(main).name
    out_dir = output_dir(workdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    latexmk = tex.require_tool("latexmk")
    # latexmk resolves pdflatex/xelatex via PATH; TinyTeX's bin dir is usually
    # not on the user's PATH, so prepend the located latexmk's own dir.
    env = dict(os.environ)
    env["PATH"] = f"{Path(latexmk).parent}{os.pathsep}{env.get('PATH', '')}"
    argv = [
        latexmk,
        engine_flag(engine),
        # -g: force processing even if latexmk thinks targets are up-to-date.
        # Without it, latexmk's cached failure state (.fdb_latexmk) skips the
        # TeX rerun after tlmgr installs a missing package (sources unchanged),
        # making the auto-install retry loop a no-op.
        "-g",
        f"-outdir={OUTPUT_DIR_NAME}",
        "-interaction=nonstopmode",
        "-halt-on-error",
        main_name,
    ]
    completed = subprocess.run(
        argv,
        cwd=str(workdir),
        env=env,
        capture_output=True,
        text=True,
    )
    stem = Path(main).stem
    log_text = ""
    log_path = out_dir / (stem + ".log")
    if log_path.exists():
        log_text = log_path.read_text(encoding="utf-8", errors="ignore")
    # bibtex's transcript lives in <stem>.blg; append it so missing-.bst
    # errors are visible to the auto-install loop.
    blg_path = out_dir / (stem + ".blg")
    if blg_path.exists():
        log_text += "\n" + blg_path.read_text(encoding="utf-8", errors="ignore")
    return completed.returncode, log_text


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
    # Outputs live next to the main file's folder (see run_latexmk).
    pdf_path = output_dir(root / Path(main).parent) / (Path(main).stem + ".pdf")

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
                # Skip anything already installed in a prior round so we don't
                # re-install the same package on every retry.
                if pkg not in installed and pkg not in newly_installed:
                    newly_installed.append(pkg)

        if not newly_installed:
            # No genuinely new package this round -> stop to avoid a dead loop.
            return CompileResult(
                ok=False,
                pdf_path=None,
                installed=installed,
                log_tail=_log_tail(log_text),
            )

        tex.tlmgr_install(newly_installed)
        for pkg in newly_installed:
            if pkg not in installed:
                installed.append(pkg)
