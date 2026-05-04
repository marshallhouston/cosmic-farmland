---
description: Wait for a PR to go green, merge it, clean up the worktree + local branch
argument-hint: "[pr-number] [--ack-yellow|--ack-red] (defaults to current branch's PR)"
---

# /ship

End-to-end tail for a PR: wait for green, merge, clean up.

## Preconditions

- PR is already pushed and open on GitHub.
- You are in the worktree (or repo) where the branch lives.
- The diff has been reviewed/tested to the extent the task warrants.

If these aren't true, stop and tell the user.

## Flow

1. **Resolve PR number.** If `$ARGUMENTS` starts with a number, use it. Otherwise `gh pr view --json number -q .number`. If neither works, stop.

1a. **Freshness check (skip if no classifier in repo).** If the repo has a risk classifier that posts `<!-- risk-score: scored_sha=<sha> tier=<tier> -->` PR comments, compare PR head SHA to the SHA in the latest classifier comment:
   ```bash
   HEAD_SHA=$(gh pr view <pr> --json headRefOid --jq .headRefOid)
   SCORED_SHA=$(gh pr view <pr> --json comments --jq '.comments[].body' | grep -oE 'scored_sha=[a-f0-9]+' | tail -1 | cut -d= -f2)
   ```
   If `SCORED_SHA` missing or != `HEAD_SHA`, auto-invoke `/risk-score <pr>` to re-score against current HEAD, then continue. Label from a prior commit is not trusted. If the repo has no classifier (no `risk:*` labels exist on any PR), skip this whole substep.

1b. **Gate on risk tier (skip if no classifier in repo).** `gh pr view <pr> --json labels --jq '.labels[].name' | grep '^risk:' | grep -v '^risk:override-' | head -1`. Enforce:
   - `risk:green` — proceed silently.
   - `risk:blue` — proceed, note tier in final report.
   - `risk:yellow` — STOP. Print the yellow reason (pull from latest classifier comment) and require explicit ack. Tell user: "Re-invoke with `/ship <pr> --ack-yellow` to proceed." If `$ARGUMENTS` contains `--ack-yellow` (or `--ack-red`), proceed and log the ack + "yellow tier" in the final report.
   - `risk:red` — STOP. Print the red reason (pull from latest classifier comment) and require explicit ack. Tell user: "Re-invoke with `/ship <pr> --ack-red` to proceed." If `$ARGUMENTS` contains `--ack-red`, proceed and log the ack in the final report.
   - `risk:needs-scoring` or no risk label (in a repo that DOES have a classifier) — auto-invoke `/risk-score <pr>` inline (do not stop and ask). The classifier workflow normally labels on PR open/sync; a missing label means either the workflow hasn't finished, failed, or the PR predates the workflow. After `/risk-score` returns, re-read the label and resume this gate with the new tier. If still missing or `needs-scoring` after one attempt, STOP and tell user: "Risk scoring failed after auto-retry. Inspect classifier run manually."
   - Repo has no classifier at all: skip silently.
   - Rationale: the classifier is the system's best signal about blast radius. /ship ignoring it defeats the two-stage pipeline. But a missing label is almost always a timing/workflow gap, not a policy signal, so auto-score rather than punt the user a next-step they already know.

