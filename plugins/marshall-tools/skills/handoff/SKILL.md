---
name: handoff
description: "Generate a self-contained resumption prompt for continuing work in a fresh session after /clear. This skill should be used when the user says 'handoff', 'resumption prompt', 'prompt for a fresh session', 'prompt to continue this', 'clear context', 'pickup prompt', 'prompt to address next steps in a clear context', 'generate a prompt for after clear', or any variation of wanting to capture current progress and next steps as a paste-able prompt for a new session. Also trigger when the user asks to 'wrap up' or 'pause here' and wants to continue later."
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
A clear, single instruction for what the fresh session should do first. Not a menu of options -- one concrete action. Examples:
- "Read the plan at `docs/superpowers/plans/...` and execute it using subagent-driven-development."
- "Create a worktree from main and begin Task 1 of the plan."
- "Run the test suite and fix any failures from the last session's changes."

## How to generate the prompt

1. **Scan the conversation** for specs, plans, decisions, and current state. Identify what has been committed vs. what is still in-flight.
2. **Read referenced files** to verify they exist and are current. Do not reference files that haven't been committed.
3. **Draft the prompt** following the five-part structure above. Write it as a fenced code block so the user can copy-paste it directly.
4. **Keep it concise.** Target 150-300 words. The prompt is a launch pad, not a novel. The fresh session will read the referenced files for detail.
5. **Output the prompt** in a single fenced code block with no commentary before it. Follow it with a brief note on what to do: "Copy this, run `/clear`, paste it in."

## Format

Output the resumption prompt as:

````
```
<the resumption prompt>
```
````

Then a one-liner: "Copy this, run `/clear`, paste it in."

## Anti-patterns to avoid

- **Don't summarize the entire conversation.** The prompt points at committed artifacts, it doesn't reproduce them.
- **Don't leave options open.** "You could do A or B" defeats the purpose. Pick the one that was decided.
- **Don't include context the files already contain.** If the spec explains the data model, don't repeat it in the prompt. Just point at the spec.
- **Don't use vague next steps.** "Continue the work" is useless. "Execute the plan at `path` starting from Task 1 using subagent-driven-development" is actionable.
- **Don't forget to verify files exist.** A prompt that references a file that was never committed is worse than no prompt at all.
