# cosmic-farmland-content

Content and review workflows: feedback pages, interactive review docs, carousels, meeting sync.

Split out of `cosmic-farmland` in 4.0.0 so the always-on context cost matches how often each skill fires. These fire while writing, not while coding. Install it and leave it disabled until you need it: a disabled plugin costs zero tokens, but its skills cannot fire until enabled plus a restart.

## Install

```
/plugin marketplace add marshallhouston/cosmic-farmland
/plugin install cosmic-farmland-content@cosmic-farmland
/plugin enable cosmic-farmland-content@cosmic-farmland
/reload-plugins
```

Disable when done: `/plugin disable cosmic-farmland-content@cosmic-farmland`.

## Contents

**Skills**

- `feedback` - section-by-section feedback page for a content file, then apply the feedback. `/feedback <file-path>`
- `interactive-review-doc` - interactive HTML review doc with a per-section feedback panel, copyable back out as markdown
- `slideshow` - LinkedIn/IG carousel from a topic or outline: HTML slides, PNGs, PDF, and a caption. Templates and house voice live in the skill dir (`VOICE.md`, `templates/`)

**Commands**

- `/granola-sync` - sync recent Granola meeting notes into `~/marshall.notes/meetings/` as markdown

## Notes

Bare command names only resolve if a shadow exists in `~/.claude/commands/`. Otherwise use the namespaced form: `/cosmic-farmland-content:granola-sync`. See the core plugin's README for the full explanation.
