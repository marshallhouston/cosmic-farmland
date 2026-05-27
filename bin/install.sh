#!/usr/bin/env bash
set -euo pipefail

# install.sh: symlink every bin/ script into ~/bin so they're on PATH and
# always track source (no stale copies). Idempotent + non-clobbering.
#
# Usage: bash bin/install.sh

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
info() { echo -e "${BLUE}▸${NC} $1"; }

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$HOME/bin"
mkdir -p "$DEST"

for src in "$BIN_DIR"/*; do
  name="$(basename "$src")"
  [ "$name" = "install.sh" ] && continue           # don't symlink the installer
  [ -f "$src" ] && [ -x "$src" ] || continue        # executable files only
  tgt="$DEST/$name"
  if [ -L "$tgt" ]; then
    cur="$(readlink "$tgt")"
    if [ "$cur" = "$src" ]; then
      ok "$name (already linked)"
    else
      warn "$name: ~/bin link points elsewhere ($cur) — left alone"
    fi
  elif [ -e "$tgt" ]; then
    warn "$name: replacing stale copy in ~/bin with symlink to source"
    ln -sf "$src" "$tgt"; ok "$name (relinked)"
  else
    ln -s "$src" "$tgt"; ok "$name (linked)"
  fi
done

case ":$PATH:" in
  *":$DEST:"*) : ;;
  *) warn "$DEST is not on PATH — add to your shell rc: export PATH=\"\$HOME/bin:\$PATH\"" ;;
esac
