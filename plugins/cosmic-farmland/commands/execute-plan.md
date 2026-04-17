---
description: Execute a superpowers implementation plan via subagent-driven-development (one subagent per task, stop before push). Defaults to the most recently modified plan in docs/superpowers/plans/.
---

## Step 0 — Resolve the plan and show marshall the context

**If `$ARGUMENTS` is non-empty:** treat it as the plan path. Skip to the pre-flight block below.

**If `$ARGUMENTS` is empty:** resolve the most recently modified plan:

```bash
ls -t docs/superpowers/plans/*.md 2>/dev/null | head -5
```

- **Zero results** → stop and tell marshall: "No plans found in `docs/superpowers/plans/`. Pass a path explicitly or write a plan first with `superpowers:writing-plans`."
- **One or more results** → pick the top one (most recently modified). Don't filter by "looks unexecuted" or "matches branch" — mtime is the signal.

### Pre-flight block

Before doing anything else, print this exact compact block so marshall can eyeball it in one glance:

```
Plan:      <filename>       (modified <N> min/hrs ago)
Branch:    <current branch>
Dirty:     <N modified, N staged, N untracked>
  <up to 5 dirty file paths, prefixed with M/A/??>
Other recent plans:
  <up to 3 next-most-recent filenames, or "none">
```

Gather the inputs via:

```bash
git rev-parse --abbrev-ref HEAD
git status --short
```

Plus the `ls -t` output you already have.

Then say one sentence: "Proceeding unless you say otherwise." **Do not** dispatch any subagents or read other files yet — marshall gets one beat to interrupt with "wait" / "use X instead" / "switch to worktree Y". If he doesn't, continue to Step 1.

Why show git state: if the plan is `2026-04-11-error-handling.md` and the dirty files are all in `src/pages/ReadSidebar.tsx`, something is off — either wrong worktree or leftover work from something else. Surface the mismatch visually, don't try to infer it.

## Step 1 — Read the plan and any linked context

1. Read the resolved plan file in full. Don't skim.
2. If the plan links to a spec (`docs/superpowers/specs/...`) or other documents, read those too. They establish the "don't relitigate" baseline.
3. Check the current branch and `git status`. If the plan was written in a worktree and you're on `main` (or vice versa), stop and ask marshall before proceeding. Don't switch branches or create a worktree on your own.

## Step 2 — Execute via subagent-driven-development

Invoke the `superpowers:subagent-driven-development` skill. One fresh subagent per task. Review between tasks. Don't batch multiple tasks into one subagent.

## Ground rules

- **The plan is the contract.** Don't relitigate decisions from the plan or any linked spec. Your job is to translate the plan into code, not to redesign it. If the plan says "use X pattern" and you'd personally pick Y, use X.
- **Follow tasks in the order the plan defines.** Each task ends in a commit per the plan's instructions — don't skip commits, squash them together, or "clean up" the history.
- **Run the verification commands the plan specifies between steps.** If a TDD step says "run the test and confirm it fails" and the test passes, stop and investigate — something is off. Don't paper over it.
- **Stop and ask before improvising.** If you hit something the plan didn't anticipate — missing file, unexpected existing state, type error the plan doesn't address, test scaffolding gap — stop and ask marshall. Don't:
  - Add features, error handling, or "improvements" that aren't in the plan
  - Refactor unrelated code you happen to touch
  - Skip a step because it "seems unnecessary"
  - Change the plan's commit messages to be "better"
- **Don't push or open a PR.** Stop after the final task's last commit. Show marshall the commit list with `git log --oneline main..HEAD` (or the appropriate base branch) and wait for further instructions.

## Announcing progress

Between tasks, give marshall a one-line status: "Task N complete, commit `<sha>`, moving to Task N+1." Nothing more. He can read the diff.

If a subagent's output needs review before proceeding (test failures, unexpected diffs, ambiguous choices), surface it immediately — don't dispatch the next subagent until marshall has seen it.
