---
description: End-of-session cap. Ships current PR (or skips if none), then writes resumption prompt.
argument-hint: "[pr-number] (optional, defaults to current branch's PR)"
---

# /wrap

End-of-session combo: ship current PR + generate handoff. Replaces the
`/ship → /handoff` pattern (13 occurrences across 13 sessions in 7d
preach-hub data, 2026-04-27 baseline).

## Flow

### 1. Detect PR state

Try `gh pr view --json number,state -q '.number,.state'` (or use `$ARGUMENTS` if
provided as PR number).

- **No PR for this branch**: skip ship phase. Proceed directly to step 3.
- **PR exists, OPEN**: proceed to step 2.
- **PR exists, MERGED/CLOSED**: skip ship phase, proceed to step 3.

### 2. Ship phase

Invoke `/ship` (or the equivalent ship flow from this plugin's `commands/ship.md`).
Pass through any flags from `$ARGUMENTS` (e.g. `--ack-yellow`, `--ack-red`).

If ship halts (yellow/red gate, conflict, CI red), STOP. Do not write handoff
of partial state. Tell user: "Ship blocked at <gate>. Resolve, then re-invoke
`/wrap` (or `/handoff` directly if not shipping)."

### 3. Handoff phase

Invoke the `handoff` skill from this plugin (or `superpowers:handoff` if not
loaded). Pass any context from the ship phase (PR number, merge SHA) so the
resumption prompt can reference what was just shipped.

### 4. Final output

Print:
- Ship result: `merged | skipped (no PR) | skipped (already closed)`
- Handoff path or pasted prompt
- Next-session reminder if anything is mid-flight (open worktree, in-progress
  branch, unresolved review comment)

## Why this exists

Pattern miner over 7d CC sessions surfaced `/ship → /handoff` as a
high-recurrence end-of-session signal. Combining cuts 2 invocations to 1
and ensures handoff captures the just-shipped PR as a frozen decision.

## Don't

- Run handoff first, then ship. Ship state is part of the handoff content.
- Continue to handoff if ship halted on a risk gate -- that ack is a
  conscious decision and should not be auto-resumed in a fresh session
  without re-evaluation.
- Replace existing `/ship` or `/handoff`. This composes them.
