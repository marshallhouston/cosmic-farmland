#!/usr/bin/env bash
# deps-audit.sh -- bucket `bun outdated` into SAFE BATCH / MAJORS / EXACT-PINNED / PEER-HELD.
# Buckets:
#   SAFE BATCH   patch/minor where update == latest        -> one PR
#   MAJORS       latest major > current major              -> one PR per dep
#   EXACT-PINNED update < latest only because package.json pins exact (no ^/~) -> own PR
#   PEER-HELD    update < latest under a caret/range spec   -> follow-up after core dep
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

major() { echo "${1%%.*}"; }
# spec for a dep name from package.json deps + devDeps (empty if absent)
spec() { node -e '
  const p=require("./package.json"),n=process.argv[1];
  const v=(p.dependencies&&p.dependencies[n])||(p.devDependencies&&p.devDependencies[n])||"";
  process.stdout.write(v);
' "$1" 2>/dev/null || true; }

safe=(); majors=(); exact=(); peer=()

# bun outdated table: | name | current | update | latest |
while IFS='|' read -r _ name current update latest _; do
  name="$(echo "$name" | xargs)"; current="$(echo "$current" | xargs)"
  update="$(echo "$update" | xargs)"; latest="$(echo "$latest" | xargs)"
  [[ "$name" == "Package" || -z "$name" || "$name" == -* ]] && continue
  name="${name% (dev)}"
  row="$name $current -> $latest"
  if [[ "$(major "$latest")" -gt "$(major "$current")" ]]; then
    majors+=("$row")
  elif [[ "$update" == "$latest" ]]; then
    safe+=("$name")
  else
    # update < latest: pinned-exact vs peer-held
    s="$(spec "$name")"
    if [[ -n "$s" && "$s" != \^* && "$s" != \~* && "$s" != *"x"* && "$s" != *"*"* ]]; then
      exact+=("$name (pin $s -> $latest)")
    else
      peer+=("$name (spec ${s:-?}, update $update < latest $latest)")
    fi
  fi
done < <(bun outdated 2>/dev/null | grep '|')

section() { local title="$1"; shift; echo "== $title =="; if [[ $# -eq 0 ]]; then echo "  (none)"; else printf '  %s\n' "$@"; fi; echo; }

section "SAFE BATCH (one PR: bun update <all>)" "${safe[@]+"${safe[@]}"}"
section "MAJORS (one PR per dep, grep usage first)" "${majors[@]+"${majors[@]}"}"
section "EXACT-PINNED (edit pin, verify peers, own PR)" "${exact[@]+"${exact[@]}"}"
section "PEER-HELD (follow-up after core dep lands)" "${peer[@]+"${peer[@]}"}"
