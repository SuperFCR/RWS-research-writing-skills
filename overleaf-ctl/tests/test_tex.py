from pathlib import Path

import overleaf_sync.tex as tex


def test_locate_tool_prefers_path(monkeypatch):
    """shutil.which hit wins over any fallback."""
    monkeypatch.setattr(tex.shutil, "which", lambda name: "/usr/local/bin/latexmk")
    assert tex.locate_tool("latexmk") == "/usr/local/bin/latexmk"


def test_locate_tool_falls_back_to_tinytex(monkeypatch, tmp_path):
    """When not on PATH, glob ~/Library/TinyTeX/bin/*/ for the tool."""
    monkeypatch.setattr(tex.shutil, "which", lambda name: None)
    bindir = tmp_path / "Library" / "TinyTeX" / "bin" / "universal-darwin"
    bindir.mkdir(parents=True)
    tool = bindir / "tlmgr"
    tool.write_text("#!/bin/sh\n")
    monkeypatch.setattr(tex.Path, "home", classmethod(lambda cls: tmp_path))
    # MacTeX dir must not exist for this machine
    monkeypatch.setattr(tex, "MACTEX_BIN", tmp_path / "nope")
    assert tex.locate_tool("tlmgr") == str(tool)


def test_locate_tool_falls_back_to_mactex(monkeypatch, tmp_path):
    """When not on PATH and no TinyTeX, use MacTeX texbin."""
    monkeypatch.setattr(tex.shutil, "which", lambda name: None)
    monkeypatch.setattr(tex.Path, "home", classmethod(lambda cls: tmp_path))  # no TinyTeX under here
    mactex = tmp_path / "texbin"
    mactex.mkdir(parents=True)
    tool = mactex / "latexmk"
    tool.write_text("#!/bin/sh\n")
    monkeypatch.setattr(tex, "MACTEX_BIN", mactex)
    assert tex.locate_tool("latexmk") == str(tool)


