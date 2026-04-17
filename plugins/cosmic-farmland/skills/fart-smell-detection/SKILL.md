---
name: fart-smell-detection
description: "Audit recent commits/PRs for bloat vs real value using PTVM (Prove The Value Motherfucker). Flags cologne-sniffing changes, ranks kill candidates. Use when the user says /fart-smell-detection, /ptvm, /prove-the-value-motherfucker, asks 'is this bloat?', 'prove the value', 'PTVM this', 'which of these commits are worth keeping', or wants a skeptical review of a batch of changes before merge."
argument-hint: "[level] [target]  e.g. 'huff PR #42', 'sniff main..HEAD', 'dutch-oven-yourselff' (staged)"
---

# Fart-Smell Detection -- PTVM Audit

Skeptically review a batch of changes. Prove every commit earns its keep. Kill the cologne-sniffing ones.

## When to use

- `/fart-smell-detection [level] [target]`
- `/ptvm [level] [target]` — alias
- `/prove-the-value-motherfucker [level] [target]` — alias
- "did we just add bloat?"
- "PTVM these commits"
- "which of these are fart-sniffing?"
- After a batch of commits lands and the user is worried about cologne.

## Criticality levels

Pick one. Default = `sniff`.

| Level | Posture | What passes |
|-------|---------|-------------|
| `whiff` | Benefit of doubt. Light pass. | Anything plausibly useful. Only flag obvious dead weight. |
| `sniff` | Balanced PTVM. Default. | Changes with clear value or low cost. Flag speculative defense / unused abstractions. |
| `huff` | Skeptical. Lungs full. | Must prove concrete value today, not hypothetical. Kill speculative hardening, premature abstractions, "nice to haves". |
| `dutch-oven-yourselff` | Max skepticism. Nuke anything not load-bearing. | Only keep changes required for correctness, data integrity, or an actual observed bug. Everything else = fart. |

Level escalation = stricter burden of proof. Same audit structure, different threshold.

## Input resolution

Figure out what to audit, in this order:

1. **Explicit PR**: `PR #42` or a GitHub URL → `gh pr view <n> --json commits,files,title,body` + `gh pr diff <n>`.
2. **Git range**: `main..HEAD`, `HEAD~5..HEAD`, a SHA range → `git log --oneline <range>`, `git show <sha>` per commit.
3. **Staged**: `--staged` flag or no target given and staged changes exist → `git diff --cached` as one unit.
4. **Auto-detect PR**: no target, no staged → run `gh pr view --json number,commits,files,title,body` on current branch. If a PR is open, audit it.
5. **Recent**: no target, no staged, no PR → last commit (`HEAD`) plus ask whether to widen.

If ambiguous, ask before auditing.

## Audit process

For each commit (or logical chunk):

1. **State it plainly** — one line: what it changes, line count.
2. **PTVM it** — answer: *what breaks in production today if this commit did not exist?*
   - Concrete bug it fixes? Keep.
   - Correctness / data integrity / observed failure? Keep.
   - Defense against attacker that cannot reach this code? Suspect.
   - Abstraction with one caller? Suspect.
   - "Nice polish" with no user-visible effect? Suspect at `huff`+, kill at `gag`.
3. **Verdict** — one of:
   - `KEEP` — earns its place.
   - `SUSPECT` — PTV is thin; acknowledge cost but small enough to leave.
   - `KILL` — cologne. Revert candidate.
4. **Reason** — one short paragraph. Name the *specific* thing that justifies or fails to justify it. No hedging.

## Output format

Match this shape (mirrors the example the user referenced):

```
# Fart-Smell Audit — [level] — [target]

## Per-commit verdicts

**A — <short title> (<N> lines): KEEP / SUSPECT / KILL**
<one-paragraph PTVM reasoning>

**B — ...**
...

## Kill candidates (ordered by most fart-sniffy)

1. <commit> — <why it smells>
2. ...

## Bottom line

<2-3 sentences. Is this bloat or not? What % of changed lines are load-bearing?
Concrete recommendation: ship / revert X / split Y.>
```

Letter commits A, B, C... in the order they landed so the user can reference them.

## Anti-patterns to watch for

Tune sensitivity by level, but always scan for these:

- **Defense-in-depth against nobody** — input sanitization on a single-user local tool, path-traversal checks on self-written paths.
- **Abstraction with one caller** — helper functions, wrapper classes, config objects used in exactly one place.
- **Speculative flexibility** — options/flags with no current consumer, "in case we need it later".
- **Comment bloat** — docstrings restating the function name, `# removed` tombstones, "used by X" references that rot.

- **Test theater** — tests that assert the implementation rather than behavior.
- **Re-exports and shims** — backwards-compat for code that was never released.
- **Logging flood** — debug logs left in after the bug was found.

At `huff` and `dutch-oven-yourselff`, treat "might be useful someday" as automatic KILL.

## Tone

Be direct. This is the point of the skill. "This smells" > "this might potentially be worth reconsidering". Do not soften. The user invoked this skill because they want the honest read, not cologne about the cologne.

Never soften verdicts to be nice. Never invent value that is not there. If a commit is load-bearing, say so clearly — false KILLs are as bad as false KEEPs.

## Boundaries

- Do not actually revert commits. Recommend, do not execute. User decides.
- If unsure whether something is load-bearing, say so — mark `SUSPECT` with the specific unknown, do not guess `KILL`.
- Code/commits/PRs referenced in output: use exact SHA / PR number / filename. No paraphrasing identifiers.
