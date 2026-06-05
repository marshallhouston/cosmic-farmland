#!/usr/bin/env bash
# ship-verify-deploy.sh -- verify a Railway prod deploy after a PR merge.
#
# Usage: ship-verify-deploy.sh <pr-number> <service-name> [health-url]
# No-op (exit 0) if the repo has no railway.json. Run in BACKGROUND; report the
# final deploy line as a follow-up message.
#
# Why this exists: a green PR check != a successful prod deploy. PR-preview and
# prod pass different gates (preview-only test DB, env-conditional pre-deploy,
# missing prod secrets). A merged-green PR has silently shipped broken prod
# before -- so verify by DEFAULT, skip only when the diff is provably inert.
#
# Exit codes: 0 = verified/skipped cleanly; 2 = could not verify (no timeout
# util, or CLI unauthenticated) -- caller surfaces "check dashboard manually".
set -uo pipefail

PR="${1:?usage: ship-verify-deploy.sh <pr> <service> [health-url]}"
SERVICE="${2:?service name required}"
HEALTH_URL="${3:-}"
# Prod env name. Defaults to "production" (Railway's default). Without an
# explicit env, `deployment list` uses the *linked* env -- which after a
# /ship run may be a preview env, silently probing the wrong deploys.
ENVIRONMENT="${4:-production}"

[ -f railway.json ] || { echo "no railway.json -- skipping prod-verify"; exit 0; }

# Portable per-call timeout as a FUNCTION (not a string var): `$VAR cmd` splits
# on whitespace but does not re-process quotes, so a perl fallback string would
# corrupt under expansion. Order: gtimeout > timeout > perl > fail loud. Never
# run an uncapped `rw` -- one hung call eats the whole budget.
if   command -v gtimeout >/dev/null 2>&1; then _to() { gtimeout 30 "$@"; }
elif command -v timeout  >/dev/null 2>&1; then _to() { timeout 30 "$@"; }
elif command -v perl     >/dev/null 2>&1; then _to() { perl -e 'alarm 30; exec @ARGV' "$@"; }
else
  echo "No timeout utility (gtimeout/timeout/perl). brew install coreutils."
  echo "Skipping prod-deploy verification. Check Railway dashboard manually."
  exit 2
fi

# dotenvx auto-loads RAILWAY_TOKEN from encrypted .env when the repo uses it.
if [ -f .env.keys ] && grep -q '^RAILWAY_TOKEN' .env 2>/dev/null; then
  rw() { _to dotenvx run --quiet -- railway "$@"; }
else
  rw() { _to railway "$@"; }
fi

# Auth + capability check via the REAL command the poll uses (--json), NOT
# `railway status`. Two reasons status is the wrong proxy: (1) project tokens
# make it exit non-zero even when valid; (2) on projects with many environments
# the CLI decode-errors on status ("expected value at line 1 column 1") while
# `deployment list` still works -- preach-hub (21 PR-preview envs) hit this and
# false-skipped a live deploy. --json output is immune to ANSI color, column
# reorder, and box-drawing drift that a human-table grep would trip on; a real
# row carries a "status" field.
if ! rw deployment list --service "$SERVICE" --environment "$ENVIRONMENT" --json 2>&1 \
     | grep -qE '"status"[[:space:]]*:[[:space:]]*"[A-Z_]+"'; then
  echo "Railway CLI can't list deployments for '$SERVICE'/'$ENVIRONMENT' (unauthenticated, wrong service, or wrong env). Either:"
  echo "  - run: ! railway login        (interactive, expires)"
  echo "  - or:  dotenvx set RAILWAY_TOKEN <project-token>  (long-lived)"
  echo "Skipping prod-deploy verification. Check Railway dashboard manually."
  exit 2
fi

# Diff-gate (fail-safe: verify unless provably inert). Skip ONLY for pure
# docs/markdown/test/CI-metadata diffs. Do NOT maintain a per-repo allowlist of
# deploy-affecting paths -- it goes stale and false-skips (a UI diff that ships
# inside the Docker image once matched nothing). grep -qv succeeds if ANY file
# is outside the inert set.
if ! gh pr diff "$PR" --name-only | grep -qvE '\.mdx?$|^docs/|\.test\.|\.spec\.|^\.github/'; then
  echo "prod-verify skipped (diff is docs/test-only)"
  exit 0
fi

# Poll for terminal deploy state. Cap 10 min (60 ticks of 10s); 10s tick keeps
# SUCCESS responsive (build dominates wall-clock anyway).
START=$SECONDS
while [ $((SECONDS - START)) -lt 600 ]; do
  # --json lists newest deploy first; take the first "status" value. Robust to
  # table format / ANSI / row-order changes that the old `sed -n 2p` assumed.
  s=$(rw deployment list --service "$SERVICE" --environment "$ENVIRONMENT" --json 2>/dev/null \
       | grep -oE '"status"[[:space:]]*:[[:space:]]*"[A-Z_]+"' | head -1 \
       | grep -oE 'SUCCESS|FAILED|CRASHED|REMOVED|BUILDING|DEPLOYING|QUEUED|INITIALIZING')
  case "$s" in
    SUCCESS)
      echo "deploy=SUCCESS after $((SECONDS - START))s"
      [ -n "$HEALTH_URL" ] && { echo "health: $(curl -s "$HEALTH_URL" || echo 'curl failed')"; }
      exit 0 ;;
    FAILED|CRASHED|REMOVED)
      echo "deploy=$s after $((SECONDS - START))s -- pull logs: rw logs <id> --service $SERVICE --deployment --lines 200"
      exit 0 ;;
    "")
      echo "rw deployment list timed out or returned empty. Skipping prod-verify."
      exit 0 ;;
  esac
  sleep 10
done

echo "deploy still building after $((SECONDS - START))s -- not claiming success; check dashboard"
exit 0
