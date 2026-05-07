#!/usr/bin/env bash
# Wire repo-tracked hooks. Run once after clone.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
echo "core.hooksPath -> .githooks"
