from overleaf_sync import compile as cmpl
from overleaf_sync.compile import CompileResult

MISSING_TIKZ_LOG = "! LaTeX Error: File `tikz.sty' not found.\n"
CLEAN_LOG = "Output written on main.pdf (1 page, 1234 bytes).\n"


def _write_output_pdf(root):
    out_dir = root / ".outputs"
    out_dir.mkdir()
    pdf_path = out_dir / "main.pdf"
    pdf_path.write_bytes(b"%PDF-1.5\n")
    return pdf_path


def test_compile_succeeds_first_try_no_install(tmp_path, monkeypatch):
    pdf_path = _write_output_pdf(tmp_path)
    monkeypatch.setattr(cmpl, "run_latexmk", lambda repo, main, engine: (0, CLEAN_LOG))

    installed_calls = []
    monkeypatch.setattr(cmpl.tex, "tlmgr_install", lambda pkgs: installed_calls.append(pkgs))
    monkeypatch.setattr(cmpl.tex, "tlmgr_search_file", lambda f: [])

    result = cmpl.compile_project(tmp_path, "main.tex", engine="pdflatex")

    assert isinstance(result, CompileResult)
    assert result.ok is True
    assert result.installed == []
    assert result.pdf_path == str(pdf_path)
    assert installed_calls == []  # nothing installed on clean success


def test_compile_installs_missing_pkg_then_retries_and_succeeds(tmp_path, monkeypatch):
    # 1st run fails with missing tikz.sty; 2nd run succeeds.
    runs = iter([(12, MISSING_TIKZ_LOG), (0, CLEAN_LOG)])
    monkeypatch.setattr(cmpl, "run_latexmk", lambda repo, main, engine: next(runs))

    searched = []
    installed = []
    monkeypatch.setattr(cmpl.tex, "tlmgr_search_file", lambda f: (searched.append(f) or ["pgf"]))
    monkeypatch.setattr(cmpl.tex, "tlmgr_install", lambda pkgs: installed.append(list(pkgs)))

    pdf_path = _write_output_pdf(tmp_path)

    result = cmpl.compile_project(tmp_path, "main.tex", engine="pdflatex", auto_install=True)

    assert result.ok is True
    assert searched == ["tikz.sty"]
    assert installed == [["pgf"]]
    assert result.installed == ["pgf"]
    assert result.pdf_path == str(pdf_path)


def test_compile_respects_max_retries_cap(tmp_path, monkeypatch):
    # Each round surfaces a genuinely NEW missing package, so the loop keeps
    # making progress and is only stopped by the max_retries cap (not the
    # early-stop "nothing new" guard, which is covered separately).
    run_count = {"n": 0}

    def counting_run(repo, main, engine):
        run_count["n"] += 1
        return (12, f"! LaTeX Error: File `pkg{run_count['n']}.sty' not found.\n")

    monkeypatch.setattr(cmpl, "run_latexmk", counting_run)
    # Resolve "pkgN.sty" -> a unique package name each round.
    monkeypatch.setattr(cmpl.tex, "tlmgr_search_file",
                        lambda f: [f.replace(".sty", "")])
    monkeypatch.setattr(cmpl.tex, "tlmgr_install", lambda pkgs: None)

    result = cmpl.compile_project(tmp_path, "main.tex", auto_install=True, max_retries=3)

    assert result.ok is False
    # initial attempt + up to max_retries retries == max_retries + 1 latexmk runs
    assert run_count["n"] == 4
    assert result.pdf_path is None
    assert "not found" in result.log_tail


def test_compile_does_not_reinstall_already_installed_pkg(tmp_path, monkeypatch):
    # Two distinct missing packages across rounds; the first reappears in the
    # second round's log but must NOT be re-installed (it's already cumulative).
    # Round 1: tikz.sty missing -> install pgf.
    # Round 2: tikz.sty STILL reported + amsmath.sty missing -> only amsmath new.
    # Round 3: clean.
    log1 = "! LaTeX Error: File `tikz.sty' not found.\n"
    log2 = ("! LaTeX Error: File `tikz.sty' not found.\n"
            "! LaTeX Error: File `amsmath.sty' not found.\n")
    runs = iter([(12, log1), (12, log2), (0, CLEAN_LOG)])
    monkeypatch.setattr(cmpl, "run_latexmk", lambda repo, main, engine: next(runs))

    search_map = {"tikz.sty": ["pgf"], "amsmath.sty": ["amsmath"]}
    monkeypatch.setattr(cmpl.tex, "tlmgr_search_file", lambda f: search_map[f])

    installed_rounds = []
    monkeypatch.setattr(cmpl.tex, "tlmgr_install",
                        lambda pkgs: installed_rounds.append(list(pkgs)))

    _write_output_pdf(tmp_path)

    result = cmpl.compile_project(tmp_path, "main.tex", engine="pdflatex", auto_install=True)

    assert result.ok is True
    # pgf installed in round 1; round 2 installs only the genuinely new amsmath.
    assert installed_rounds == [["pgf"], ["amsmath"]]
    assert result.installed == ["pgf", "amsmath"]  # deduped, order-preserving


def test_compile_stops_early_when_no_new_pkg(tmp_path, monkeypatch):
    # Same missing package every round; once installed, no NEW package remains,
    # so the loop must stop early rather than burning all max_retries.
    monkeypatch.setattr(cmpl, "run_latexmk",
                        lambda repo, main, engine: (12, MISSING_TIKZ_LOG))
    monkeypatch.setattr(cmpl.tex, "tlmgr_search_file", lambda f: ["pgf"])

    install_rounds = []
    monkeypatch.setattr(cmpl.tex, "tlmgr_install",
                        lambda pkgs: install_rounds.append(list(pkgs)))

    result = cmpl.compile_project(tmp_path, "main.tex", auto_install=True, max_retries=5)

    assert result.ok is False
    # pgf installed exactly once; second round finds nothing new -> stop early.
    assert install_rounds == [["pgf"]]
    assert result.installed == ["pgf"]


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


def test_compile_project_subdir_main_pdf_path(tmp_path, monkeypatch):
    """pdf_path must point at <subdir>/.outputs/<stem>.pdf for subfolder mains."""
    out = tmp_path / "T2V" / ".outputs"
    out.mkdir(parents=True)
    (out / "main.pdf").write_bytes(b"%PDF-fake")
    monkeypatch.setattr(cmpl, "run_latexmk", lambda repo, main, engine: (0, "ok"))

    result = cmpl.compile_project(tmp_path, "T2V/main.tex")

    assert result.ok is True
    assert result.pdf_path == str(out / "main.pdf")
