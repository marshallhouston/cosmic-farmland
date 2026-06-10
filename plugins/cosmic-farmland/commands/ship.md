---
description: Wait for a PR to go green, merge it, clean up the worktree + local branch
argument-hint: "[pr-number] [--ack-yellow|--ack-red] (defaults to current branch's PR)"
---

# /ship

End-to-end tail for a PR: wait for green, merge, clean up. Two helper scripts do
the heavy lifting; this file is the spec. Incident history that justifies each
guard lives in `scripts/ship.CHANGELOG.md`, not inline.

## Preconditions

- PR is pushed and open on GitHub.
- You're in the worktree/repo where the branch lives.
- The diff is reviewed/tested to the extent the task warrants.

If not, stop and tell the user.

## Flow

1. **Resolve PR.** `$ARGUMENTS` starts with a number → use it. Else `gh pr view --json number -q .number`. Neither works → stop.

2. **Risk gate (skip entirely if the repo has no `risk:*` classifier).** Read the tier: `gh pr view <pr> --json labels --jq '.labels[].name' | grep '^risk:' | grep -v '^risk:override-' | head -1`.
   - First, **freshness**: compare PR head SHA to `scored_sha=` in the latest `<!-- risk-score: ... -->` comment. Mismatch/missing → auto-invoke `/risk-score <pr>`, then re-read. A label from a stale commit is not trusted.
   - `risk:green` → proceed silently. `risk:blue` → proceed, note tier in report.
   - `risk:yellow` / `risk:red` → STOP, print the reason from the classifier comment, require `--ack-yellow` / `--ack-red` in `$ARGUMENTS` to proceed (log the ack in the report + step 4a).
   - `risk:needs-scoring` or no label (in a classifier repo) → auto-invoke `/risk-score <pr>` once, re-read, resume. Still missing → STOP, tell user to inspect the classifier run.
   - Rationale: the classifier is the system's blast-radius signal; ignoring it defeats the two-stage pipeline. A missing label is almost always a timing gap, so auto-score rather than punt.

