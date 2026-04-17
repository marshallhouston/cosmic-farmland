---
name: feedback
description: "Generate a section-by-section feedback page for any content file, then apply the feedback. Use when the user says /feedback <file>, 'give me a feedback page', 'review this file', or wants to do structured section-by-section review of any markdown or text file."
argument-hint: <file-path>
---

# Feedback -- Section-by-Section Review Loop

Generate a feedback review page for a content file, collect structured feedback, and apply it.

## When to use

Any time the user wants to review a file section by section and apply structured feedback. Common triggers:
- `/feedback <file>`
- "give me a feedback page for this"
- "I want to review this draft"
- "let me give section-by-section feedback"

## How it works

The feedback loop has three phases:

### 1. Generate the review page

If the project has a feedback generator script (e.g., `_scripts/generate-feedback-html`), use it:

```bash
bundle exec ruby _scripts/generate-feedback-html "<file-path>"
```

If no project-specific generator exists, use the `/interactive-review-doc` skill to build the three-panel HTML review page on the fly from the file contents.

Then open the generated HTML:

```bash
open feedback.html
```

### 2. Collect feedback

Tell the user:

> feedback.html is open. fill in the sections, hit "copy all feedback as markdown", then paste it here.

Wait for the user to paste the feedback markdown.

### 3. Apply feedback

Work through each `## section-name` block in the pasted feedback:

- Find the corresponding section in the original file
- Apply the requested changes
- Preserve the author's voice and style (check CLAUDE.md for voice guidelines)
- Do not smooth out rawness, remove literary references, or add polish
- Handle "instead X -> do Y" patterns as direct replacements
- Handle "add" instructions by inserting content at the appropriate location
- Handle "cut" instructions by removing the specified content

After applying all section feedback, summarize what changed.

## The review page format

The review page is a three-panel HTML document:
- **Left sidebar:** section navigation with scroll-spy highlighting
- **Center:** the content, split by sections
- **Right panel:** feedback textareas for each section

The user fills in feedback per section, hits "Copy All Feedback", and pastes the markdown back. Only sections with feedback are included in the copy.

## Output format (what the user pastes back)

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
