---
description: List your open PRs and ship them in sequence. Replaces /ship -> /ship loops.
argument-hint: "[--ack-yellow|--ack-red] (passed to each /ship)"
---

# /ship-all

Drain the open-PR queue. Lists every open PR you authored, then ships
each in turn via the existing `/ship` flow.

Pattern miner over 7d preach-hub: `/ship → /ship` fired 49 times across
27 sessions (2026-04-27 baseline). This replaces the manual N-invocation
loop.

## Flow

### 1. Find open PRs you authored

```bash
gh pr list --author "@me" --state open --json number,title,headRefName,url \
  --jq '.[] | "\(.number)\t\(.title)\t\(.headRefName)"'
```

Sort by PR number ascending (oldest first). Print to user as a numbered list.

### 2. Confirmation menu (single confirmation, not per-PR)

Show:
```
Found N open PRs:
  #123  feat: ...
  #124  fix: ...
  #125  chore: ...

Ship all? [y / select-numbers / n]
```

Parse response:
- `y` / `yes` / `all` → ship all
- comma-separated numbers (e.g. `1,3`) → ship those by index
- `n` / `no` → abort

**Do not re-ask between PRs.** That defeats the purpose. One confirmation,
then drain.

### 3. Ship loop

For each selected PR:

1. **cd into the matching worktree.** `git worktree list` -> find the
   one whose branch matches `headRefName`. If no worktree, `cd` into the
   main repo (the branch must be checked out somewhere or `gh pr merge`
   will not be able to clean up).
2. Invoke `/ship <pr-number>` with any pass-through flags from
   `$ARGUMENTS`.
3. Capture result: `merged` / `blocked-yellow` / `blocked-red` / `failed`.
4. Continue to next PR regardless. Do not stop on individual failures
   unless they indicate systemic problems (auth failure, network down).

### 4. Summary

Print final tally:
```
Shipped: N
Blocked: M (#123 yellow, #124 red)
Failed:  K (#125 - merge conflict)
```

For blocked PRs, include the gate reason inline. User can re-invoke with
`--ack-yellow` / `--ack-red` if intentional.

## Don't

- Re-confirm between PRs. One menu up front, then go.
- Modify or replace `/ship`. Compose it.
- Ship PRs you didn't author (filter by `--author "@me"`).
- Auto-pass `--ack-yellow` / `--ack-red` unless `$ARGUMENTS` includes them
  -- those acks must be explicit per invocation.

## When to use vs `/ship`

- `/ship` -- one PR, deliberate.
- `/ship-all` -- queue drain at end of session, batch confidence.
- `/wrap` -- single PR + handoff. Different use case.
