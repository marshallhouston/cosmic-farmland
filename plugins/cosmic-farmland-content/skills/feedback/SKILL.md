---
name: feedback
description: "Section-by-section feedback page for a content file, then apply it. Triggers: /feedback <file>, 'give me a feedback page', 'review this file'."
argument-hint: <file-path>
---

# Feedback -- Section-by-Section Review Loop

Open a content file for human review, collect structured feedback, and apply it.

## When to use

Any time the user wants to review a file and apply structured feedback. Common triggers:
- `/feedback <file>`
- "give me a feedback page for this"
- "I want to review this draft"
- "let me give section-by-section feedback"

## How it works

Three phases: open the file in a review UI, collect feedback, apply it. Step 1 has two paths -- prefer the first.

### 1. Open the file for review

**Preferred path: `contextbridge open`** (if available on PATH)

```bash
contextbridge open "<file-path>"
```

This opens an inline annotation UI in the browser, blocks until the user submits, and writes the user's annotations to stdout as markdown. No copy-paste step. The Bash tool result IS the feedback -- skip phase 2 and go straight to phase 3.

Detect availability:

```bash
command -v contextbridge >/dev/null 2>&1
```

**Fallback path: project HTML generator + manual paste**

For machines without `contextbridge`, fall back to the old loop:

If the project has a feedback generator script (e.g., `_scripts/generate-feedback-html`):

```bash
bundle exec ruby _scripts/generate-feedback-html "<file-path>"
open feedback.html
```

If no project-specific generator exists, use the `/interactive-review-doc` skill to build a three-panel HTML review page on the fly, then `open feedback.html`.

### 2. Collect feedback (fallback path only)

Tell the user:

> feedback.html is open. fill in the sections, hit "copy all feedback as markdown", then paste it here.

Wait for the user to paste the feedback markdown.

(With `contextbridge open`, this phase is automatic -- annotations land in the Bash tool result.)

### 3. Apply feedback

Work through each comment block (either contextbridge's per-line annotations or the fallback's `## section-name` blocks):

- Find the corresponding section in the original file
- Apply the requested changes
- Preserve the author's voice and style (check CLAUDE.md for voice guidelines)
- Do not smooth out rawness, remove literary references, or add polish
- Handle "instead X -> do Y" patterns as direct replacements
- Handle "add" instructions by inserting content at the appropriate location
- Handle "cut" instructions by removing the specified content

After applying all feedback, summarize what changed.

## Why two paths

`contextbridge open` eliminates the manual copy-paste step that the HTML+paste flow requires. It uses the same transport pattern as PlanBridge: local HTTP server, browser annotation UI, submit -> stdout -> exit. Stdout lands in Claude's tool result naturally.

The HTML+paste fallback stays for machines without `contextbridge` installed and for cases where per-section textareas are genuinely needed (currently rare; inline annotation has proven sufficient for most reviews).

## Fallback review page format

The fallback HTML review page is a three-panel document:
- **Left sidebar:** section navigation with scroll-spy highlighting
- **Center:** the content, split by sections
- **Right panel:** feedback textareas for each section

The user fills in feedback per section, hits "Copy All Feedback", and pastes the markdown back. Only sections with feedback are included in the copy.

## Fallback output format (what the user pastes back)

```markdown
# feedback: [document title]

## section name

instead: "original text"
do: "replacement text"

add "new content to insert"

cut "content to remove"

## another section

free-form feedback here
```
