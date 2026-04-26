---
name: ptv-idea
description: "PTVM audit of an idea/proposal/plan BEFORE diff. Triggers: /ptv-idea, /ptvi, 'is this worth building', 'audit this proposal', 'sanity-check this plan'."
argument-hint: "[level] <idea text | path to spec | 'last turn'>  e.g. 'huff add dark mode toggle', 'sniff docs/SMOKE_LEDGER_PLAN.md'"
---

# PTV-Idea -- Audit the Proposal, Not the Diff

Same PTVM bar as `fart-sniffing-detection`, applied to an idea before code exists. Catch cologne at the proposal stage -- the cheapest place to kill bloat. YAGNI.

## When to use

- `/ptv-idea [level] <idea>`
- `/ptvi [level] <idea>` -- alias
- `/prove-the-value-idea [level] <idea>` -- alias
- "is this idea worth building?"
- "PTV this proposal / spec / plan"
- "sanity-check this before I write code"
- After a brainstorm, before a plan doc.
- After a plan doc, before a PR.

Use `fart-sniffing-detection` instead when shipped commits exist and you want to audit the diff.

## Criticality levels

Pick one. Default = `sniff`. Same vocabulary as PTVM so muscle memory carries.

| Level | Posture | What passes |
|-------|---------|-------------|
| `whiff` | Benefit of doubt. | Any idea with a plausible user or dev win. Flag obvious overreach only. |
| `sniff` | Balanced. Default. | Ideas with concrete value or low cost. Flag speculative scope, premature frameworks, unproven premise. |
| `huff` | Skeptical. | Must name a *specific recent* pain it solves. Kill aspirational matrices, "future-proof" designs, tiered rollouts without baseline data. |
| `dutch-oven-yourselff` | Max skepticism. | Only greenlight the *smallest* version that proves the premise. Everything else deferred until that version ships and produces signal. |

## Input resolution

Figure out what to audit, in this order:

1. **Inline text** after the level token -- treat as the idea.
2. **Path** to a spec/plan/doc (`.md`, `.txt`) -- read and audit.
3. **"last turn"** / "this proposal" / "what I just said" -- audit the most recent user message or assistant proposal in conversation context.
4. **No arg** -- scan recent conversation for the most recent proposal-shaped content (bullet lists, "I want to add X", `Status: next` items the user is actively discussing). If ambiguous, ask.

Never audit code diffs here -- route to `fart-sniffing-detection`.

## Audit dimensions

For each proposal, work through these six dimensions. Be concrete; name specifics from the proposal.

1. **Premise** -- Is the stated problem real, recent, and recurring? Or assumed?
   - Strong: "item X failed yesterday," "Y users hit this," "regression landed via PR #Z."
   - Weak: "feels brittle," "might need later," "industry best practice."
2. **Value** -- Who benefits, measurably, if this ships today?
   - Concrete user pain / dev friction / $ saved / incident avoided -> strong.
   - Hypothetical, generalized, "scaling" -> weak.
3. **Complexity** -- Moving parts introduced. New files, configs, abstractions, mental models. Count them.
   - <=3 parts tightly scoped -> strong.
   - Framework / matrix / tier system / new vocabulary -> suspect at `sniff`, KILL at `huff`.
4. **Alternatives** -- Did the proposal consider simpler options? Name at least one cheaper path and why it was rejected (or why it wasn't mentioned).
5. **Reversibility** -- If this turns out wrong in 2 weeks, how painful is the rollback?
   - File-level addition, no callers -> cheap.
   - New abstraction with downstream callers / migration / schema -> expensive.
6. **Scope creep** -- Which parts are load-bearing for the *premise* vs cologne? Retro tables, decision matrices, tier rollouts, naming systems, doc scaffolding are frequent cologne.

## Verdicts

Per dimension: `STRONG` / `OK` / `THIN` / `MISSING`.

Overall: one of

- **BUILD** -- earns it. Ship the proposal as written.
- **TRIM** -- core premise is load-bearing; cut specific parts and ship the rest.
- **DEFER** -- premise plausible but unproven. Ship a smaller version first; come back with data.
- **KILL** -- cologne. Abandon.

Always include a **Smallest Version That Proves The Premise (SVTPTP)** -- the cheapest thing you could ship in one PR that would generate signal about whether the full proposal earns its keep. Even on BUILD, name it -- often reveals the real scope.

## Output format

```
# PTV-Idea Audit -- [level] -- [short title of idea]

Premise in one line: <restate what the user is proposing, in your own words, so they can verify understanding>

## Dimensions

- **Premise:** [STRONG|OK|THIN|MISSING] -- <specific reason>
- **Value:** [...] -- <who benefits, measurably>
- **Complexity:** [...] -- <count moving parts>
- **Alternatives:** [...] -- <name a cheaper path or flag the omission>
- **Reversibility:** [...] -- <rollback cost>
- **Scope creep:** [...] -- <which parts are cologne>

## Verdict: BUILD | TRIM | DEFER | KILL

<one paragraph, direct. Name the specific parts to cut / keep / defer.>

## Smallest Version That Proves The Premise

<one-PR-sized scope that would produce decision-quality signal. Even on BUILD.>

## What would flip the verdict

<one-liner: what evidence would move this from DEFER -> BUILD, or TRIM -> BUILD.>
```

## Anti-patterns to flag hard

- **Tier systems / level matrices (L0-LN)** before L0 has produced data.
- **Decision matrices** whose rows are speculation, not observed cases.
- **Retro backtest tables** that are directionally useful but don't change the near-term scope.
- **Frameworks / vocabularies / naming systems** introduced before the thing they describe exists twice.
- **"Phase 2/3" bullets** that assume Phase 1 will succeed.
- **"Eventually we'll want..."** any sentence with "eventually" is cologne bait.
- **Self-generalizing scope** -- idea starts as "fix X" and the proposal contains "so we should also..." three times.
- **Metrics without baselines** -- "cut latency 20%" with no current latency number.
- **Governance / promotion gates / SLAs** for a feature with zero users.

## Tone

Direct. PTVM. Do not soften. "This is cologne" > "this might be reconsidered." False KILLs are as bad as false BUILDs -- if a proposal is load-bearing, say so clearly.

The point is to kill bloat at the proposal stage so it never becomes a diff. Be the friend who says "don't build that yet."

## Boundaries

- Do not write the code. Do not draft the plan doc. Recommend only.
- If the idea is genuinely ambiguous and you cannot restate the premise in one line, ask ONE clarifying question before auditing.
- If the proposal is actually a bug fix or incident response (not a new-feature idea), route to normal planning -- PTV-Idea is for *new additions*, not corrections.
- Never invent value the user didn't claim. If value is implicit, mark `Value: THIN` and surface it.
