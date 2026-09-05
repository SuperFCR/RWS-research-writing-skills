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

    # latexmk writes <main>.log into .outputs; simulate it.
    (tmp_path / ".outputs").mkdir()
    (tmp_path / ".outputs" / "main.log").write_text(
        "Output written on main.pdf (1 page)")

    rc, log_text = cmpl.run_latexmk(tmp_path, "main.tex", "xelatex")

    assert rc == 0
    assert log_text == "Output written on main.pdf (1 page)"
    argv = calls["argv"]
    assert argv[0] == "/fake/bin/latexmk"
    assert "-xelatex" in argv
    assert "-outdir=.outputs" in argv
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
    assert (tmp_path / ".outputs").is_dir()


def test_run_latexmk_ignores_stale_root_log(tmp_path, monkeypatch):
    """Root-level logs from old compiles must not be used after switching to
    .outputs; otherwise stale diagnostics can drive wrong auto-installs."""
    monkeypatch.setattr(cmpl.tex, "require_tool", lambda name: "/fake/bin/latexmk")

    class FakeCompleted:
        returncode = 0

    monkeypatch.setattr(cmpl.subprocess, "run", lambda *a, **k: FakeCompleted())
    (tmp_path / "main.log").write_text("stale root log")
    (tmp_path / ".outputs").mkdir()
    (tmp_path / ".outputs" / "main.log").write_text("fresh output log")

    rc, log_text = cmpl.run_latexmk(tmp_path, "main.tex", "pdflatex")

    assert rc == 0
    assert log_text == "fresh output log"


def test_run_latexmk_prepends_tex_bindir_to_subprocess_path(tmp_path, monkeypatch):
    """latexmk internally invokes pdflatex/xelatex via PATH, so the located
    latexmk's own bin dir must be prepended to the subprocess env PATH
    (TinyTeX's bin dir is normally NOT on the user's PATH)."""
    calls = {}

    monkeypatch.setattr(
        cmpl.tex, "require_tool", lambda name: "/fake/texbin/latexmk")

    class FakeCompleted:
        returncode = 0

    def fake_run(argv, cwd=None, env=None, **kwargs):
        calls["env"] = env
        return FakeCompleted()

    monkeypatch.setattr(cmpl.subprocess, "run", fake_run)

    cmpl.run_latexmk(tmp_path, "main.tex", "pdflatex")

    env = calls["env"]
    assert env is not None, "run_latexmk must pass an env to subprocess.run"
    assert env["PATH"].startswith("/fake/texbin"), env["PATH"]
    # the rest of the parent PATH must be preserved
    import os
    assert os.environ["PATH"] in env["PATH"]


def test_run_latexmk_forces_processing_with_g_flag(tmp_path, monkeypatch):
    """latexmk caches failure state in .fdb_latexmk: after a failed run with
    unchanged sources it skips rerunning TeX entirely — but our auto-install
    retry loop changes the TeX TREE (tlmgr install), not the source files,
    so every retry must force processing with -g."""
    calls = {}
    monkeypatch.setattr(cmpl.tex, "require_tool", lambda name: "/fake/bin/latexmk")

    class FakeCompleted:
        returncode = 0

    def fake_run(argv, **kwargs):
        calls["argv"] = argv
        return FakeCompleted()

    monkeypatch.setattr(cmpl.subprocess, "run", fake_run)
    cmpl.run_latexmk(tmp_path, "main.tex", "pdflatex")
    assert "-g" in calls["argv"]


def test_run_latexmk_includes_blg_transcript(tmp_path, monkeypatch):
    """bibtex errors live in <stem>.blg, not <stem>.log — run_latexmk must
    surface both so the auto-install loop can see missing .bst files."""
    monkeypatch.setattr(cmpl.tex, "require_tool", lambda name: "/fake/bin/latexmk")

    class FakeCompleted:
        returncode = 12

    monkeypatch.setattr(cmpl.subprocess, "run", lambda *a, **k: FakeCompleted())
    (tmp_path / ".outputs").mkdir()
    (tmp_path / ".outputs" / "main.log").write_text("tex part ok")
    (tmp_path / ".outputs" / "main.blg").write_text(
        "I couldn't open style file IEEEtran.bst")

    rc, log_text = cmpl.run_latexmk(tmp_path, "main.tex", "pdflatex")
    assert rc == 12
    assert "tex part ok" in log_text
    assert "IEEEtran.bst" in log_text


def test_run_latexmk_subdir_main_runs_in_that_dir(tmp_path, monkeypatch):
    """When the main file lives in a subfolder (Overleaf folder layouts, e.g.
    T2V/main.tex), latexmk must run from that folder so relative \\input
    paths resolve; outputs land in <subdir>/.outputs/."""
    calls = {}
    monkeypatch.setattr(cmpl.tex, "require_tool", lambda name: "/fake/bin/latexmk")

    class FakeCompleted:
        returncode = 0

    def fake_run(argv, cwd=None, **kwargs):
        calls["argv"] = argv
        calls["cwd"] = cwd
        return FakeCompleted()

    monkeypatch.setattr(cmpl.subprocess, "run", fake_run)
    sub = tmp_path / "T2V"
    (sub / ".outputs").mkdir(parents=True)
    (sub / ".outputs" / "main.log").write_text("from subdir")

    rc, log_text = cmpl.run_latexmk(tmp_path, "T2V/main.tex", "pdflatex")

    assert rc == 0
    assert log_text == "from subdir"
    assert str(calls["cwd"]) == str(sub)
    assert calls["argv"][-1] == "main.tex"
