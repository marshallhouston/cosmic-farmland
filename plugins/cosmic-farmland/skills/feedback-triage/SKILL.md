---
name: feedback-triage
description: Triage raw feedback into structured items, optionally spawn worktrees for accepted ones. Triggers: "triage feedback", "rip on this", "/feedback-triage", or pasted block from named source. Not for single bugs or file review (use /feedback).
---

# Feedback Triage

Turn a raw feedback blob into a structured triage doc, then optionally spawn worktrees for accepted items.

## When to use

Trigger when:
- User pastes feedback from a named source (person, channel, meeting notes) and wants to process it
- User says: "triage", "categorize", "rip on this", "what do we do with this feedback"
- User invokes `/feedback-triage`

Not for:
- Single-bug reports (one task, no triage needed)
- PR review comments (use the PR review flow)
- Section-by-section review of an existing file (use `/feedback`)

## Inputs required

Before triaging, confirm:
1. **Source** — who gave the feedback (name or channel). Used in filename + attribution.
2. **Date** — when received (default: today).
3. **Raw content** — paste-in blob. Preserve verbatim for audit.

## Process

### Step 1 — Load project config

Read `.feedback-triage.json` at repo root. If absent, use defaults below.

Config schema (all optional):
```json
{
  "docs_dir": "docs/feedback",
  "index_file": "docs/feedback/INDEX.md"
}
```

Categories, tiers, sizes, and decisions are fixed in this skill (see Step 3). Extract them into config only when a second project genuinely needs different values.

### Step 2 — Parse feedback into items

Break blob into atomic items. One "ask" = one item. Merges ("combine X and Y into Z") = one item. Multi-part suggestions split only if they stand or fall independently.

### Step 3 — Triage each item

For each item, fill:
- **Raw quote** — verbatim from source
- **Category** — one of: `IA`, `feature`, `content`, `bug`, `polish`, `vision`
- **Tier** — one of: `v1`, `v2`, `v3`, `vX`
- **Size** — `S` / `M` / `L` (no time estimates)
- **Decision** — one of: `accept`, `defer`, `reject`, `needs-discussion`
- **Rationale** — one sentence. Why this tier, why this decision.
- **Next action** — if `accept`: worktree branch name (slugified). Else: what unblocks it.
- **Dependencies** — other items, missing primitives, external blockers

Propose the full triage in a compact table before writing. Let the user override any field.

### Step 4 — Write the doc

Path: `{docs_dir}/YYYY-MM-DD-{source-slug}.md`

Slugify source the same way as branches (Step 6): lowercase, hyphens only, strip punctuation, max ~40 chars.

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

## Worktrees proposed

- `feedback/{branch-1}` — {one-line scope}
- `feedback/{branch-2}` — {one-line scope}

## Deferred / rejected / discussion

- {item} — {reason}
```

### Step 5 — Update index

Append to `{index_file}` (create if missing):
```markdown
- YYYY-MM-DD — {source} — {N items, M accepted} — [link](./YYYY-MM-DD-source.md)
```

### Step 6 — Propose worktrees (require explicit y/n)

For each `accept` item with a branch name:
1. Print the full list of proposed worktree commands, one per line:
   ```
   git worktree add ../{repo}-{branch-slug} -b feedback/{branch-slug}
   ```
2. Before running any of them, ask the user: *"Spawn these N worktrees now? (y/n)"*
3. Only on explicit `y` do you run the commands. On `n` or ambiguous, stop and leave the proposed list in the doc for manual spawn later.
4. Before each `git worktree add`, verify the target directory does not exist and the branch name does not collide with an existing branch. If either collides, skip that one and report it to the user.

Report list of spawned worktree paths back to user.

Branch slug rules: lowercase, hyphens only, no punctuation, max ~40 chars.

## Guardrails

- **Don't re-triage items already in the index** — check for prior triage of the same source+date before writing. If exists, offer merge or overwrite.
- **Never spawn worktrees silently** — always list them and require explicit y/n (Step 6).
- **Preserve the raw quote** — never paraphrase into the `Quote` field. Future re-reads need source fidelity.
- **No time estimates** — use Size (S/M/L) only.

## Red flags — stop and ask

- Feedback contains a security issue → break out, handle separately, do not bury in triage
- Feedback is really a spec (>1000 words of detailed requirements) → suggest `/ce-plan` or brainstorming skill instead
- User pastes code review comments → redirect to PR review flow
- Source is anonymous or unclear → ask before filing
