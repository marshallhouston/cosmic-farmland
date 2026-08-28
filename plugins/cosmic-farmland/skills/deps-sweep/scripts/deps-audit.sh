#!/usr/bin/env bash
# Bucket `bun outdated` into held / majors / exact-pinned / peer-held / safe-batch.
#
# Safe-batch   = patch/minor on runtime + dev where Update == Latest.
# Majors       = Latest major > Current major.
# Exact-pinned = Update < Latest but package.json pins an exact version (no range char).
#                Not blocked -- edit the pin to bump. Verify peers before shipping.
# Peer-held    = Update < Latest under a caret/range spec (bun couldn't pick latest,
#                usually a real peer mismatch).
# Held         = deliberately parked in the repo's .deps-held: a bump that is really
#                a migration. Checked BEFORE every other bucket so a breaking
#                semver-minor can't land in SAFE BATCH, the one bucket that says
#                "bump without thinking". (why: preach-hub's better-auth 1.7 is a
#                minor with a required-column data migration, and it showed up as
#                safe on three consecutive sweeps.)
#
# Repo-agnostic. Everything repo-specific lives in .deps-held at the repo root:
#
#   # comments and blank lines ignored
#   <dep name> | <why it is parked, and what unparks it> | <optional probe command>
#
# The probe command runs on every audit and its output is printed under the entry.
# A HELD row with no watcher is just a slower "never", so use the probe to check
# the signal that actually unparks the dep. Probes must stay silent when the gate
# is still shut, or they become noise everyone learns to skip.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

HELD_FILE="${DEPS_HELD_FILE:-.deps-held}"

major() { cut -d. -f1 <<<"$1" | sed 's/[^0-9]//g'; }

# Spec string for a dep from package.json (deps + devDeps). Empty if absent.
spec() {
  node -e 'const p=require("./package.json");const n=process.argv[1];
    const v=(p.dependencies&&p.dependencies[n])||(p.devDependencies&&p.devDependencies[n])||"";
    process.stdout.write(v);' "$1" 2>/dev/null || true
}

