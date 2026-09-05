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


def test_detect_main_finds_main_in_subdir(tmp_path):
    """Overleaf projects often keep content in a folder (e.g. T2V/main.tex);
    detect_main must search subdirectories, returning a root-relative path."""
    sub = tmp_path / "T2V"
    sub.mkdir()
    (sub / "main.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\nx\n\\end{document}\n")
    assert detect_main(tmp_path) == "T2V/main.tex"


def test_detect_main_ignores_git_and_outputs_dirs(tmp_path):
    for noise in (".git", ".outputs"):
        d = tmp_path / noise
        d.mkdir()
        (d / "decoy.tex").write_text(
            "\\documentclass{article}\n\\begin{document}\n\\end{document}\n")
    sub = tmp_path / "src"
    sub.mkdir()
    (sub / "real.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\n\\end{document}\n")
    assert detect_main(tmp_path) == "src/real.tex"


def test_detect_main_root_candidate_wins_over_subdir(tmp_path):
    (tmp_path / "main.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\n\\end{document}\n")
    sub = tmp_path / "old"
    sub.mkdir()
    (sub / "main.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\n\\end{document}\n")
    assert detect_main(tmp_path) == "main.tex"


def test_detect_main_multiple_subdir_candidates_ambiguous(tmp_path):
    for name in ("a", "b"):
        d = tmp_path / name
        d.mkdir()
        (d / "main.tex").write_text(
            "\\documentclass{article}\n\\begin{document}\n\\end{document}\n")
    with pytest.raises(AmbiguousMainError) as exc:
        detect_main(tmp_path)
    assert "a/main.tex" in str(exc.value) and "b/main.tex" in str(exc.value)