3. **Poll until green — background, not foreground.** Run `${CLAUDE_PLUGIN_ROOT}/scripts/ship-poll.sh <pr>` with `run_in_background: true`. It **self-exits** the instant the PR reaches a terminal-for-ship state, emitting one heartbeat per tick and a final verdict token on its last line; the background task then re-invokes you with that output. **Do NOT arm a `tail -F | grep` Monitor on it** — a perpetual Monitor never self-exits and lingers on the statusline after the verdict already fired, piling up across back-to-back ships (why: 2026-06-10 — two stale CI-verdict monitors sat armed after their PRs had merged). The background-task completion notification IS the signal. Surface the output-file path so the user can `! tail -f` it. Act on the verdict token:
   - `merged` → auto-merge already fired; skip to step 6.
   - `READY` / `READY_NO_CHECKS` → break, go to step 4 (manual merge — auto-merge didn't fire or repo has no CI).
   - `FAILURE` → step 3a.
   - `STALL` → ship-poll saw no state change for 5 min: a check is hung or the PR is gated outside the rollup (review required, branch protection). Report what's pending + the gate, stop.
   - `closed` → stop. `TIMEOUT` (20 min hard cap) → report what's pending, stop.
   - Never `gh pr checks --watch` (blocks on the slowest check, no liveness output).

3a. **Investigate every failure automatically — never punt.** Pull the log (`gh run view --job <job-id> --log-failed`), name the root cause in one sentence (code / infra / flake / config / secret / upstream). Then check if it actually blocks: `gh pr view <pr> --json mergeable,mergeStateStatus`. If `MERGEABLE` and the failed check is non-required (common on private repos), it's cosmetic — continue to step 4, note it in the report. If it's a real blocker: code issue → report file/line + fix, stop; infra/billing/upstream → report cause + affected workflow + remediation, stop; flake → `gh run rerun <run-id> --failed` once, back to step 3 (fails again = not a flake).

4. **Verify mergeable.** `gh pr view <pr> --json state,mergeable,mergeStateStatus` → require `OPEN` / `MERGEABLE` / `CLEAN`. Else report and stop.

4a. **Log ack** (only if past a yellow/red gate): `gh pr comment <pr> --body "Shipped with \`--ack-<tier>\` override by @$(gh api user --jq .login) at $(date -u +%Y-%m-%dT%H:%M:%SZ). Classifier tier: <tier>."`

5. **Merge.** `gh pr merge <pr> --squash --delete-branch`. `--delete-branch` may print a cosmetic worktree-collision error locally — the merge still landed. Confirm: `gh pr view <pr> --json state,mergedAt` → `MERGED` means success regardless of local stderr.

6. **Clean up.** Path depends on how you entered the worktree:
   - `EnterWorktree(name:...)` (this-session create) → `ExitWorktree(action: "remove")` deletes dir + branch.
   - `EnterWorktree(path:...)` (pre-existing) → `remove` is a no-op; do the dance: `ExitWorktree(action: "keep")`, then from main repo `git worktree remove <path> 2>&1; git branch -D <branch> 2>&1`.
   - Not in a worktree → `git branch -D <branch>` from main.
   - Then `git checkout main 2>&1 | tail -2; git pull --ff-only 2>&1 | tail -3`.
   - Local-branch cleanup is mandatory: the pretool hook strips `--delete-branch` inside a worktree, so the merge only deleted the *remote* branch.
   - **No lingering background tasks.** ship-poll self-exits on its verdict, so there is no Monitor to stop. Leave the step-6a deploy-verify shell running (it self-exits and reports). If you armed any other `run_in_background` shell, `TaskStop` it. Statusline should be clear of this ship's tasks before you report.

6a. **Verify prod deploy** (skip if no `railway.json`). Run `${CLAUDE_PLUGIN_ROOT}/scripts/ship-verify-deploy.sh <pr> <service> [health-url] [environment]` with `run_in_background: true`; report the deploy line as a follow-up when it exits. The script handles the timeout/auth/diff-gate/poll logic and exits 0 (verified or cleanly skipped) or 2 (couldn't verify → tell user to check the dashboard). Get `<service>` from `railway status --json` (the service whose source repo matches this one); derive `[health-url]` from the prod domain + the repo's health path (e.g. `https://<domain>/api/health`) — omit it if unknown. `[environment]` defaults to `production`; pass it only if the repo's prod env is named otherwise. A green check is not a green deploy — preview and prod pass different gates. **If the deploy line reports `FAILED`/`CRASHED`, investigate per the step-3a discipline (pull logs, name root cause) — don't just relay the string.**

6b. **Prune the PR's preview env** (skip if the repo has no `railway:prune-envs` script in `package.json`). A merged PR's Railway preview environment goes stale the instant it merges, but Railway's auto-delete-on-close leaks stragglers. They pile up silently until the CLI's project query decode-errors (`expected value at line 1 column 1`), which breaks `railway status`, `railway link`, and the step-6a auth probe. Delete it at the source: `bun run railway:prune-envs --pr <pr>` (foreground, fast). The repo's script must scope deletion to that single PR's env and refuse open PRs. Generic across repos -- gated on the script existing, so repos without it no-op. Incident 2026-06-05: 17 stragglers piled to 21 and broke every env-scoped CLI op in preach-hub.

7. **Report.** One or two sentences: PR number, merged URL, cleanup status. Note if prod-verify is running in background (status follows) or was skipped. Nothing more.

## Principles

- **A failing check is a signal, not a dead-end.** There is no "a check failed, want me to look?" — if it failed, look (step 3a). The user invoked `/ship` presupposing failures get investigated.
- **A running check is not a reason to freeze.** Stream snapshots; the user wants liveness, not suspense.
- **CI is the authority** — don't re-run tests locally, don't ask for confirmation when gates pass, don't merge over a real failure to "unblock."
