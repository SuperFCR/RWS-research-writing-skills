from click.testing import CliRunner

import overleaf_sync.cli as cli_mod
from overleaf_sync.cli import main
from overleaf_sync.compile import AmbiguousMainError, CompileResult
from overleaf_sync.gitops import GitError
from overleaf_sync.registry import Project
from overleaf_sync.tex import TexNotFoundError


def _stub_resolve(monkeypatch, path="/repo", main_tex=None, engine=None):
    monkeypatch.setattr(
        cli_mod.registry, "get_project",
        lambda alias: Project(alias=alias, path=path,
                              remote="https://git.overleaf.com/PID",
                              main=main_tex, engine=engine))


def test_compile_uses_registry_main_and_engine(monkeypatch):
    _stub_resolve(monkeypatch, path="/repo", main_tex="paper.tex", engine="xelatex")
    captured = {}

    def fake_detect(repo, override=None):
        captured["detect_override"] = override
        return override or "auto.tex"

    def fake_compile(repo, main, engine="pdflatex", auto_install=True, max_retries=5):
        captured.update(repo=str(repo), main=main, engine=engine, auto_install=auto_install)
        return CompileResult(ok=True, pdf_path="/repo/paper.pdf", installed=[], log_tail="")

    monkeypatch.setattr(cli_mod.compile_mod, "detect_main", fake_detect)
    monkeypatch.setattr(cli_mod.compile_mod, "compile_project", fake_compile)

    runner = CliRunner()
    result = runner.invoke(main, ["compile", "mypaper"])

    assert result.exit_code == 0, result.output
    # registry main feeds detect_main as override; registry engine is used
    assert captured["detect_override"] == "paper.tex"
    assert captured["main"] == "paper.tex"
    assert captured["engine"] == "xelatex"
    assert captured["auto_install"] is True
    assert "/repo/paper.pdf" in result.output


def test_compile_flags_override_registry_and_no_auto_install(monkeypatch):
    _stub_resolve(monkeypatch, path="/repo", main_tex="paper.tex", engine="xelatex")
    captured = {}
    monkeypatch.setattr(cli_mod.compile_mod, "detect_main",
                        lambda repo, override=None: override)
    monkeypatch.setattr(
        cli_mod.compile_mod, "compile_project",
        lambda repo, main, engine="pdflatex", auto_install=True, max_retries=5:
            captured.update(main=main, engine=engine, auto_install=auto_install)
            or CompileResult(ok=True, pdf_path="/repo/m.pdf", installed=[], log_tail=""))

    runner = CliRunner()
    result = runner.invoke(
        main, ["compile", "mypaper", "--main", "m.tex",
               "--engine", "lualatex", "--no-auto-install"])

    assert result.exit_code == 0, result.output
    assert captured["main"] == "m.tex"
    assert captured["engine"] == "lualatex"
    assert captured["auto_install"] is False


def test_compile_open_opens_pdf(monkeypatch):
    _stub_resolve(monkeypatch, path="/repo", main_tex="paper.tex", engine=None)
    opened = {}
    monkeypatch.setattr(cli_mod.compile_mod, "detect_main",
                        lambda repo, override=None: override or "paper.tex")
    monkeypatch.setattr(
        cli_mod.compile_mod, "compile_project",
        lambda repo, main, engine="pdflatex", auto_install=True, max_retries=5:
            CompileResult(ok=True, pdf_path="/repo/paper.pdf", installed=["tikz"], log_tail=""))
    monkeypatch.setattr(cli_mod.subprocess, "run",
                        lambda args, **kw: opened.update(args=args))

    runner = CliRunner()
    result = runner.invoke(main, ["compile", "mypaper", "--open"])

    assert result.exit_code == 0, result.output
    # default engine when registry engine is None
    assert opened["args"] == ["open", "/repo/paper.pdf"]
    assert "tikz" in result.output


def test_compile_failure_exits_1_and_prints_log(monkeypatch):
    _stub_resolve(monkeypatch, path="/repo", main_tex="paper.tex", engine=None)
    monkeypatch.setattr(cli_mod.compile_mod, "detect_main",
                        lambda repo, override=None: override or "paper.tex")
    monkeypatch.setattr(
        cli_mod.compile_mod, "compile_project",
        lambda repo, main, engine="pdflatex", auto_install=True, max_retries=5:
            CompileResult(ok=False, pdf_path=None, installed=[],
                          log_tail="! Undefined control sequence."))
    runner = CliRunner()
    result = runner.invoke(main, ["compile", "mypaper"])
    assert result.exit_code == 1
    assert "Undefined control sequence" in result.output


def test_compile_ambiguous_main_exits_1(monkeypatch):
    _stub_resolve(monkeypatch, path="/repo", main_tex=None, engine=None)

    def boom(repo, override=None):
        raise AmbiguousMainError("multiple main-file candidates: a.tex, b.tex; specify one with --main")
    monkeypatch.setattr(cli_mod.compile_mod, "detect_main", boom)

    runner = CliRunner()
    result = runner.invoke(main, ["compile", "mypaper"])
    assert result.exit_code == 1
    assert "multiple main-file candidates" in result.output