2. **Poll PR state until it merges or stalls.** Do NOT use `gh pr checks --watch`. That command blocks until **every** check has a terminal state, even when one slow gate (Railway preview, opt-in runtime checks, classifier waiting on LLM) hangs for 10–15 minutes after the merge would otherwise have fired. Poll the PR state directly and snapshot each tick so the user sees liveness:

   ```bash
   PR=<pr>
   START=$SECONDS
   STALL_START=$SECONDS
   LAST=""
   while [ $((SECONDS - START)) -lt 1200 ]; do
     SNAP=$(gh pr view "$PR" --json state,statusCheckRollup --jq '{
       state,
       failed:  [.statusCheckRollup[] | select(.conclusion == "FAILURE") | .name],
       pending: [.statusCheckRollup[] | select(.status == "IN_PROGRESS" or .status == "QUEUED") | .name],
       passed:  [.statusCheckRollup[] | select(.conclusion == "SUCCESS")] | length
     }')
     STATE=$(jq -r .state <<<"$SNAP")
     FAILED=$(jq -r '.failed | join(",")' <<<"$SNAP")
     PENDING=$(jq -r '.pending | join(",")' <<<"$SNAP")
     PASSED=$(jq -r '.passed' <<<"$SNAP")
     SUMMARY="state=$STATE passed=$PASSED pending=[$PENDING] failed=[$FAILED]"
     [ "$SUMMARY" != "$LAST" ] && { echo "$(date -u +%T) $SUMMARY"; LAST="$SUMMARY"; STALL_START=$SECONDS; }
     case "$STATE" in
       MERGED) echo "merged"; break ;;
       CLOSED) echo "closed without merge"; exit 1 ;;
     esac
     [ -n "$FAILED" ] && { echo "failed: $FAILED"; break; }
     # All-green-but-OPEN: auto-merge isn't going to fire. Break and let step 5 merge manually.
     if [ "$STATE" = "OPEN" ] && [ -z "$PENDING" ] && [ -z "$FAILED" ] && [ "$PASSED" -gt 0 ]; then
       echo "all green, OPEN with no auto-merge -- falling through to manual merge"
       break
     fi
     # No-checks-at-all: repos that killed GHA (preach-hub #419, etc.) have an empty
     # statusCheckRollup. Wait one extra tick to be sure no checks are coming, then
     # fall through. Prevents 5-min stall on every ship in CI-less repos.
     if [ "$STATE" = "OPEN" ] && [ -z "$PENDING" ] && [ -z "$FAILED" ] && [ "$PASSED" -eq 0 ] && [ $((SECONDS - START)) -gt 60 ]; then
       echo "no checks present after 60s grace -- repo has no CI rollup, falling through to manual merge"
       break
     fi
     # Stall detector: 5 min with no state change → bail with snapshot.
     if [ $((SECONDS - STALL_START)) -gt 300 ]; then
       echo "STALL: no check state changed in 5 min. Bailing with snapshot above."
       break
     fi
     sleep 30
   done
   ```
   - `state: MERGED` means an auto-merge job (or admin merge) fired. Done. Skip step 4 (merge already happened) and go to step 6.
   - `state: OPEN` with all checks green and no pending: auto-merge didn't fire (label applied late, classifier missed the PR, repo auto-merge disabled, etc.). Break out of the poll and continue to step 4 (verify mergeable) → step 5 (manual merge). Do NOT wait the full 5-min stall — we already know the answer.
   - Any check `FAILURE` while still `OPEN` triggers step 3a (investigate). Do not wait for other gates to also finish.
   - Hard cap total wait at 20 min. If still `OPEN` with only pending checks, report what's pending and stop.
   - Stall: 5 minutes with no state change → bail with the last snapshot. Either a check is genuinely hung (CI infra issue, external dep timeout) or the PR is gated on something not in the rollup (review required, branch protection waiting on a context).
   - Why poll-not-watch: `--watch` gives no output until done. On a hung check the user sees nothing for 10+ minutes and assumes the assistant froze. Tick output proves liveness and surfaces *which* check is slow.
   - Why fall-through-on-green: incident 2026-04-26 PR #319 sat OPEN for 5 min after going green because `auto-merge-green` workflow only fires on `classify` completion and the label was applied manually after. The poll waited for MERGED that wasn't coming. Falling through to manual merge as soon as all-green removes the dead-wait. Defensive against label-applied-late, classifier-missed, repo-level auto-merge-disabled, and any other reason auto-merge fails to fire.
   - Why fall-through-on-no-checks: incident 2026-05-03 PR #431 stalled the full 5min because preach-hub killed GHA (#419). statusCheckRollup is permanently empty; only Railway pre-deploy gates post-merge. The all-green branch requires `PASSED > 0`, so empty rollup never matched. 60s grace window confirms no checks are inbound (classifier comments are not check rollup entries), then falls through. Saves about 4 min on every ship in CI-less repos.

3. **Verify required checks all passed.** Parse the final snapshot. Every check should have `conclusion: SUCCESS`. If anything is `FAILURE`, go to step 3a. Otherwise continue.

