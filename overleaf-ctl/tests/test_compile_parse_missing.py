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


LOG_FONT_TFM_MISSING = r"""
LaTeX Font Info:    Trying to load font information for OT1+ppl on input line 503.
(/Users/falcary/Library/TinyTeX/texmf-dist/tex/latex/psnfss/ot1ppl.fd
File: ot1ppl.fd 2001/06/04 font definitions for OT1/ppl.
)
! Font OT1/ppl/m/n/10=pplr7t at 10.0pt not loadable: Metric (TFM) file not
found.
<to be read again>
                   relax
!  ==> Fatal error occurred, no output PDF file produced!
"""


def test_parse_missing_files_font_tfm_not_loadable():
    """Real pdflatex log: missing Palatino metrics surface as a Font ...
    'Metric (TFM) file not found' error, NOT a 'File ... not found' line.
    The error wraps across lines ('not \nfound.')."""
    assert parse_missing_files(LOG_FONT_TFM_MISSING) == ["pplr7t.tfm"]


LOG_BST_MISSING = r"""
This is BibTeX, Version 0.99e (TeX Live 2026)
The top-level auxiliary file: main.aux
I couldn't open style file IEEEtran.bst
---line 41 of file main.aux
I found no style file---while reading file main.aux
"""


def test_parse_missing_files_bibtex_style():
    """bibtex reports a missing .bst in the .blg transcript with its own
    error shape — must map to the .bst filename for tlmgr search."""
    assert parse_missing_files(LOG_BST_MISSING) == ["IEEEtran.bst"]


LOG_BABEL_UNKNOWN_OPTION = r"""
(/Users/falcary/Library/TinyTeX/texmf-dist/tex/generic/babel/errbabel.def)

! Package babel Error: Unknown option 'latin'.

See the babel package documentation for explanation.
"""


def test_parse_missing_files_babel_language_option():
    """babel reports a missing language .ldf as 'Unknown option', not as a
    file-not-found — map it to <lang>.ldf for tlmgr file search
    (e.g. latin.ldf -> babel-latin)."""
    assert parse_missing_files(LOG_BABEL_UNKNOWN_OPTION) == ["latin.ldf"]