def test_locate_tool_returns_none_when_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(tex.shutil, "which", lambda name: None)
    monkeypatch.setattr(tex.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(tex, "MACTEX_BIN", tmp_path / "nope")
    assert tex.locate_tool("latexmk") is None


import pytest


def test_require_tool_returns_path_when_found(monkeypatch):
    monkeypatch.setattr(tex, "locate_tool", lambda name: "/abs/bin/latexmk")
    assert tex.require_tool("latexmk") == "/abs/bin/latexmk"


def test_require_tool_raises_with_setup_hint(monkeypatch):
    monkeypatch.setattr(tex, "locate_tool", lambda name: None)
    with pytest.raises(tex.TexNotFoundError) as ei:
        tex.require_tool("latexmk")
    msg = str(ei.value)
    assert "latexmk" in msg
    assert "setup.sh" in msg


# Real `tlmgr search --global --file "/tikz.sty"` output shape:
#   each matching package starts flush-left with "<pkg>:" then indented file lines.
TLMGR_TIKZ_OUTPUT = """\
tlmgr: package repository https://mirror.ctan.org/systems/texlive/tlnet
pgf:
\ttexmf-dist/tex/generic/pgf/frontendlayer/tikz.sty
\ttexmf-dist/tex/latex/pgf/frontendlayer/tikz.sty
"""

# `tlmgr search --global --file "/algorithm.sty"` returns multiple packages:
TLMGR_MULTI_OUTPUT = """\
tlmgr: package repository https://mirror.ctan.org/systems/texlive/tlnet
algorithm2e:
\ttexmf-dist/tex/latex/algorithm2e/algorithm2e.sty
algorithms:
\ttexmf-dist/tex/latex/algorithms/algorithm.sty
"""

TLMGR_EMPTY_OUTPUT = """\
tlmgr: package repository https://mirror.ctan.org/systems/texlive/tlnet
"""


def _run_tlmgr_stub(output):
    class _CP:
        def __init__(self, out):
            self.stdout = out
            self.returncode = 0
    def runner(*args, **kwargs):
        return _CP(output)
    return runner


def test_tlmgr_search_file_single_package(monkeypatch):
    monkeypatch.setattr(tex, "require_tool", lambda name: "/abs/bin/tlmgr")
    monkeypatch.setattr(tex.subprocess, "run", _run_tlmgr_stub(TLMGR_TIKZ_OUTPUT))
    assert tex.tlmgr_search_file("tikz.sty") == ["pgf"]


def test_tlmgr_search_file_multiple_packages_order_preserving(monkeypatch):
    monkeypatch.setattr(tex, "require_tool", lambda name: "/abs/bin/tlmgr")
    monkeypatch.setattr(tex.subprocess, "run", _run_tlmgr_stub(TLMGR_MULTI_OUTPUT))
    assert tex.tlmgr_search_file("algorithm.sty") == ["algorithm2e", "algorithms"]


def test_tlmgr_search_file_no_match(monkeypatch):
    monkeypatch.setattr(tex, "require_tool", lambda name: "/abs/bin/tlmgr")
    monkeypatch.setattr(tex.subprocess, "run", _run_tlmgr_stub(TLMGR_EMPTY_OUTPUT))
    assert tex.tlmgr_search_file("nope.sty") == []


def test_tlmgr_search_file_invokes_global_file_flags(monkeypatch):
    """Argv must use --global --file with a leading-slash filename."""
    captured = {}
    monkeypatch.setattr(tex, "require_tool", lambda name: "/abs/bin/tlmgr")

    class _CP:
        stdout = TLMGR_TIKZ_OUTPUT
        returncode = 0

    def runner(argv, *a, **k):
        captured["argv"] = argv
        return _CP()

    monkeypatch.setattr(tex.subprocess, "run", runner)
    tex.tlmgr_search_file("tikz.sty")
    argv = captured["argv"]
    assert argv[0] == "/abs/bin/tlmgr"
    assert "--global" in argv
    assert "--file" in argv
    assert "/tikz.sty" in argv  # leading slash anchors the basename


def test_tlmgr_install_invokes_tlmgr_install_with_packages(monkeypatch):
    captured = {}
    monkeypatch.setattr(tex, "require_tool", lambda name: "/abs/bin/tlmgr")

    def runner(argv, *a, **k):
        captured["argv"] = argv
        captured["check"] = k.get("check")
        class _CP:
            returncode = 0
        return _CP()

    monkeypatch.setattr(tex.subprocess, "run", runner)
    tex.tlmgr_install(["pgf", "algorithm2e"])
    assert captured["argv"] == ["/abs/bin/tlmgr", "install", "pgf", "algorithm2e"]


def test_tlmgr_install_empty_list_is_noop(monkeypatch):
    """No packages -> do not invoke tlmgr at all."""
    called = {"ran": False}
    monkeypatch.setattr(tex, "require_tool", lambda name: "/abs/bin/tlmgr")

    def runner(*a, **k):
        called["ran"] = True
        class _CP:
            returncode = 0
        return _CP()

    monkeypatch.setattr(tex.subprocess, "run", runner)
    tex.tlmgr_install([])
    assert called["ran"] is False


def test_install_tinytex_pipes_installer_to_shell(monkeypatch):
    captured = {}

    def runner(cmd, *a, **k):
        captured["cmd"] = cmd
        captured["shell"] = k.get("shell")
        captured["check"] = k.get("check")
        class _CP:
            returncode = 0
        return _CP()

    monkeypatch.setattr(tex.subprocess, "run", runner)
    tex.install_tinytex()
    cmd = captured["cmd"]
    assert "https://yihui.org/tinytex/install-bin-unix.sh" in cmd
    assert "curl" in cmd and "| sh" in cmd
    assert captured["shell"] is True
    assert captured["check"] is True


# ---- platform-aware fallback dirs -------------------------------------------

def test_locate_tool_windows_tinytex_fallback(tmp_path, monkeypatch):
    """Windows TinyTeX lives at %APPDATA%/TinyTeX/bin/windows/ and tools end
    in .exe; the mac-only fallback list finds nothing there."""
    monkeypatch.setattr(tex.sys, "platform", "win32")
    bindir = tmp_path / "TinyTeX" / "bin" / "windows"
    bindir.mkdir(parents=True)
    (bindir / "latexmk.exe").write_text("")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(tex.shutil, "which", lambda name: None)

    assert tex.locate_tool("latexmk") == str(bindir / "latexmk.exe")


def test_locate_tool_linux_tinytex_fallback(tmp_path, monkeypatch):
    """Linux TinyTeX installs to ~/.TinyTeX/bin/<arch>/."""
    monkeypatch.setattr(tex.sys, "platform", "linux")
    bindir = tmp_path / ".TinyTeX" / "bin" / "x86_64-linux"
    bindir.mkdir(parents=True)
    (bindir / "latexmk").write_text("")
    monkeypatch.setattr(tex.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(tex.shutil, "which", lambda name: None)

    assert tex.locate_tool("latexmk") == str(bindir / "latexmk")