3a. **Investigate every failure automatically — no asking.** A failing check is never ignored and never punted back to the user as "want me to look?". Do the diagnosis, then proceed.
   - Pull the failing job's log: `gh run view --job <job-id> --log-failed` (job id is the numeric segment at the end of the check URL). For workflow-level failures: `gh run view <run-id> --log-failed`.
   - Identify the **root cause** in one sentence: code issue, infra/billing issue, flake, config drift, secret missing, upstream outage, etc.
   - Check whether the failure is actually **blocking the merge**: run `gh pr view <pr> --json mergeable,mergeStateStatus`. If `mergeable: MERGEABLE` and the failure is on a non-required check (common on private repos without branch protection), the check is cosmetic — continue to step 4 and merge. Note the cosmetic failure in the final report.
   - If the failure is a genuine blocker:
     - **Code issue on this PR** → report root cause + file/line, recommend the fix, stop.
     - **Infra / billing / upstream** (e.g. API key exhausted, third-party 5xx, missing secret) → report root cause + which workflow file is affected, recommend remediation (top up, swap provider, disable workflow), stop.
     - **Flake** (transient, re-run likely passes) → re-run once with `gh run rerun <run-id> --failed`, then loop back to step 2. If it fails again, treat as non-flake.
   - Never stop with just a URL and "investigate?". The user invoked ship to ship; the diagnosis is part of the job.

4. **Verify mergeable.** `gh pr view <pr> --json state,mergeable,mergeStateStatus`. Require `state: OPEN`, `mergeable: MERGEABLE`, `mergeStateStatus: CLEAN`. If not, report and stop.

4a. **Log ack if used.** If proceeding past a yellow or red gate via `--ack-yellow`/`--ack-red`, post an audit comment before merging:
   ```bash
   gh pr comment <pr> --body "Shipped with \`--ack-<tier>\` override by @$(gh api user --jq .login) at $(date -u +%Y-%m-%dT%H:%M:%SZ). Classifier tier: <tier>."
   ```
   Green/blue/no-classifier: skip.

5. **Merge.** `gh pr merge <pr> --squash --delete-branch`.
   - `--delete-branch` may fail locally from a worktree with a cosmetic `'<base>' is already used by worktree` error — this is expected and the merge still succeeded on GitHub.
   - After merge, verify with `gh pr view <pr> --json state,mergedAt`. If `state: MERGED`, treat as success regardless of local stderr.

6. **Clean up.**
   - If running from a worktree: use `ExitWorktree` (or `cd` out, then `git worktree remove <path>`). If worktree has uncommitted changes beyond the merged work, stop and ask.
   - Delete local branch: `git branch -D <branch>` (ignore if already gone).
   - In the main checkout: `git pull --ff-only` on the default branch.

