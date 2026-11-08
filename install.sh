#!/bin/sh
# Installs the `dsa` command into its own venv (like pipx) and wires it into Zed.
set -e
cd "$(dirname "$0")"
if command -v pipx >/dev/null; then
  pipx install --force .
else
  VENV="${XDG_DATA_HOME:-$HOME/.local/share}/zed-dsa/venv"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --upgrade .
  mkdir -p "$HOME/.local/bin"
  ln -sf "$VENV/bin/dsa" "$HOME/.local/bin/dsa"
fi
"$HOME/.local/bin/dsa" setup-zed
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "Add ~/.local/bin to your PATH so Zed tasks can find dsa." ;; esac