# Exact pin = full X.Y.Z (optionally with prerelease/build), no range char.
# A bare major ("10") or major.minor ("10.2") is a RANGE, not a pin -- leave
# those to the major/range logic so an out-of-range major lands in MAJORS.
is_exact() { [[ "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+([-+].*)?$ ]]; }

# Field <n> of the .deps-held row for a dep, or empty. Reads a file, so the
# bucketing logic below takes the reason as an argument to stay testable.
#
# Field 3 is everything after the second `|`, rejoined. Probes are shell, and
# shell is full of pipes -- splitting on every `|` truncated the probe at its
# first one and left the tail printing as a bogus unblock signal.
held_field() {
  local name="${1% (dev)}" field="$2"
  [ -f "$HELD_FILE" ] || return 0
  awk -F'|' -v want="$name" -v f="$field" '
    /^[[:space:]]*#/ || /^[[:space:]]*$/ { next }
    { gsub(/^[[:space:]]+|[[:space:]]+$/, "", $1)
      if ($1 != want) next
      if (f >= 3) { v = ""; for (i = 3; i <= NF; i++) v = v (i > 3 ? "|" : "") $i }
      else        { v = $f }
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", v); print v; exit }
  ' "$HELD_FILE"
}
held_reason() { held_field "$1" 2; }
held_probe()  { held_field "$1" 3; }

# Which bucket a row belongs in. Echoes: parked | majors | pinned | held | safe.
#
# The major test MUST come first among the semver tests. A caret/tilde range can
# never resolve across a major, so every major has update != latest by definition
# -- testing that first swallowed the entire MAJORS bucket into pinned/held and
# made it unreachable. (why: preach-hub's 2026-07-28 sweep reported "MAJORS (0)"
# while four majors sat in PEER-HELD.)
bucket_for() {
  local current="$1" update="$2" latest="$3" s="$4" reason="${5:-}"
  local cm lm
  if [ -n "$reason" ]; then echo parked; return; fi
  cm=$(major "$current"); lm=$(major "$latest")
  if [ -n "$cm" ] && [ -n "$lm" ] && [ "$lm" -gt "$cm" ]; then
    echo majors
  elif [ "$update" != "$latest" ]; then
    if is_exact "$s"; then echo pinned; else echo held; fi
  else
    echo safe
  fi
}

self_test() {
  local fails=0
  check() { # expected current update latest spec label [held-reason]
    local got; got=$(bucket_for "$2" "$3" "$4" "$5" "${7:-}")
    if [ "$got" != "$1" ]; then
      echo "FAIL: $6 -- expected $1, got $got"; fails=$((fails + 1))
    fi
  }
  # The regression: caret-ranged major. update is capped inside the major, so the
  # old code filed this as held. It is a major.
  check majors 5.3.0 5.3.0 6.0.1 '^5.3.0'   'caret-ranged major'
  # Exact-pinned major is still a major, not a pin-edit.
  check majors 6.0.3 6.0.3 7.0.2 '6.0.3'    'exact-pinned major'
  # Within-major, pin holds it back -> edit the pin.
  check pinned 2.14.0 2.14.0 2.19.0 '2.14.0' 'exact-pinned minor'
  # Within-major, range holds it back -> genuine peer block.
  check held   1.2.0 1.2.0 1.9.0 '^1.2.0'   'peer-held minor'
  # Nothing in the way.
  check safe   1.2.0 1.9.0 1.9.0 '^1.2.0'   'safe minor'
  check safe   1.2.0 1.2.1 1.2.1 '^1.2.0'   'safe patch'
  # A parked dep must never reach SAFE BATCH, even when it looks like a clean minor.
  check parked 1.6.25 1.7.2 1.7.2 '^1.6.25' 'parked breaking minor' 'some reason'
  # A parked dep outranks even a major, so the reason is read before the bump.
  check parked 6.0.3 6.0.3 7.0.2 '^6.0.3'   'parked major' 'some reason'

  # .deps-held parsing, against a temp file so the test does not depend on the repo.
  local tmp; tmp=$(mktemp)
  printf '# comment\n\nleft-pad | because reasons | echo probed\nbare-dep | no probe here\npiped-dep | reason | npm info x | grep -q 7 && echo fired\n' >"$tmp"
  local saved="$HELD_FILE"; HELD_FILE="$tmp"
  field() { # expected actual label
    if [ "$1" != "$2" ]; then echo "FAIL: $3 -- expected '$1', got '$2'"; fails=$((fails + 1)); fi
  }
  field "because reasons" "$(held_reason left-pad)"        'reason parsed'
  field "echo probed"     "$(held_probe left-pad)"         'probe parsed'
  field "no probe here"   "$(held_reason bare-dep)"        'reason without probe'
  field ""                "$(held_probe bare-dep)"         'missing probe is empty'
  field ""                "$(held_reason not-listed)"      'unlisted dep is empty'
  field "because reasons" "$(held_reason 'left-pad (dev)')" 'dev suffix stripped'
  field ""                "$(held_reason '#')"             'comment line ignored'
  # The bug a live run caught: a probe containing pipes was truncated at the
  # first one, and the tail printed as a bogus unblock signal.
  field "npm info x | grep -q 7 && echo fired" "$(held_probe piped-dep)" 'probe keeps its pipes'
  field "reason"          "$(held_reason piped-dep)"       'reason unaffected by probe pipes'
  HELD_FILE="$saved"; rm -f "$tmp"

  if [ "$fails" -gt 0 ]; then echo "$fails self-test failure(s)"; return 1; fi
  echo "deps-audit self-test: 17 passed"
}

if [ "${1:-}" = "--self-test" ]; then self_test; exit $?; fi

raw=$(bun outdated 2>/dev/null || true)
if ! grep -q '|' <<<"$raw"; then
  echo "All dependencies current."
  exit 0
fi

# Parse rows: | name | current | update | latest |
rows=$(awk -F'|' '
  /^\| [A-Za-z@]/ && $2 !~ /Package/ {
    gsub(/^ +| +$/, "", $2); gsub(/^ +| +$/, "", $3);
    gsub(/^ +| +$/, "", $4); gsub(/^ +| +$/, "", $5);
    print $2 "\t" $3 "\t" $4 "\t" $5;
  }
' <<<"$raw")

safe=()
parked=()
parked_names=()
majors=()
pinned=()
held=()

while IFS=$'\t' read -r name current update latest; do
  [ -z "$name" ] && continue
  s=$(spec "$name")
  reason=$(held_reason "$name")
  case "$(bucket_for "$current" "$update" "$latest" "$s" "$reason")" in
    parked) parked+=("$name $current -> $latest -- $reason"); parked_names+=("$name") ;;
    majors) majors+=("$name $current -> $latest") ;;
    pinned) pinned+=("$name $current -> $latest (exact-pinned '$s'; edit pin to bump, verify peers)") ;;
    held)   held+=("$name $current -> update=$update latest=$latest (peer-held, spec '$s')") ;;
    safe)   safe+=("$name $current -> $latest") ;;
  esac
done <<<"$rows"

printf "\n=== SAFE BATCH (%d) ===\n" "${#safe[@]}"
[ ${#safe[@]} -gt 0 ] && printf '  %s\n' "${safe[@]}" || echo "  (none)"

printf "\n=== HELD (%d, do NOT bump, see note) ===\n" "${#parked[@]}"
[ ${#parked[@]} -gt 0 ] && printf '  %s\n' "${parked[@]}" || echo "  (none)"

# Run each parked dep's watcher. Probe failures are non-fatal: a probe that cannot
# answer (no network, missing tool) stays quiet rather than breaking the audit.
for _name in ${parked_names[@]+"${parked_names[@]}"}; do
  _probe=$(held_probe "$_name")
  [ -z "$_probe" ] && continue
  _out=$(bash -c "$_probe" 2>/dev/null || true)
  [ -n "$_out" ] && printf '  ** %s unblock signal:\n%s\n' "$_name" "$(sed 's/^/     /' <<<"$_out")"
done

printf "\n=== MAJORS (%d, separate PR each) ===\n" "${#majors[@]}"
[ ${#majors[@]} -gt 0 ] && printf '  %s\n' "${majors[@]}" || echo "  (none)"

printf "\n=== EXACT-PINNED (%d, edit pin to bump) ===\n" "${#pinned[@]}"
[ ${#pinned[@]} -gt 0 ] && printf '  %s\n' "${pinned[@]}" || echo "  (none)"

printf "\n=== PEER-HELD (%d, bump alongside core) ===\n" "${#held[@]}"
[ ${#held[@]} -gt 0 ] && printf '  %s\n' "${held[@]}" || echo "  (none)"

total=$(( ${#safe[@]} + ${#parked[@]} + ${#majors[@]} + ${#pinned[@]} + ${#held[@]} ))
printf "\nTotal: %d outdated.\n" "$total"