def test_compile_tex_not_found_exits_1_with_setup_hint(monkeypatch):
    _stub_resolve(monkeypatch, path="/repo", main_tex="paper.tex", engine=None)
    monkeypatch.setattr(cli_mod.compile_mod, "detect_main",
                        lambda repo, override=None: override or "paper.tex")

    def boom(repo, main, engine="pdflatex", auto_install=True, max_retries=5):
        raise TexNotFoundError("找不到 TeX 工具 'latexmk'。")
    monkeypatch.setattr(cli_mod.compile_mod, "compile_project", boom)

    runner = CliRunner()
    result = runner.invoke(main, ["compile", "mypaper"])
    assert result.exit_code == 1
    assert "setup.sh" in result.output


def test_compile_bad_engine_value_error_exits_1(monkeypatch):
    _stub_resolve(monkeypatch, path="/repo", main_tex="paper.tex", engine=None)
    monkeypatch.setattr(cli_mod.compile_mod, "detect_main",
                        lambda repo, override=None: override or "paper.tex")

    def boom(repo, main, engine="pdflatex", auto_install=True, max_retries=5):
        raise ValueError("unknown engine 'dvipdf'; expected one of ['lualatex', 'pdflatex', 'xelatex']")
    monkeypatch.setattr(cli_mod.compile_mod, "compile_project", boom)

    runner = CliRunner()
    result = runner.invoke(main, ["compile", "mypaper", "--engine", "dvipdf"])
    assert result.exit_code == 1
    assert "unknown engine" in result.output


def test_compile_giterror_exits_1(monkeypatch):
    _stub_resolve(monkeypatch, path="/repo", main_tex="paper.tex", engine=None)
    monkeypatch.setattr(cli_mod.compile_mod, "detect_main",
                        lambda repo, override=None: override or "paper.tex")

    def boom(repo, main, engine="pdflatex", auto_install=True, max_retries=5):
        raise GitError("git ... failed")
    monkeypatch.setattr(cli_mod.compile_mod, "compile_project", boom)

    runner = CliRunner()
    result = runner.invoke(main, ["compile", "mypaper"])
    assert result.exit_code == 1
    assert "git ... failed" in result.output


def test_compile_prompts_choice_on_multiple_mains_and_remembers(monkeypatch):
    """User request: when several main candidates exist, offer an interactive
    numbered choice, then persist it to the registry so it's asked only once."""
    _stub_resolve(monkeypatch, path="/repo", main_tex=None, engine=None)
    err = AmbiguousMainError(
        "multiple main-file candidates: a/main.tex, b/main.tex; specify one with --main",
        candidates=["a/main.tex", "b/main.tex"])
    monkeypatch.setattr(cli_mod.compile_mod, "detect_main",
                        lambda repo, override=None: (_ for _ in ()).throw(err)
                        if override is None else override)
    captured = {}
    monkeypatch.setattr(
        cli_mod.compile_mod, "compile_project",
        lambda repo, main, engine="pdflatex", auto_install=True, max_retries=5:
            captured.update(main=main)
            or CompileResult(ok=True, pdf_path="/repo/b/.outputs/main.pdf",
                             installed=[], log_tail=""))
    saved = {}
    reg = {"mypaper": Project(alias="mypaper", path="/repo",
                              remote="https://git.overleaf.com/PID")}
    monkeypatch.setattr(cli_mod.registry, "load_registry", lambda: reg)
    monkeypatch.setattr(cli_mod.registry, "save_registry",
                        lambda projects: saved.update(projects))

    runner = CliRunner()
    result = runner.invoke(main, ["compile", "mypaper"], input="2\n")

    assert result.exit_code == 0, result.output
    assert "a/main.tex" in result.output and "b/main.tex" in result.output
    assert captured["main"] == "b/main.tex"
    assert saved["mypaper"].main == "b/main.tex"


def test_compile_ambiguous_no_input_still_exits_1(monkeypatch):
    """Non-interactive (EOF on stdin) keeps the clean error exit."""
    _stub_resolve(monkeypatch, path="/repo", main_tex=None, engine=None)
    err = AmbiguousMainError("multiple main-file candidates: a.tex, b.tex",
                             candidates=["a.tex", "b.tex"])
    monkeypatch.setattr(cli_mod.compile_mod, "detect_main",
                        lambda repo, override=None: (_ for _ in ()).throw(err))
    result = CliRunner().invoke(main, ["compile", "mypaper"], input="")
    assert result.exit_code == 1


def test_compile_open_uses_startfile_on_windows(monkeypatch):
    """--open must not call the mac-only `open` on Windows."""
    _stub_resolve(monkeypatch, path="/repo", main_tex="paper.tex", engine=None)
    monkeypatch.setattr(cli_mod.compile_mod, "detect_main",
                        lambda repo, override=None: override or "paper.tex")
    monkeypatch.setattr(
        cli_mod.compile_mod, "compile_project",
        lambda repo, main, engine="pdflatex", auto_install=True, max_retries=5:
            CompileResult(ok=True, pdf_path="/repo/.outputs/paper.pdf",
                          installed=[], log_tail=""))
    opened = {}
    monkeypatch.setattr(cli_mod.sys, "platform", "win32")
    monkeypatch.setattr(cli_mod.os, "startfile",
                        lambda p: opened.update(path=p), raising=False)
    ran = {}
    monkeypatch.setattr(cli_mod.subprocess, "run",
                        lambda args, **kw: ran.update(args=args))

    result = CliRunner().invoke(main, ["compile", "mypaper", "--open"])

    assert result.exit_code == 0, result.output
    assert opened["path"] == "/repo/.outputs/paper.pdf"
    assert not ran  # no `open` subprocess on windows
