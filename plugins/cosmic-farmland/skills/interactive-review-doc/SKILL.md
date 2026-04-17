---
name: interactive-review-doc
description: "Create interactive HTML review documents with a side-by-side feedback panel. Use this skill whenever the user asks to create a reviewable document, interactive review doc, feedback doc, or anything where they want to review content and leave section-by-section feedback that can be copied to clipboard. Also use when the user says 'review doc', 'review flow', 'feedback flow', 'interactive doc', or asks for any document with a feedback/notes/comments panel alongside the content. This skill should trigger even when the user doesn't explicitly mention 'review' — if they're creating a report, guide, plan, or any structured content and mention wanting to give feedback, iterate on it, or copy notes back into Claude, this is the right skill."
---

# Interactive Review Document Skill

This skill creates interactive HTML review documents — a structured content panel on the left with an always-visible feedback panel on the right. The user can add notes per section and copy all feedback to clipboard as formatted markdown, ready to paste back into Claude or Claude Code.

## Why this format exists

Marshall (and many users) have a recurring workflow: Claude produces structured content, the user reviews it section by section, and wants to send feedback back into Claude efficiently. Rather than switching between apps or taking notes elsewhere, this format keeps everything in one view with a one-click copy-to-clipboard that outputs clean markdown.

## Design Requirements

These are non-negotiable. They reflect real user preferences learned through iteration:

### Dark mode by default
Use a GitHub-dark-inspired palette. Key tokens:
- Background: `#0d1117`
- Surface: `#161b22`
- Surface raised: `#1c2129`
- Border: `#30363d`
- Text primary: `#e6edf3`
- Text muted: `#8b949e`
- Accent blue: `#58a6ff`
- Green: `#3fb950`
- Orange: `#d29922`

### Three-column layout
1. **Left sidebar (200px):** Section navigation with scroll-spy highlighting. Orange dots on sections that have feedback.
2. **Center content (flex):** The actual document content. Scrollable independently.
3. **Right panel (360px, always visible):** Feedback panel. This is NOT a drawer/overlay — it is a persistent, always-visible column. Each section gets a collapsible accordion row with a textarea. The active content section's feedback row auto-expands on scroll.

### Feedback panel behavior
- Accordion-style: section headers are clickable, expand to reveal textarea
- Auto-expand: as user scrolls content, the corresponding feedback section opens
- Auto-save: feedback saves to an in-memory object on every keystroke (no save button needed)
- Section headers turn orange when they have feedback
- Sidebar nav dots appear on sections with feedback

### Copy to clipboard
- "Copy All Feedback" button in top bar AND in feedback panel footer
- Output format is markdown with `## Section Name` headers and feedback text under each
- Only includes sections that have feedback (skip empty ones)
- Show a toast confirmation on copy

### Top bar
- Sticky, dark surface background
- Document title on left
- "Expand All" / "Collapse All" / "Copy All Feedback [badge count]" on right

### Responsive
- Under 1000px: hide left nav, keep content + feedback
- Under 700px: stack vertically, feedback below content

## How to build it

When this skill triggers, follow these steps:

### 1. Gather the content
Figure out what content goes into the review doc. This could be:
- Content you just generated in conversation
- A document the user uploaded
- Research you compiled
- Any structured content with logical sections

### 2. Structure into sections
Each section needs:
- A unique `data-key` (kebab-case, e.g., `executive-summary`)
- A display title (e.g., "Executive Summary")
- The HTML content (paragraphs, lists, tables, callouts)

### 3. Build the HTML
Write a single self-contained HTML file. No external dependencies. All CSS and JS inline.

Use this structure:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>[Doc Title] — Review</title>
  <style>/* dark mode styles per design tokens above */</style>
</head>
<body>
  <div class="topbar">...</div>
  <div class="layout"> <!-- CSS grid: 200px 1fr 360px -->
    <nav class="nav"><!-- built by JS --></nav>
    <main class="content"><!-- sections here --></main>
    <aside class="feedback-panel"><!-- built by JS --></aside>
  </div>
  <script>/* nav builder, feedback state, scroll spy, copy logic */</script>
</body>
</html>
```

### 4. Key implementation patterns

**Section HTML pattern:**
```html
<div class="section" data-key="section-key" id="s-section-key">
  <h2>Section Title</h2>
  <p>Content...</p>
</div>
```

**Section metadata JS object** (drives nav + feedback panel):
```js
const sectionMeta = {
  'section-key': 'Section Title',
  'another-key': 'Another Section',
};
```

**Feedback state:** Simple object `const fb = {};` keyed by section key. Textareas update this on `oninput`. No localStorage (not supported in Claude artifacts).

**Scroll spy:** Listen to scroll on `.content`, find current section by `getBoundingClientRect`, update nav `.active` class and auto-expand matching feedback section.

**Copy all:** Build markdown string from `fb` object, use `navigator.clipboard.writeText()`, show toast.

**Callout boxes** for important info:
```html
<div class="callout callout-blue">...</div>  <!-- info -->
<div class="callout callout-green">...</div> <!-- positive/tips -->
<div class="callout callout-orange">...</div> <!-- warnings -->
```

**Tables** for structured data with dark header row and alternating subtle row backgrounds.

### 5. Save and share
Save to the outputs directory and provide a `computer://` link.

## Content formatting guidelines

- Use `<h2>` for section titles, `<h3>` for subsections, `<h4>` for sub-subsections
- Use `<strong>` for emphasis within list items (bold the label, then description)
- Keep paragraphs concise — this is a review format, not a novel
- Use tables for anything with 3+ columns of structured data
- Use callout boxes sparingly for key takeaways, warnings, or action items
- Font sizes: section titles 22px, subsections 17px, body 16px, table cells 15px, nav/sidebar 14px, feedback headers 14px, feedback textareas 15px, topbar title 16px, buttons 14px

## Example output format when user clicks "Copy All"

```markdown
# [Document Title] — Feedback

## 1. Section Name
The user's feedback text here, exactly as typed.

## 4. Another Section
More feedback here.
```

This pastes cleanly into Claude Desktop or Claude Code for the next iteration.