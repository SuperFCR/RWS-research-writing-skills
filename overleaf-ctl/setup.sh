#!/usr/bin/env bash
# overleaf-ctl setup: venv (>=3.10) + mirror-safe editable install + symlink + idempotent TinyTeX.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SKILL_DIR/.venv"
BIN_LINK="$HOME/.local/bin/overleaf-ctl"
GOOD_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"   # NOT the broken .../web/simple
TINYTEX_INSTALLER="https://yihui.org/tinytex/install-bin-unix.sh"

echo "==> overleaf-ctl setup (skill dir: $SKILL_DIR)"

# 1. Pick a >=3.10 interpreter (NEVER /usr/bin/python3 = 3.9.6).
PYBIN=""
for cand in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$cand" >/dev/null 2>&1 && \
     "$cand" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,10) else 1)'; then
    PYBIN="$(command -v "$cand")"; break
  fi
done
[ -n "$PYBIN" ] || { echo "ERROR: no python >=3.10 found on PATH"; exit 1; }
echo "==> Using interpreter: $("$PYBIN" --version) ($PYBIN)"

# 2. Create venv (idempotent).
if [ ! -x "$VENV_DIR/bin/python" ]; then
  "$PYBIN" -m venv "$VENV_DIR"
else
  echo "==> Reusing venv at $VENV_DIR"
fi

# 3. Editable install through the CORRECT mirror, ignoring the broken pip config/env.
#    PIP_CONFIG_FILE=/dev/null  -> ignore ~/.pip/pip.conf (.../web/simple)
#    HOMEBREW_PIP_INDEX_URL=    -> ignore the broken env mirror
#    --no-build-isolation       -> build with the setuptools/wheel we just installed
export PIP_CONFIG_FILE=/dev/null
export PIP_INDEX_URL="$GOOD_INDEX"
export HOMEBREW_PIP_INDEX_URL=
"$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV_DIR/bin/python" -m pip install --no-build-isolation -e "$SKILL_DIR[dev]"

# 4. Symlink the global command (idempotent; relink if it points elsewhere).
mkdir -p "$(dirname "$BIN_LINK")"
[ -e "$BIN_LINK" ] || [ -L "$BIN_LINK" ] && rm -f "$BIN_LINK" || true
ln -s "$VENV_DIR/bin/overleaf-ctl" "$BIN_LINK"
echo "==> Linked $BIN_LINK -> $VENV_DIR/bin/overleaf-ctl"

# 5. Idempotent TinyTeX install: skip if a TeX toolchain is already resolvable.
have_tex() {
  command -v latexmk >/dev/null 2>&1 && return 0
  command -v tlmgr   >/dev/null 2>&1 && return 0
  ls "$HOME"/Library/TinyTeX/bin/*/tlmgr >/dev/null 2>&1 && return 0
  [ -x "/Library/TeX/texbin/tlmgr" ] && return 0
  return 1
}
if have_tex; then
  echo "==> TeX toolchain already present; skipping TinyTeX install"
else
  echo "==> Installing TinyTeX from $TINYTEX_INSTALLER"
  curl -sL "$TINYTEX_INSTALLER" | sh
  TLMGR="$(ls "$HOME"/Library/TinyTeX/bin/*/tlmgr 2>/dev/null | head -n1 || true)"
  if [ -n "$TLMGR" ]; then
    echo "==> Ensuring latexmk + base packages"
    "$TLMGR" install latexmk latex-bin xetex || true
  fi
fi

# 6. Smoke check + next steps.
echo "==> Verifying: overleaf-ctl --version"
"$BIN_LINK" --version
cat <<'EOF'

==> Done. Next steps:
    overleaf-ctl login                       # store your Overleaf git token in Keychain
    overleaf-ctl clone <git-url> <alias>     # clone a project + register it
    overleaf-ctl sync  <alias>               # auto-commit -> pull --rebase -> push
    overleaf-ctl compile <alias> --open      # local latexmk build, open the PDF
EOF
