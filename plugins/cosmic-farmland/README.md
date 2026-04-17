# cosmic-farmland

Marshall's cross-project skills, commands, and hooks.

## Install

In Claude Code:

```
/plugin marketplace add marshallhouston/cosmic-farmland
/plugin install cosmic-farmland@cosmic-farmland
/reload-plugins
```

## Contents

**Skills**

- `disk-memory-cleanup` — free disk space (Xcode caches, node_modules, etc.)
- `fart-smell-detection` — PTVM ("Prove The Value Motherfucker") audit of recent commits or a PR. Flags cologne-sniffing changes, ranks kill candidates. Four skepticism levels: `whiff` → `sniff` → `huff` → `dutch-oven-yourselff`.
- `feedback` — section-by-section review loop
- `golf-tee-times` — check tee time availability
- `handoff` — generate self-contained session handoff
- `interactive-review-doc` — create interactive HTML review docs

**Commands**

- `/execute-plan` — execute a written plan
- `/fart-smell-detection [level] [target]` — run the skill above. Target = PR number, git range, `--staged`, or auto-detect current branch's open PR. Aliases: `/ptvm`, `/prove-the-value-motherfucker`.
- `/granola-sync` — sync recent Granola meetings
