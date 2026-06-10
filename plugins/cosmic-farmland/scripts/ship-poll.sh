#!/usr/bin/env bash
# ship-poll.sh -- poll a PR until it reaches a terminal-for-ship state.
#
# Usage: ship-poll.sh <pr-number>
# Emits one heartbeat line per tick (timestamp + JSON snapshot), then a final
# verdict token on its own line: READY | READY_NO_CHECKS | FAILURE | STALL | merged | closed
#
# Run this in the BACKGROUND (run_in_background). It self-exits on a verdict, so
# the background task notifies the caller -- no separate Monitor needed (a
# perpetual tail -F|grep Monitor never self-exits and leaks onto the statusline).
# Foreground buffers stdout until exit, so a multi-minute poll looks frozen;
# background streams each tick to the output file for `! tail -f`.
#
# Snapshot schema handles BOTH GitHub Actions CheckRuns (.conclusion) and
# Railway/external StatusContexts (.state) -- a filter on .conclusion alone
# misses Railway "pending" and can false-fall-through to merge mid-build.
#
# Verdict semantics:
#   merged          -- auto-merge/admin already merged; caller skips to cleanup.
#   closed          -- PR closed unmerged; caller stops (exit 1).
#   FAILURE         -- a check failed while OPEN; caller investigates.
#   READY           -- OPEN, all checks green, >=1 passed; caller merges manually
#                      (auto-merge didn't fire: label late / disabled / missed).
#   READY_NO_CHECKS -- OPEN, no checks at all after a 60s grace; CI-less repo,
#                      caller merges manually.
#   STALL           -- OPEN with pending checks but no snapshot change for 5
#                      min; a check is hung or a gate sits outside the rollup
#                      (review required, branch protection). Caller investigates.
#
# Caps: 20 min hard total; a 5-min no-change stall bail is emitted as STALL.
set -euo pipefail

PR="${1:?usage: ship-poll.sh <pr-number>}"
START=$SECONDS
LAST_CHANGE=$SECONDS   # last tick at which the snapshot changed
PREV=""                # previous snapshot, to detect a hung / no-change state

while [ $((SECONDS - START)) -lt 1200 ]; do
  SNAP=$(gh pr view "$PR" --json state,mergeStateStatus,statusCheckRollup --jq '{
    state, mss: .mergeStateStatus,
    checks: [.statusCheckRollup[]? | {n:(.name // .context), s:(.conclusion // .state)}]
  }')
  T=$((SECONDS - START))
  echo "$(date -u +%T) +${T}s $(jq -c . <<<"$SNAP")"

  STATE=$(jq -r .state <<<"$SNAP")
  case "$STATE" in MERGED) echo merged; exit 0;; CLOSED) echo closed; exit 1;; esac

  FAILS=$(jq -r '[.checks[] | select(.s=="FAILURE" or .s=="ERROR")] | length' <<<"$SNAP")
  PEND=$(jq -r  '[.checks[] | select(.s=="PENDING" or .s=="IN_PROGRESS" or .s=="QUEUED")] | length' <<<"$SNAP")
  [ "$FAILS" -gt 0 ] && { echo "FAILURE"; exit 0; }

  if [ "$STATE" = "OPEN" ] && [ "$PEND" = "0" ]; then
    PASSED=$(jq -r '[.checks[] | select(.s=="SUCCESS")] | length' <<<"$SNAP")
    if   [ "$PASSED" -gt 0 ]; then echo "READY"; exit 0
    elif [ "$T" -gt 60 ];     then echo "READY_NO_CHECKS"; exit 0
    fi
  fi

  # No-change stall bail (moved in from the caller's Monitor): if the snapshot
  # has not changed for 5 min we are OPEN with pending checks that are not
  # moving -- a hung check or a gate outside the rollup. Emit STALL and exit so
  # the background task notifies the caller; no perpetual Monitor is needed.
  # (why: 2026-06-10 stale-monitor leak.)
  if [ "$SNAP" != "$PREV" ]; then LAST_CHANGE=$SECONDS; PREV="$SNAP"; fi
  if [ $((SECONDS - LAST_CHANGE)) -ge 300 ]; then
    echo "STALL after $((SECONDS - LAST_CHANGE))s with no state change -- still OPEN/pending"
    exit 0
  fi

  sleep 20
done

echo "TIMEOUT after $((SECONDS - START))s -- still OPEN with pending checks"
exit 0
