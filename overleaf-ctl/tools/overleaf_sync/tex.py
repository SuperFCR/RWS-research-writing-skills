from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

TINYTEX_BIN_GLOB = "Library/TinyTeX/bin/*"      # joined under Path.home() (macOS)
MACTEX_BIN = Path("/Library/TeX/texbin")


class TexNotFoundError(RuntimeError):
    """Raised when a required TeX tool cannot be located."""


def _fallback_bin_dirs() -> list[Path]:
    """Per-platform TeX bin dirs to probe when the tool is not on PATH.

    TinyTeX installs to ~/Library/TinyTeX (macOS), %APPDATA%/TinyTeX (Windows,
    binaries under bin/windows), ~/.TinyTeX (Linux). MacTeX is macOS-only.
    """
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        return [Path(appdata) / "TinyTeX" / "bin" / "windows"] if appdata else []
    if sys.platform == "darwin":
        return sorted(Path.home().glob(TINYTEX_BIN_GLOB)) + [MACTEX_BIN]
    return sorted(Path.home().glob(".TinyTeX/bin/*"))


def locate_tool(name: str) -> str | None:
    """Return absolute path to `name`: PATH -> platform TeX dirs, else None."""
    found = shutil.which(name)
    if found:
        return found
    names = [name, name + ".exe"] if sys.platform == "win32" else [name]
    for bindir in _fallback_bin_dirs():
        for cand_name in names:
            cand = bindir / cand_name
            if cand.exists():
                return str(cand)
    return None


def require_tool(name: str) -> str:
    """Locate `name` or raise TexNotFoundError pointing at the optional TeX setup documentation."""
    path = locate_tool(name)
    if path is None:
        raise TexNotFoundError(
            f"找不到 TeX 工具 {name!r}。请按 README 的可选 TeX 依赖说明安装 LaTeX 工具链，"
            f"或确认 TinyTeX/MacTeX 已安装。"
        )
    return path


def tlmgr_search_file(filename: str) -> list[str]:
    """Run `tlmgr search --global --file "/<filename>"`; return package names.

    Package names are the flush-left lines ending in ':' in tlmgr output;
    indented lines are matched file paths. Deduped, order-preserving.
    """
    tlmgr = require_tool("tlmgr")
    query = filename if filename.startswith("/") else "/" + filename
    proc = subprocess.run(
        [tlmgr, "search", "--global", "--file", query],
        capture_output=True,
        text=True,
    )
    packages: list[str] = []
    for line in proc.stdout.splitlines():
        if not line or line[0] in (" ", "\t"):
            continue  # indented file path, skip
        if line.startswith("tlmgr:"):
            continue  # repository banner / diagnostics
        stripped = line.rstrip()
        if stripped.endswith(":"):
            pkg = stripped[:-1].strip()
            if pkg and pkg not in packages:
                packages.append(pkg)
    return packages


def tlmgr_install(packages: list[str]) -> None:
    """Install the given TeX Live packages via `tlmgr install`. No-op if empty."""
    if not packages:
        return
    tlmgr = require_tool("tlmgr")
    subprocess.run([tlmgr, "install", *packages], check=True)


TINYTEX_INSTALL_URL = "https://yihui.org/tinytex/install-bin-unix.sh"


def install_tinytex() -> None:
    """Legacy explicit TinyTeX helper; never called by the default installer."""
    subprocess.run(
        f'curl -sL "{TINYTEX_INSTALL_URL}" | sh',
        shell=True,
        check=True,
    )
