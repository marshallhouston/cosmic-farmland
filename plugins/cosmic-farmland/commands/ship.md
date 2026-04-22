---
description: Watch a PR's checks, merge when green, clean up the worktree + local branch
argument-hint: "[pr-number] (defaults to current branch's PR)"
---

# /ship

End-to-end tail for a PR: wait for green, merge, clean up.

## Preconditions

- PR is already pushed and open on GitHub.
- You are in the worktree (or repo) where the branch lives.
- The diff has been reviewed/tested to the extent the task warrants.

If these aren't true, stop and tell the user.

## Flow

1. **Resolve PR number.** If `$ARGUMENTS` is a number, use it. Otherwise `gh pr view --json number -q .number`. If neither works, stop.

2. **Watch checks.** Run `gh pr checks <pr> --watch`. Block until it exits.

3. **Verify required checks all passed.** Parse the final output — look for every row marked `pass`. If anything is `fail`, go to step 3a. Otherwise continue.

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

5. **Merge.** `gh pr merge <pr> --squash --delete-branch`.
   - `--delete-branch` may fail locally from a worktree with a cosmetic `'main' is already used by worktree` error — this is expected and the merge still succeeded on GitHub.
   - After merge, verify with `gh pr view <pr> --json state,mergedAt`. If `state: MERGED`, treat as success regardless of local stderr.

6. **Clean up.**
   - If running from a worktree: `cd` out, then `git worktree remove <path>`. If worktree has uncommitted changes beyond the merged work, stop and ask.
   - Delete local branch: `git branch -D <branch>` (ignore if already gone).
   - In the main checkout: `git pull --ff-only` on `main` (or whatever the repo's default branch is).

7. **Report.** One or two sentences: PR number, merged URL, cleanup status. Nothing more.

## Non-goals

- Do not re-run tests locally before merging. CI is the authority.
- Do not ask for confirmation at any step if all gates pass. Trust the checks.
- Do not merge with failing checks "just to unblock." If something failed, fix it or escalate.

## When things go wrong

- CI check fails → follow step 3a automatically: pull logs, diagnose root cause, check if merge is actually blocked, act accordingly. Never stop at "classify failed, investigate?".
- A check stays pending after watch exits → re-run `gh pr checks <pr> --watch`.
- Merge blocked by review required / conflicts → report state and stop.
- Worktree cleanup fails because of uncommitted files → stop, tell the user what's there.

## Principle

A failing check is a signal, not a dead-end. There is no world where the correct response is "a check failed, want me to look?" — if it failed, look. The user's reason for invoking `/ship` presupposes that failures get investigated, not ignored or deferred back.