6a. **Verify production deploy (skip if repo has no `railway.json`).** A green PR check is not the same as a successful prod deploy. PR-preview and prod can pass different gates: preview-only test DB, env-conditional pre-deploy commands, missing prod secrets. Real incident 2026-05-01: PR #421 merged green, but prod deploys had been silently failing pre-deploy on every push since #419 (a guard in src/test/setup.ts rejected mainline DB; PR-preview used switchyard so the gap was invisible). Surfaced only when a user asked about an unrelated service. Do not let `/ship` return success while prod is stale.

   If `railway.json` exists at repo root and the `railway` CLI is available:

   **Pre-flight auth check.** Before polling, confirm the CLI can talk to the project. Define a shell function (not a variable) so word-splitting works the same in bash and zsh -- the Bash tool here uses zsh on macOS, where `$VAR command` does not split.

   ```bash
   # Portable timeout: macOS zsh has no `timeout`. Prefer `gtimeout`
   # (coreutils via brew), fall back to GNU `timeout`, fall back to no-op.
   # No-op is acceptable for the pre-flight only because we judge auth
   # from stdout, not exit code; the per-call timeout for deploy polling
   # is enforced by the outer 10-minute SECONDS cap.
   if command -v gtimeout >/dev/null 2>&1; then TO="gtimeout 30";
   elif command -v timeout  >/dev/null 2>&1; then TO="timeout 30";
   else TO=""; fi

   # dotenvx loads RAILWAY_TOKEN from encrypted .env automatically when
   # the repo uses dotenvx. Project tokens reject `railway whoami`
   # (account-scoped); use a project-scoped command like `status` to
   # verify auth -- and judge auth from stdout (`railway status` exits
   # non-zero on some project-token configs even when it prints valid
   # `Project: ... Environment: ... Service: ...` info).
   if [ -f .env.keys ] && grep -q '^RAILWAY_TOKEN' .env 2>/dev/null; then
     rw() { $TO dotenvx run --quiet -- railway "$@"; }
   else
     rw() { $TO railway "$@"; }
   fi

   if ! rw status 2>&1 | grep -q '^Project:'; then
     echo "Railway CLI not authenticated. Either:"
     echo "  - run: ! railway login        (interactive, expires)"
     echo "  - or:  dotenvx set RAILWAY_TOKEN <project-token>  (long-lived)"
     echo "Skipping prod-deploy verification. Check Railway dashboard manually."
     exit 2
   fi
   ```

   **Hard per-call timeout.** Every `rw` invocation is wrapped in `$TO` which expands to `gtimeout 30` / `timeout 30` / empty. Without it, a single hung CLI call (network, auth refresh, project resolution) can eat the entire skill budget -- 17-minute hang seen on PR #428. macOS users should `brew install coreutils` for `gtimeout`; without it the deploy-poll loop's outer 10-minute `SECONDS` cap is the only ceiling. Auth detection uses stdout grep (`^Project:`) rather than exit code because `railway status` returns non-zero on some project-token configs even when the project is correctly resolved (incident 2026-05-04: every preach-hub /ship false-negatived on auth and silently skipped prod-verify).

   **Poll for terminal state (cap 10 min total, 30 ticks of 20s):**
   ```bash
   START=$SECONDS
   while [ $((SECONDS - START)) -lt 600 ]; do
     s=$(rw deployment list --service <service> 2>/dev/null | awk 'NR==2{print $3}')
     case "$s" in
       SUCCESS|FAILED|CRASHED|REMOVED) break ;;
       "") echo "rw deployment list timed out or returned empty. Skipping prod-verify."; break ;;
     esac
     sleep 20
   done
   ```
   - Service name from `rw status --json` (service whose source repo matches the current GitHub repo). For preach-hub it is `preach-hub`. Hardcoding is fine when the skill is invoked in a known repo.
   - Cap wait at 10 min (30 ticks of 20s). If still BUILDING/DEPLOYING after that, report the status and stop. Do not claim success.
   - On non-SUCCESS terminal: pull the deploy logs (`rw logs <id> --service <s> --deployment --lines 200`), diagnose the failure inline (same discipline as step 3a, never punt with "investigate?"), and report. Common causes: pre-deploy command failing, migration failing, runtime crash on boot, missing env var.
   - On SUCCESS: health-check the prod domain (`curl -s <prod-domain>/api/health`) and include the response in the report.
   - If `railway` CLI is not on PATH, surface that fact (do not silently skip). Tell the user the deploy could not be verified locally and they should check the Railway dashboard.
   - If the repo has no `railway.json` and no other known deploy target, skip silently.

   Rationale: the gate that actually serves users is the deploy gate. If `/ship` does not verify it, a broken prod-only path looks identical to a clean ship until the next surface area happens to expose it. With this step, every `/ship` either confirms prod is live on the merged commit or surfaces the failure with logs at the moment it happens.

7. **Report.** One or two sentences: PR number, merged URL, cleanup status, **prod deploy status (deploy id + SUCCESS/FAILED + commit live in prod)**. Nothing more.

## Non-goals

- Do not re-run tests locally before merging. CI is the authority.
- Do not ask for confirmation at any step if all gates pass. Trust the checks.
- Do not merge with failing checks "just to unblock." If something failed, fix it or escalate.

## When things go wrong

- A check fails: follow step 3a automatically. Pull logs, diagnose root cause, check if merge is actually blocked, act accordingly. Never stop at "X failed, investigate?".
- Poll loop times out at 20 min with only pending checks: report what's pending and stop. Do not extend the timeout silently.
- Stall detector bails (5 min no state change): report which check is hung. The user can decide to re-invoke, kick the workflow, or override.
- Merge blocked by review required or conflicts: report state and stop.
- Worktree cleanup fails because of uncommitted files: stop, tell the user what's there.

## Principle

A failing check is a signal, not a dead-end. There is no world where the correct response is "a check failed, want me to look?" — if it failed, look. The user's reason for invoking `/ship` presupposes that failures get investigated, not ignored or deferred back. Equally: a *running* check is not a reason to silently freeze. Stream snapshots; the user wants liveness, not suspense.
