#!/usr/bin/env bash
# Compatibility entry point: install the CLI only. TeX is a separate optional dependency.
set -euo pipefail
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_PYTHON=""
for candidate in "$PACKAGE_ROOT/.venv/bin/python" "${PYTHON:-}" python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
  if [ -n "$candidate" ] && command -v "$candidate" >/dev/null 2>&1 && \
    "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,10) else 1)'; then
    INSTALL_PYTHON="$candidate"
    break
  fi
done
if [ -z "$INSTALL_PYTHON" ]; then
  echo "Python >= 3.10 is required. Set PYTHON to the desired executable." >&2
  exit 1
fi
exec "$INSTALL_PYTHON" "$PACKAGE_ROOT/scripts/install.py" "$@"
