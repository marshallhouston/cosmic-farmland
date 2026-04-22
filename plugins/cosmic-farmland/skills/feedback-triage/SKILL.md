---
name: feedback-triage
description: Intake raw feedback from a person, categorize and triage each item into structured actionable units, then auto-spawn worktrees for accepted items. Use when the user says "triage this feedback", "categorize feedback from X", "/feedback-triage", pastes a block of feedback from a named source (co-founder, user, tester), or wants to turn a feedback dump into per-item decisions + worktrees. Not for single-bug reports or code review comments -- those have their own flows.
---

# Feedback Triage

Turn a raw feedback blob into a structured triage doc, then auto-spawn worktrees for accepted items. Reusable across projects via per-project config.

## When to use

Trigger when:
- User pastes feedback from a named source (person, channel, meeting notes) and wants to process it
- User says: "triage", "categorize", "what do we do with this feedback", "rip on this"
- User invokes `/feedback-triage`

Not for: single-bug reports, code review comments on a PR, one-off asks that map to one task. Those skip the triage doc.

## Inputs required

Before triaging, confirm:
1. **Source** — who gave the feedback (name or channel). Used in filename + attribution.
2. **Date** — when received (default: today).
3. **Raw content** — paste-in blob. Preserve verbatim for audit.

## Process

### Step 1 — Load project config

Read `.feedback-triage.json` at repo root. If absent, use defaults below and note it.

Config schema:
```json
{
  "docs_dir": "docs/feedback",
  "index_file": "docs/feedback/INDEX.md",
  "categories": ["IA", "feature", "content", "bug", "polish", "vision"],
  "tiers": ["v1", "v2", "v3", "vX"],
  "sizes": ["S", "M", "L"],
  "decisions": ["accept", "defer", "reject", "needs-discussion"],
  "worktree_prefix": "feedback",
  "tracker_file": "docs/V1_PLUS.md",
  "tracker_append_on_accept": false,
  "auto_spawn_worktrees": true
}
```

Unknown categories/tiers in user confirmation: ask, then offer to extend config.

### Step 2 — Parse feedback into items

Break blob into atomic items. One "ask" = one item. Merges ("combine X and Y into Z") = one item. Multi-part suggestions ("do A with subcats B, C, D") = one item if they stand or fall together, else split.

### Step 3 — Triage each item

For each item, fill:
- **Raw quote** — verbatim from source
- **Category** — from config
- **Tier** — from config
- **Size** — S/M/L (no time estimates)
- **Decision** — from config
- **Rationale** — one sentence. Why this tier, why this decision.
- **Next action** — if `accept`: worktree branch name (slugified). Else: what unblocks it.
- **Dependencies** — other items, missing primitives, external blockers

Propose the full triage to the user in a compact table before writing. Let them override any field.

### Step 4 — Write the doc

Path: `{docs_dir}/YYYY-MM-DD-{source-slug}.md`

Template:
```markdown
# Feedback triage — {source} — {date}

**Source:** {source}
**Received:** {date}
**Triaged:** {date}

## Raw feedback

> {verbatim blob}

## Items

### 1. {short title}
- **Quote:** {raw quote}
- **Category:** {cat}
- **Tier:** {tier}
- **Size:** {size}
- **Decision:** {decision}
- **Rationale:** {one sentence}
- **Next action:** {branch name or unblock condition}
- **Dependencies:** {list or none}

### 2. ...

## Worktrees to spawn

- `{prefix}/{branch-1}` — {one-line scope}
- `{prefix}/{branch-2}` — {one-line scope}

## Deferred / rejected / discussion

- {item} — {reason}
```

### Step 5 — Update index

Append to `{index_file}` (create if missing):
```markdown
- YYYY-MM-DD — {source} — {N items, M accepted} — [link](./YYYY-MM-DD-source.md)
```

### Step 6 — Auto-spawn worktrees (if config enables)

For each `accept` item with a branch name:
1. Create worktree via `git worktree add ../{repo}-{branch-slug} -b {prefix}/{branch-slug}`
2. Use the repo's existing worktree convention (check sibling worktrees first — match naming)
3. Copy the triage doc path into the worktree's first commit message as a reference? No — leave that to the per-worktree work

Report list of spawned worktree paths back to user.

If `auto_spawn_worktrees: false`: list candidates, stop. User spawns manually.

### Step 7 — Project-specific tracker integration (optional)

If `tracker_append_on_accept: true`: append accepted items to `{tracker_file}` using that project's conventions. Read the tracker first to match format. Ask user if conventions are unclear — do not guess.

## Guardrails

- **Don't re-triage items already in the index** — check for prior triage of the same source+date before writing. If exists, offer merge or overwrite.
- **Don't spawn worktrees silently** — always list them before creating.
- **Preserve the raw quote** — never paraphrase into the `Quote` field. Future re-reads need source fidelity.
- **No time estimates** — use Size (S/M/L) and complexity notes only.
- **Slugify branch names** — lowercase, hyphens, no punctuation. Max ~40 chars.

## Red flags — stop and ask

- Feedback contains a security issue → break out, handle separately, do not bury in triage
- Feedback is really a spec (>1000 words of detailed requirements) → suggest `/ce-plan` or brainstorming skill instead
- User pastes code review comments → redirect to PR review flow
- Source is anonymous or unclear → ask before filing
