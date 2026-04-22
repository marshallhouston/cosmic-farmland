# cosmic-farmland

Marshall's cross-project skills, commands, and hooks.

## Breaking changes

**1.0.0** — `fart-smell-detection` skill/command renamed to `fart-sniffing-detection`. Pin to `0.5.1` if you relied on the old name.

Transition: `/fart-smell-detection` still works as a deprecated shim that forwards to the new skill and prints a rename notice. Shim will be removed in `2.0.0` — update scripts/muscle memory before then. Aliases `/ptv`, `/ptvm`, `/prove-the-value-motherfucker` unchanged.

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
- `fart-sniffing-detection` — PTVM ("Prove The Value Motherfucker") audit of recent commits or a PR. Flags cologne-sniffing changes, ranks kill candidates. Four skepticism levels: `whiff` → `sniff` → `huff` → `dutch-oven-yourselff`.
- `feedback` — section-by-section review loop
- `feedback-triage` — intake a raw feedback blob from a named source, triage each item (category/tier/size/decision), write a dated doc, propose worktrees for accepted items
- `golf-tee-times` — check tee time availability
- `handoff` — generate self-contained session handoff
- `interactive-review-doc` — create interactive HTML review docs

**Commands**

- `/execute-plan` — execute a written plan
- `/fart-sniffing-detection [level] [target]` — run the skill above. Target = PR number, git range, `--staged`, or auto-detect current branch's open PR. Aliases: `/ptvm`, `/prove-the-value-motherfucker`.
- `/feedback-triage <source>` — triage a pasted feedback blob from a named source (runs the `feedback-triage` skill)
- `/granola-sync` — sync recent Granola meetings
- `/ship [pr-number]` — watch a PR's checks, merge when green, clean up worktree + local branch. Defaults to current branch's PR.

## Short-name resolution (`/ptv` returning "Unknown command")

Claude Code resolves plugin commands under their namespaced form: `/cosmic-farmland:<name>`. The bare form (`/ptv`, `/next`, etc.) only resolves if a matching file exists in `~/.claude/commands/` as a **user-global shadow**. No shadow → bare name errors with "Unknown command: /ptv. Did you mean /ptvm?" even after `/plugin update` and `/reload-plugins`.

Two ways to use bare names:

1. **Use the namespaced form** — `/cosmic-farmland:ptv huff`. Always works.
2. **Install a shadow** — copy the plugin command file to `~/.claude/commands/`:
   ```
   cp ~/.claude/plugins/cache/cosmic-farmland/cosmic-farmland/*/commands/ptv.md ~/.claude/commands/ptv.md
   ```
   Then `/reload-plugins`. Shadow is machine-local (not tracked in this repo) and must be re-copied per machine. Shadows drift from the plugin over time — prefer the namespaced form unless muscle memory demands otherwise.
