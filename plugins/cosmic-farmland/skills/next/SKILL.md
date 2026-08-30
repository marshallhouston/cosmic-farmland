---
name: next
description: "What to work on next here: git state, PRs, worktrees, backlog docs, issues. Triggers: /next, 'what's next', 'what should I work on', 'what now'."
argument-hint: "(none) — reads repo state automatically"
---

# /next — What's next here?

Answer the literal question "what should I work on next in this repo?" by reading state. No taxonomy, no modes, no ceremony. Let the state dictate the shape of the answer.

## When to use

- `/next`
- "what's next?"
- "what should I work on?"
- "what now?"
- "where was I?"
- Session resumption after `/clear` or handoff.

## Gather signals (parallel)

Run these together, don't serialize:

1. `git status -sb` — branch, ahead/behind, uncommitted
2. `git log --oneline -5` — recent commits
3. `gh pr list --author @me --state open --json number,title,headRefName,isDraft,mergeable,statusCheckRollup` — open PRs
4. `gh pr checks` on current branch if a PR exists
5. `ls .worktrees/ 2>/dev/null` + per-worktree `git -C <path> status -sb` — in-flight parallel work
6. `gh issue list --limit 10 --state open`
7. Planning docs — read whichever exist: `.claude/BACKLOG.md`, `BACKLOG.md`, `ROADMAP.md`, `docs/ROADMAP.md`, `docs/V1_PLUS.md`, `docs/MVP_SCOPE.md`, `docs/plans/`, `docs/superpowers/plans/`, `TODO.md`. **Skip `*/archive/` subdirs — already-shipped.**
8. Stash list (`git stash list`) — abandoned WIP signal

Skip anything that errors or is missing. Don't announce the skips.

## Decide the answer from state

Walk the signals in order; the first one that has a concrete next action wins. Do not list all categories; answer the specific thing.

1. **Uncommitted changes on current branch** → commit or stash.
2. **Committed but unpushed** → push.
3. **Pushed but no PR** → open PR.
4. **Open PR, checks failing** → fix failing checks (name them).
5. **Open PR, checks green, mergeable** → merge.
6. **Open PR, awaiting review** → nudge or context-switch.
7. **Just merged/shipped, tree clean, <2h since last commit** → 1-2 adjacent follow-ups (post-ship verification, docs, adjacent worktree).
8. **Worktree w/ unpushed commits** → finish that thread.
9. **Stash entries present** → surface top stash entry as potential resume.
10. **Clean + idle** → top 3 from planning docs / open issues / worktrees. Tag each `[BACKLOG]` / `[issue #N]` / `[worktree <name>]` / `[ROADMAP]`.

If multiple apply, pick the most immediate (lower number wins).

## Cross-check before listing a plan as unbuilt (repo > headers)

Plan-doc status headers go stale — a doc reading "no code yet" / "0 tasks" can describe already-shipped work. **A header is a claim, not truth. Verify against repo state before listing a plan as next:**

- Grep `git log --oneline -50` for the plan's feature name / scope. A matching `feat(...)` commit → shipped, don't list it.
- Check whether the plan's named artifacts exist (the script/file/CLI the plan says it builds). Present → shipped.
- If shipped but the doc still claims unbuilt: say so, and move the doc to `<dir>/archive/` with a SHIPPED header instead of listing it.

Trust the repo over the header every time.

## Output format

Keep it tight. Match this shape:

```
**State:** <one line — branch, clean/dirty, last commit age, open PR if any>

**Next:** <one concrete action, imperative verb>

<if idle/clean + no active thread, then:>
Or:
- <option 1> — [tag]
- <option 2> — [tag]
- <option 3> — [tag]
```

Never output more than 3 options. Never pad with categories that have nothing.

## Anti-patterns

- Don't do a strategic zoom-out when answer is "push to origin."
- Don't list every worktree. Only cite worktrees w/ unpushed commits or the one matching current focus.
- Don't cite memory/prior-session facts without verifying against live state.
- Don't narrate the signal gathering. Just answer.
- Don't ask "which would you like?" unless 3+ options are genuinely equal priority AND there's no active thread.
- Don't invent priorities. If no planning doc exists and no issues are open, say "no queued work found — pick yourself or start a brainstorm."

## Tone

Terse. Imperative. One sentence per line. This skill is for someone mid-flow who wants to know the next move, not a briefing.
