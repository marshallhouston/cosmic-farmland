---
name: handoff
description: "Generate self-contained resumption prompt for fresh session after /clear. Triggers: 'handoff', 'resumption prompt', 'pickup prompt', 'wrap up', 'pause here', 'prompt for new session'."
---

# Handoff -- Resumption Prompt Generator

Generate a self-contained prompt that captures current work state so a fresh session (after `/clear` or in a new terminal) can pick up exactly where this one left off. The prompt is the bridge between sessions -- it must carry enough context that the next session never re-discovers or re-brainstorms what this session already decided.

## When to use

Any time the user wants to pause and continue in a fresh context window. Common triggers:
- "give me a prompt to continue this after clear"
- "I want to pick this up in a fresh session"
- "wrap this up so I can continue later"
- "handoff prompt"

## What a good resumption prompt contains

A resumption prompt has five parts. Each is required unless genuinely not applicable.

### 1. Goal (1-2 sentences)
What the user is trying to accomplish, stated plainly. Not the history of how we got here -- just the destination.

### 2. Frozen decisions
Decisions made in this session that must not be revisited. Reference committed files by path. Use explicit language:
- "The design spec is committed and approved -- do not re-brainstorm or revise it."
- "The implementation plan is committed -- execute it task-by-task."

For each frozen artifact, state:
- Its file path
- That it has been reviewed and approved
- What the next session should NOT do with it (e.g., don't redesign, don't re-plan)

### 3. Key constraints
Non-obvious decisions baked into the spec/plan that a fresh session might otherwise re-discover or contradict. Pull these from the conversation -- they are the "why" behind choices that aren't obvious from reading the files alone. Keep to 3-7 bullets. Skip anything that's already clear from reading the referenced files.

### 4. Current state
Where things stand right now:
- What has been committed (branch name, recent commits)
- What has NOT been started yet
- Any open questions or known gaps

### 5. Next step (imperative)
A clear, single instruction for what the fresh session should do first. Not a menu of options -- one concrete action.

**Anchor to a specific skill invocation.** Name the skill the fresh session should use, so auto-triggered skills (e.g. `brainstorming`) don't hijack the intended next step. Examples below show this explicitly.

**Worktree guidance:** If the next step involves multi-task feature implementation (3+ tasks, new files, schema changes), the *sender* creates the git worktree before writing the handoff. Bake the absolute worktree path and branch name into the prompt so the fresh session starts inside it. Feature work happens on branches, not main.

Examples:
- "cd into `/Users/marshallhouston/code/preach-hub-feat-invites` (branch: `feat/invites`), then invoke `superpowers:executing-plans` on `docs/superpowers/plans/invites.md` starting at Task 1."
- "Run the test suite and fix any failures from the last session's changes. Do not invoke brainstorming or planning skills."
- "Invoke `superpowers:executing-plans` on `docs/superpowers/plans/...` starting at Task 4. Worktree already exists at cwd."

### 6. Receiver self-check (append verbatim)
Append this block to every handoff prompt so the fresh session verifies state before acting:

```
Before first action, verify:
- Referenced files exist at the committed SHA named above.
- cwd matches the worktree path stated above.
- Current branch matches.
If any check fails, stop and report -- do not guess or re-discover.
```

## How to generate the prompt

1. **Pre-flight git check.** Run `git status --short` and `git rev-parse HEAD`. If working tree is dirty and the handoff would reference uncommitted files, stop and ask the user: "Commit first, or explicitly flag these files as uncommitted in the prompt?" Never silently reference phantom files.
2. **Create worktree if needed.** If next step = multi-task feature work and current cwd is main checkout, create the worktree now (`git worktree add ../<repo>-<branch> -b <branch>`) before drafting. Capture the absolute path for the prompt.
3. **Scan the conversation** for specs, plans, decisions, and current state. Identify what has been committed vs. what is still in-flight.
4. **Read referenced files** to verify they exist and are current. Do not reference files that haven't been committed.
5. **Draft the prompt** following the six-part structure above.
6. **Hard cap: 250 words.** The prompt is a launch pad, not a novel. If "Key constraints" exceeds 3 bullets, move the rest into the spec file. Fresh session reads referenced files for detail.
7. **Copy to clipboard automatically** using `pbcopy` (macOS). Pipe raw prompt text (no markdown fences) to `pbcopy` via Bash so the user can paste immediately after `/clear`.
8. **Display the prompt** in a fenced code block so the user can review what was copied.
9. **Tell the user:** "Copied to clipboard. Run `/clear`, then paste."

## Format

1. Copy to clipboard via Bash:
```bash
echo '<the resumption prompt>' | pbcopy
```

2. Display the same prompt in a fenced code block for review.

3. One-liner: "Copied to clipboard. Run `/clear`, then paste."

## Anti-patterns to avoid

- **Don't summarize the entire conversation.** The prompt points at committed artifacts, it doesn't reproduce them.
- **Don't leave options open.** "You could do A or B" defeats the purpose. Pick the one that was decided.
- **Don't include context the files already contain.** If the spec explains the data model, don't repeat it in the prompt. Just point at the spec.
- **Don't use vague next steps.** "Continue the work" is useless. Name the skill and the entry point.
- **Don't forget to verify files exist.** A prompt that references a file that was never committed is worse than no prompt at all.
- **Don't skip the pre-flight git check.** Dirty working tree = uncommitted files = broken handoff. Commit first or flag explicitly.
- **Don't defer worktree creation to the fresh session.** If feature work, create it now and bake the path in.
