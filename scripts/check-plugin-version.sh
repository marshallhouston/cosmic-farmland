#!/usr/bin/env bash
# Fail if any plugin's source files changed in this diff without a corresponding
# version bump in that plugin's plugin.json. Plugins ship to users via the
# marketplace cache; without a version bump, /reload-plugins is the only way
# users notice a change, and there's no way to tell what changed when.
#
# Compares HEAD against $BASE_REF (default: origin/main).

set -euo pipefail

BASE_REF="${BASE_REF:-origin/main}"
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# Make sure we have the base ref locally for diff.
git fetch --quiet origin "${BASE_REF#origin/}" 2>/dev/null || true

CHANGED=$(git diff --name-only "$BASE_REF"...HEAD -- 'plugins/*' 2>/dev/null || true)
[ -z "$CHANGED" ] && { echo "No plugin files changed."; exit 0; }

# Group changed files by plugin (plugins/<name>/...).
PLUGINS=$(echo "$CHANGED" | awk -F/ '{print $2}' | sort -u)

FAIL=0
for PLUGIN in $PLUGINS; do
  MANIFEST="plugins/${PLUGIN}/plugin.json"
  if [ ! -f "$MANIFEST" ]; then
    echo "  skip: plugins/${PLUGIN} (no plugin.json)"
    continue
  fi

  # Source files changed in this plugin (anything except the manifest itself).
  SOURCE_CHANGED=$(echo "$CHANGED" | grep "^plugins/${PLUGIN}/" | grep -v "^${MANIFEST}$" || true)
  [ -z "$SOURCE_CHANGED" ] && continue

  OLD_VERSION=$(git show "${BASE_REF}:${MANIFEST}" 2>/dev/null | jq -r .version 2>/dev/null || echo "")
  NEW_VERSION=$(jq -r .version "$MANIFEST")

  if [ -z "$OLD_VERSION" ] || [ "$OLD_VERSION" = "null" ]; then
    echo "  skip: plugins/${PLUGIN} (new plugin, no base version)"
    continue
  fi

  if [ "$OLD_VERSION" = "$NEW_VERSION" ]; then
    echo "FAIL: plugins/${PLUGIN} source changed but version still ${NEW_VERSION}"
    echo "      Bump plugins/${PLUGIN}/plugin.json version (current: ${NEW_VERSION})"
    echo "      Changed files:"
    echo "$SOURCE_CHANGED" | sed 's/^/        /'
    FAIL=1
  else
    echo "OK:   plugins/${PLUGIN} ${OLD_VERSION} -> ${NEW_VERSION}"
  fi
done

exit $FAIL
