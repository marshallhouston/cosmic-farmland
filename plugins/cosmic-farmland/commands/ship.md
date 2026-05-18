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

2. **Poll PR state -- background bash + Monitor, NOT foreground.** Do NOT use `gh pr checks --watch` (blocks until every check is terminal; one slow Railway preview hangs the whole thing). Do NOT run the poll in foreground Bash either: foreground buffers stdout until exit, so a 4-min poll looks frozen and the user interrupts asking "is it hung?". Pattern: `run_in_background: true` for the poll loop (heartbeat every tick to a file) + `Monitor` on the same file with a `grep --line-buffered` alternation that fires only on terminal events. User sees nothing during quiet pending; gets a notification the instant state flips. Surface the bg-output-file path in your text reply so the user can `! tail -f` it themselves if they want live ticks. Incident 2026-05-07: foreground poll on PR #479 had user interrupt twice in 4 min; switching to background+Monitor fixed it.

   ```bash
   # Background poll. Schema handles BOTH GitHub Actions CheckRun
   # (.conclusion) and Railway/external StatusContext (.state). Earlier ship
   # had jq filter checking only .conclusion; missed Railway pending entirely
   # and false-fell-through to merge attempt while preview was still
   # building (PR #479 incident).
   PR=<pr>
   START=$SECONDS
   while [ $((SECONDS - START)) -lt 1200 ]; do
     SNAP=$(gh pr view "$PR" --json state,mergeStateStatus,statusCheckRollup --jq '{
       state, mss: .mergeStateStatus,
       checks: [.statusCheckRollup[]? | {n:(.name // .context), s:(.conclusion // .state)}]
     }')
     T=$((SECONDS - START))
     echo "$(date -u +%T) +${T}s $(jq -c . <<<"$SNAP")"
     STATE=$(jq -r .state <<<"$SNAP")
     case "$STATE" in MERGED) echo merged; break;; CLOSED) echo closed; exit 1;; esac
     FAILS=$(jq -r '[.checks[] | select(.s=="FAILURE" or .s=="ERROR")] | length' <<<"$SNAP")
     PEND=$(jq -r  '[.checks[] | select(.s=="PENDING" or .s=="IN_PROGRESS" or .s=="QUEUED")] | length' <<<"$SNAP")
     [ "$FAILS" -gt 0 ] && { echo "FAILURE"; break; }
     if [ "$STATE" = "OPEN" ] && [ "$PEND" = "0" ]; then
       PASSED=$(jq -r '[.checks[] | select(.s=="SUCCESS")] | length' <<<"$SNAP")
       if [ "$PASSED" -gt 0 ]; then echo "READY"; break
       elif [ $T -gt 60 ]; then    echo "READY_NO_CHECKS"; break
       fi
     fi
     sleep 20
   done
   ```

   Then arm Monitor on the bg-output file path returned by the Bash tool result:

   ```bash
   tail -n 0 -F <bg-output-file> | grep -E --line-buffered "READY|READY_NO_CHECKS|FAILURE|merged|closed"
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

6. **Clean up.** Two paths depending on how you entered the worktree:
   - **Session entered via `EnterWorktree(name:...)` (this-session create):** call `ExitWorktree(action: "remove")`. Tool deletes worktree dir + branch.
   - **Session entered via `EnterWorktree(path:...)` (pre-existing worktree):** ExitWorktree only operates on this-session creates, so `action: "remove"` is a no-op. Two-step dance is mandatory:
     1. `ExitWorktree(action: "keep")` -- returns session cwd to main repo.
     2. From main repo: `git worktree remove <path> 2>&1; git branch -D <branch> 2>&1`. Both will normally succeed (the merge already deleted the remote branch; local branch + worktree dir are now safe to drop).
   - **Not in a worktree:** just `git branch -D <branch>` from main repo.
   - Then: `git checkout main 2>&1 | tail -2; git pull --ff-only 2>&1 | tail -3`.
   - Note: `gh pr merge --delete-branch` is auto-stripped by the local pretool hook when CWD is inside a worktree (collision with worktree HEAD), so the local-branch cleanup above is mandatory, not optional. Remote branch is deleted by the merge regardless.

6a. **Verify production deploy (skip if repo has no `railway.json`).** A green PR check is not the same as a successful prod deploy. PR-preview and prod can pass different gates: preview-only test DB, env-conditional pre-deploy commands, missing prod secrets. Real incident 2026-05-01: PR #421 merged green, but prod deploys had been silently failing pre-deploy on every push since #419 (a guard in src/test/setup.ts rejected mainline DB; PR-preview used switchyard so the gap was invisible). Surfaced only when a user asked about an unrelated service. Do not let `/ship` return success while prod is stale.

   If `railway.json` exists at repo root and the `railway` CLI is available:

   **Pre-flight auth check.** Before polling, confirm the CLI can talk to the project. Define a shell function (not a variable) so word-splitting works the same in bash and zsh -- the Bash tool here uses zsh on macOS, where `$VAR command` does not split.

   ```bash
   # Portable timeout. Define `_to` as a function so the timeout
   # invocation isn't subject to shell word-splitting (a string
   # variable with embedded quotes -- e.g. `TO="perl -e '...'"` --
   # breaks because `$TO cmd` splits on whitespace but does not
   # re-process quotes). Function form survives both bash and zsh.
   #
   # Order: gtimeout (coreutils via brew) > GNU timeout > perl
   # (always on macOS) > fail loud. Never silently proceed without
   # a per-call cap -- a single hung `rw` call eats the entire
   # skill budget (17-min hang on PR #428; another on PR #449 where
   # coreutils was missing and there was no perl fallback wired up).
   if command -v gtimeout >/dev/null 2>&1; then
     _to() { gtimeout 30 "$@"; }
   elif command -v timeout >/dev/null 2>&1; then
     _to() { timeout 30 "$@"; }
   elif command -v perl >/dev/null 2>&1; then
     _to() { perl -e 'alarm 30; exec @ARGV' "$@"; }
   else
     echo "No timeout utility available (gtimeout, timeout, perl all missing)."
     echo "Install coreutils: brew install coreutils"
     echo "Skipping prod-deploy verification. Check Railway dashboard manually."
     exit 2
   fi

   # dotenvx loads RAILWAY_TOKEN from encrypted .env automatically when
   # the repo uses dotenvx. Project tokens reject `railway whoami`
   # (account-scoped); use a project-scoped command like `status` to
   # verify auth -- and judge auth from stdout (`railway status` exits
   # non-zero on some project-token configs even when it prints valid
   # `Project: ... Environment: ... Service: ...` info).
   if [ -f .env.keys ] && grep -q '^RAILWAY_TOKEN' .env 2>/dev/null; then
     rw() { _to dotenvx run --quiet -- railway "$@"; }
   else
     rw() { _to railway "$@"; }
   fi

   if ! rw status 2>&1 | grep -q '^Project:'; then
     echo "Railway CLI not authenticated. Either:"
     echo "  - run: ! railway login        (interactive, expires)"
     echo "  - or:  dotenvx set RAILWAY_TOKEN <project-token>  (long-lived)"
     echo "Skipping prod-deploy verification. Check Railway dashboard manually."
     exit 2
   fi
   ```

   **Hard per-call timeout.** Every `rw` invocation is wrapped via `_to`, a shell function that picks the first available of `gtimeout 30`, `timeout 30`, or `perl -e 'alarm 30; exec @ARGV'`. If none of the three are present the skill exits 2 before polling rather than entering an unbounded loop. Function form (vs. a `TO=` string variable) is required because `$TO cmd` would split on whitespace but not re-process embedded quotes, so a perl fallback string would corrupt under expansion. Auth detection uses stdout grep (`^Project:`) rather than exit code because `railway status` returns non-zero on some project-token configs even when the project is correctly resolved (incident 2026-05-04: every preach-hub /ship false-negatived on auth and silently skipped prod-verify). Incidents driving each layer: 17-min hang PR #428 (no per-call cap at all); PR #449 (coreutils missing, no perl fallback, hang on `rw deployment list`).

   **Diff-gate skip.** Prod-verify exists to catch failures in build, pre-deploy, or boot. If the merged diff touches none of those surfaces, the prod deploy is a no-op clone of the previous one and verifying it just blocks the session. Before polling, check the merged diff:
   ```bash
   gh pr diff <pr> --name-only | grep -E '^(src/server/|src/db/|drizzle/|migrations/|scripts/(deploy|migrate|pre-deploy)|railway\.json|nixpacks\.toml|Dockerfile|package\.json|bun\.lock|\.env(\.|$))' && NEEDS_VERIFY=1 || NEEDS_VERIFY=0
   ```
   If `NEEDS_VERIFY=0` (pure docs/UI/copy/test changes), skip the poll entirely and note "prod-verify skipped (diff touches no deploy-affecting paths)" in the final report. The next deploy-affecting ship will catch any drift.

   **Poll for terminal state (run in background; cap 10 min total, 30 ticks of 10s).** Launch this as a single `run_in_background: true` Bash invocation so the foreground session continues immediately. The notification surfaces when the loop exits; report deploy status as a follow-up message rather than holding step 7 hostage to it.
   ```bash
   START=$SECONDS
   while [ $((SECONDS - START)) -lt 600 ]; do
     s=$(rw deployment list --service <service> 2>/dev/null | sed -n '2p' | grep -oE 'SUCCESS|FAILED|CRASHED|REMOVED|BUILDING|DEPLOYING|QUEUED|INITIALIZING')
     case "$s" in
       SUCCESS|FAILED|CRASHED|REMOVED) echo "deploy=$s after $((SECONDS - START))s"; break ;;
       "") echo "rw deployment list timed out or returned empty. Skipping prod-verify."; break ;;
     esac
     sleep 10
   done
   ```
   - Service name from `rw status --json` (service whose source repo matches the current GitHub repo). For preach-hub it is `preach-hub`. Hardcoding is fine when the skill is invoked in a known repo.
   - Cap wait at 10 min (60 ticks of 10s). If still BUILDING/DEPLOYING after that, report the status and stop. Do not claim success.
   - 10s tick (was 20s): cuts the worst-case overshoot from 20s to 10s when status flips mid-tick. Healthy deploy is still ~3-5min total, so the tick rate is dwarfed by build time -- but keeps the poll responsive when SUCCESS lands.
   - On non-SUCCESS terminal: pull the deploy logs (`rw logs <id> --service <s> --deployment --lines 200`), diagnose the failure inline (same discipline as step 3a, never punt with "investigate?"), and report. Common causes: pre-deploy command failing, migration failing, runtime crash on boot, missing env var.
   - On SUCCESS: health-check the prod domain (`curl -s <prod-domain>/api/health`) and include the response in the report.
   - If `railway` CLI is not on PATH, surface that fact (do not silently skip). Tell the user the deploy could not be verified locally and they should check the Railway dashboard.
   - If the repo has no `railway.json` and no other known deploy target, skip silently.

   Rationale: the gate that actually serves users is the deploy gate. If `/ship` does not verify it, a broken prod-only path looks identical to a clean ship until the next surface area happens to expose it. With this step, every `/ship` either confirms prod is live on the merged commit or surfaces the failure with logs at the moment it happens.

7. **Report.** One or two sentences: PR number, merged URL, cleanup status. If prod-verify ran in background, note that deploy status will follow as a separate message when the poll exits. If prod-verify was skipped via the diff-gate, note that. Otherwise (synchronous verify, e.g. user explicitly asked to wait): include deploy id + SUCCESS/FAILED + commit live in prod. Nothing more.

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
